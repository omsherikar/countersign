"""IDENTITY: the APAAR registry confirms the id, the name and the date of birth (D18)."""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet, ApaarResult
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.checks.base import (
    CheckSubject,
    SourceDown,
    call_source,
    flag_intent,
    masked_problem_value,
    pending_unavailable,
)
from app.engine.contracts import CheckOutcome
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


def _outcome(status: CheckStatus, detail: dict, flags=(), calls=()) -> CheckOutcome:
    return CheckOutcome(
        type=CHECK, status=status, source=SOURCE, detail=detail, flags=tuple(flags), calls=calls
    )


def decide(subject: CheckSubject, result: ApaarResult) -> CheckOutcome:
    """The registry's answer to a status, a detail and the flag it calls for."""
    thresholds = get_rules().name_matching
    last4 = subject.apaar_last4
    calls = (SOURCE,)
    related = [subject.enrolment_id]
    if not result.exists:
        flag = flag_intent(
            subject,
            FlagType.INVALID_APAAR,
            Severity.HIGH,
            ev.invalid_apaar_not_found(last4, subject.checked_on, related),
        )
        return _outcome(CheckStatus.FAIL, ev.identity_not_found(last4), [flag], calls)
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
        return _outcome(CheckStatus.FAIL, detail, [flag], calls)
    if result.name_score >= thresholds.pass_threshold:
        return _outcome(CheckStatus.PASS, ev.identity_pass(result.name_score, last4), (), calls)
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
        return _outcome(
            CheckStatus.PENDING, ev.identity_review(result.name_score, last4), [flag], calls
        )
    return _outcome(
        CheckStatus.FAIL, ev.identity_name_differs(result.name_score, last4), [flag], calls
    )


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    if (
        subject.admission_route is AdmissionRoute.INTERNATIONAL
        or subject.consent_status is ConsentStatus.INTERNATIONAL
    ):
        return _outcome(CheckStatus.NA, ev.identity_international())
    if subject.apaar_problem:
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
        return _outcome(CheckStatus.FAIL, ev.identity_malformed(subject.apaar_problem), [flag])
    if not subject.apaar_id:
        return _outcome(CheckStatus.NA, ev.identity_no_apaar())
    apaar_id = subject.apaar_id
    result = await call_source(
        gate, SOURCE, lambda: adapters.apaar.verify(apaar_id, subject.name_normalised, subject.dob)
    )
    if isinstance(result, SourceDown):
        return pending_unavailable(CHECK, result)
    return decide(subject, result)
