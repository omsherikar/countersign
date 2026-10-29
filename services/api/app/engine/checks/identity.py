"""IDENTITY: is this person who the college says (D34, D36; API_CONTRACT §A4.4)?

Four routes, first match wins: an international student is checked with Study in India by
passport; a linked APAAR with the APAAR registry; a record without a linked APAAR that the
student claimed through DigiLocker is confirmed by that sign-in; a malformed APAAR is the
college's own error; otherwise the row is Not applicable and the record waits for the
claim. Name matching supports a decision and never makes one: a name from 75 to 89 is
Pending for an officer.
"""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet, ApaarResult, SiiResult
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.checks.base import (
    SUPPLIED_BY,
    CheckSubject,
    SourceDown,
    call_source,
    flag_intent,
    masked_problem_value,
    unavailable_outcome,
)
from app.engine.contracts import CheckOutcome, FlagIntent
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    ConsentStatus,
    FlagType,
    Severity,
)

SOURCE = "APAAR"
CHECK = CheckType.IDENTITY


def _apaar(status: CheckStatus, detail: dict, flags: tuple[FlagIntent, ...] = ()) -> CheckOutcome:
    """A registry answer: supplied by the registry, independent of the college."""
    return CheckOutcome(
        type=CHECK,
        status=status,
        source=SOURCE,
        detail=detail,
        flags=flags,
        calls=(SOURCE,),
        supplied_by=SUPPLIED_BY["APAAR"],
        independent=True,
    )


def decide(subject: CheckSubject, result: ApaarResult) -> CheckOutcome:
    """The registry's answer to an evidence state, a detail and the case it calls for."""
    thresholds = get_rules().name_matching
    last4 = subject.apaar_last4
    related = [subject.enrolment_id]
    if not result.exists:
        flag = flag_intent(
            subject,
            FlagType.INVALID_APAAR,
            Severity.HIGH,
            ev.invalid_apaar_not_found(last4, subject.checked_on, related),
        )
        return _apaar(CheckStatus.CONTRADICTED, ev.identity_not_found(last4), (flag,))
    if thresholds.dob_must_match and not result.dob_match:
        flag = flag_intent(
            subject,
            FlagType.NAME_MISMATCH,
            Severity.MEDIUM,
            ev.name_mismatch(
                name=subject.name,
                name_score=result.name_score,
                dob_match=False,
                checked_on=subject.checked_on,
                related=related,
            ),
        )
        detail = ev.identity_dob_mismatch(result.name_score, last4)
        return _apaar(CheckStatus.CONTRADICTED, detail, (flag,))
    if result.name_score >= thresholds.pass_threshold:
        return _apaar(CheckStatus.CONFIRMED, ev.identity_confirmed(result.name_score, last4))
    review = result.name_score >= thresholds.review_threshold
    flag = flag_intent(
        subject,
        FlagType.NAME_MISMATCH,
        Severity.LOW if review else Severity.MEDIUM,
        ev.name_mismatch(
            name=subject.name,
            name_score=result.name_score,
            dob_match=True,
            checked_on=subject.checked_on,
            related=related,
        ),
    )
    if review:
        return _apaar(CheckStatus.PENDING, ev.identity_review(result.name_score, last4), (flag,))
    detail = ev.identity_name_differs(result.name_score, last4)
    return _apaar(CheckStatus.CONTRADICTED, detail, (flag,))


def decide_sii(result: SiiResult | None) -> CheckOutcome:
    """Study in India by passport: it knows the passport holder, or it has nothing."""
    known = result is not None and result.admitted
    return CheckOutcome(
        type=CHECK,
        status=CheckStatus.CONFIRMED if known else CheckStatus.PENDING,
        source="SII",
        detail=ev.identity_sii_confirmed() if known else ev.identity_sii_none(),
        calls=("SII",) if result is not None else (),
        supplied_by=SUPPLIED_BY["SII"],
        independent=True,
    )


def is_international(subject: CheckSubject) -> bool:
    return (
        subject.admission_route is AdmissionRoute.INTERNATIONAL
        or subject.consent_status is ConsentStatus.INTERNATIONAL
    )


def claimed(subject: CheckSubject) -> CheckOutcome:
    """The student signed in with DigiLocker and claimed the record (D36): the sign-in
    decides; the writer dates it at the claim."""
    return CheckOutcome(
        type=CHECK,
        status=CheckStatus.CONFIRMED,
        source="DIGILOCKER",
        detail=ev.identity_digilocker_claim(),
        supplied_by=SUPPLIED_BY["DIGILOCKER"],
        independent=True,
    )


def malformed(subject: CheckSubject) -> CheckOutcome:
    """The college uploaded an APAAR that is not 12 digits: its own error, dated the upload."""
    assert subject.apaar_problem is not None
    flag = flag_intent(
        subject,
        FlagType.INVALID_APAAR,
        Severity.MEDIUM,
        ev.invalid_apaar_malformed(
            subject.apaar_problem,
            masked_problem_value(subject),
            subject.checked_on,
            [subject.enrolment_id],
        ),
    )
    return CheckOutcome(
        type=CHECK,
        status=CheckStatus.CONTRADICTED,
        source=SOURCE,
        detail=ev.identity_malformed(subject.apaar_problem),
        flags=(flag,),
        supplied_by=SUPPLIED_BY["COLLEGE_UPLOAD"],
        observed_at=subject.uploaded_at,
        independent=False,
    )


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    if is_international(subject):
        if not subject.passport_no:
            return decide_sii(None)
        passport = subject.passport_no
        sii = await call_source(
            gate,
            "SII",
            lambda: adapters.sii.verify(passport, subject.name_normalised, subject.nationality),
        )
        if isinstance(sii, SourceDown):
            return unavailable_outcome(CHECK, sii)
        return decide_sii(sii)
    if subject.apaar_id:
        apaar_id = subject.apaar_id
        result = await call_source(
            gate,
            SOURCE,
            lambda: adapters.apaar.verify(apaar_id, subject.name_normalised, subject.dob),
        )
        if isinstance(result, SourceDown):
            return unavailable_outcome(CHECK, result)
        return decide(subject, result)
    if subject.digilocker_claimed:
        return claimed(subject)
    if subject.apaar_problem:
        return malformed(subject)
    return CheckOutcome(
        type=CHECK, status=CheckStatus.NOT_APPLICABLE, source=SOURCE, detail=ev.identity_no_apaar()
    )
