"""ADMISSION, the Joining record row: did the student join this college in this programme
(D39; API_CONTRACT §A4.4; ENGINES §17.4)?

Every route except International reads the state admission authority's joining record:
management, NRI and spot admissions are approved by the state regulator too. The request
names the student as uploaded, the year they joined the programme (a lateral entrant joins
in year 2), the college's AICTE id and the programme; no roll number, since the upload's
counselling reference is an allotment reference. International admissions read Study in
India.

Not found is a contradiction only after the reporting deadline: before it the row is
Pending, and while the authority has published nothing it is Not yet due. An authority
that is late to publish is never the student's contradiction.
"""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet, JoiningResult, SiiResult
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.checks.base import (
    SUPPLIED_BY,
    CheckSubject,
    SourceDown,
    call_source,
    flag_intent,
    unavailable_outcome,
)
from app.engine.contracts import CheckOutcome
from app.models.enums import CheckStatus, CheckType, FlagType, Severity

CHECK = CheckType.ADMISSION
SOURCE = "ADMISSION_AUTHORITY"
JOINING_RECORD = "JOINING_RECORD"
STUDY_IN_INDIA = "STUDY_IN_INDIA"


def admission_check_for(subject: CheckSubject) -> str:
    return get_rules().admission_routes[subject.admission_route.value].admission_check


def _deadline(subject: CheckSubject):
    if subject.reporting_deadline is not None:
        return subject.reporting_deadline
    return get_rules().reporting.deadline_for(subject.joining_year or subject.cohort_year)


def decide_joining(subject: CheckSubject, result: JoiningResult) -> CheckOutcome:
    """The authority's answer to an evidence state (API_CONTRACT §A4.4)."""
    deadline = _deadline(subject)
    year = subject.joining_year or subject.cohort_year
    today = subject.checked_on
    words = {"state_name": subject.state_name, "joining_year": year, "deadline": deadline}
    flags = ()
    independent = True
    if result.found and result.joined_on is not None:
        status = CheckStatus.CONFIRMED
        detail = ev.admission_joined(
            programme_code=subject.programme_code,
            joined_on=result.joined_on,
            round_no=result.round,
            route=result.route,
            uploaded_route=subject.admission_route,
            today=today,
            **words,
        )
    elif not result.published:
        # the authority has published nothing for the state and year: it is late, or not
        # due yet; neither is evidence about the student
        independent = False
        if today <= deadline:
            status, detail = CheckStatus.NOT_YET_DUE, ev.admission_not_yet_due(today=today, **words)
        else:
            status = CheckStatus.PENDING
            detail = ev.admission_unpublished_late(today=today, **words)
    elif today <= deadline:
        status, detail = CheckStatus.PENDING, ev.admission_pending(today=today, **words)
    else:
        status = CheckStatus.CONTRADICTED
        detail = ev.admission_not_found(programme_code=subject.programme_code, today=today, **words)
        flags = (
            flag_intent(
                subject,
                FlagType.NOT_IN_JOINING_RECORD,
                Severity.MEDIUM,
                ev.not_in_joining_record(
                    state_name=subject.state_name,
                    programme_code=subject.programme_code,
                    joining_year=year,
                    deadline=deadline,
                    checked_on=today,
                    related=[subject.enrolment_id],
                ),
            ),
        )
    return CheckOutcome(
        type=CHECK,
        status=status,
        source=SOURCE,
        detail=detail,
        flags=flags,
        calls=(SOURCE,),
        supplied_by=SUPPLIED_BY[SOURCE],
        independent=independent,
    )


def decide_sii(subject: CheckSubject, result: SiiResult | None) -> CheckOutcome:
    """Study in India holds the international admission, at this college, programme and
    cohort, or it does not."""
    confirmed = (
        result is not None
        and result.admitted
        and result.institution_aicte_id == subject.institution_aicte_id
        and result.programme == subject.programme_code
        and result.academic_year == subject.cohort_year
    )
    flags = ()
    if confirmed:
        status = CheckStatus.CONFIRMED
        detail = ev.admission_sii_confirmed(subject.programme_code, subject.cohort_year)
    else:
        status, detail = CheckStatus.CONTRADICTED, ev.admission_sii_not_admitted()
        flags = (
            flag_intent(
                subject,
                FlagType.NOT_IN_JOINING_RECORD,
                Severity.MEDIUM,
                ev.not_in_study_in_india(
                    programme_code=subject.programme_code,
                    cohort_year=subject.cohort_year,
                    checked_on=subject.checked_on,
                    related=[subject.enrolment_id],
                ),
            ),
        )
    return CheckOutcome(
        type=CHECK,
        status=status,
        source="SII",
        detail=detail,
        flags=flags,
        calls=("SII",) if result is not None else (),
        supplied_by=SUPPLIED_BY["SII"],
        independent=True,
    )


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    if admission_check_for(subject) == STUDY_IN_INDIA:
        if not subject.passport_no:
            return decide_sii(subject, None)
        passport = subject.passport_no
        sii = await call_source(
            gate,
            "SII",
            lambda: adapters.sii.verify(passport, subject.name_normalised, subject.nationality),
        )
        if isinstance(sii, SourceDown):
            return unavailable_outcome(CHECK, sii)
        return decide_sii(subject, sii)
    found = await call_source(
        gate,
        SOURCE,
        lambda: adapters.admission_authority.joining(
            state=subject.state_code,
            academic_year=subject.joining_year or subject.cohort_year,
            name=subject.name_normalised,
            dob=subject.dob,
            institution_code=subject.institution_aicte_id,
            programme=subject.programme_code,
        ),
    )
    if isinstance(found, SourceDown):
        return unavailable_outcome(CHECK, found)
    return decide_joining(subject, found)
