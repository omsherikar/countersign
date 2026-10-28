"""ADMISSION: the counselling list, the seat-type rules or Study in India, by route (D18)."""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet, CounsellingResult, SiiResult
from app.core.cohort import start_year
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.checks.base import CheckSubject, SourceDown, call_source, pending_unavailable
from app.engine.contracts import CheckOutcome
from app.models.enums import CheckStatus, CheckType

CHECK = CheckType.ADMISSION
COUNSELLING_LIST = "COUNSELLING_LIST"
SEAT_TYPE_RULES = "SEAT_TYPE_RULES"
STUDY_IN_INDIA = "STUDY_IN_INDIA"


def admission_check_for(subject: CheckSubject) -> str:
    return get_rules().admission_routes[subject.admission_route.value].admission_check


def decide_counselling(subject: CheckSubject, result: CounsellingResult) -> CheckOutcome:
    cohort_start = start_year(subject.cohort_year)
    if result.found:
        status = CheckStatus.PASS
        detail = ev.admission_counselling_found(
            state_name=subject.state_name,
            programme_code=subject.programme_code,
            cohort_start=cohort_start,
            round_no=result.round,
            allotment_ref=result.allotment_ref,
            counselling_ref=subject.counselling_ref,
        )
    else:
        status = CheckStatus.FAIL
        detail = ev.admission_counselling_not_found(
            state_name=subject.state_name,
            programme_code=subject.programme_code,
            cohort_start=cohort_start,
        )
    return CheckOutcome(
        type=CHECK, status=status, source="COUNSELLING", detail=detail, calls=("COUNSELLING",)
    )


def decide_seat_rules(subject: CheckSubject) -> CheckOutcome:
    """Management, spot and NRI: the route's pool exists in the cohort approval and the
    enrolment holds a seat in it."""
    route, code, year = subject.admission_route, subject.programme_code, subject.cohort_year
    target = subject.target_seat_type
    if not subject.target_capacity:
        status, detail = (
            CheckStatus.FAIL,
            ev.admission_seat_rules_no_pool(route, code, year, target),
        )
    elif subject.seat_in_cohort_approval and subject.seat_type is target:
        status, detail = CheckStatus.PASS, ev.admission_seat_rules_pass(route, code, target)
    else:
        status, detail = (
            CheckStatus.FAIL,
            ev.admission_seat_rules_no_seat(route, code, year, target),
        )
    return CheckOutcome(type=CHECK, status=status, source="SEAT_LEDGER", detail=detail)


def decide_sii(subject: CheckSubject, result: SiiResult) -> CheckOutcome:
    confirmed = (
        result.admitted
        and result.institution_aicte_id == subject.institution_aicte_id
        and result.programme == subject.programme_code
        and result.academic_year == subject.cohort_year
    )
    if confirmed:
        status = CheckStatus.PASS
        detail = ev.admission_sii_confirms(subject.programme_code, subject.cohort_year)
    else:
        status, detail = CheckStatus.FAIL, ev.admission_sii_no_match()
    return CheckOutcome(type=CHECK, status=status, source="SII", detail=detail, calls=("SII",))


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    kind = admission_check_for(subject)
    if kind == SEAT_TYPE_RULES:
        return decide_seat_rules(subject)
    if kind == STUDY_IN_INDIA:
        if not subject.passport_no:
            return CheckOutcome(
                type=CHECK,
                status=CheckStatus.FAIL,
                source="SII",
                detail=ev.admission_sii_no_match(),
            )
        passport = subject.passport_no
        sii = await call_source(
            gate,
            "SII",
            lambda: adapters.sii.verify(passport, subject.name_normalised, subject.nationality),
        )
        if isinstance(sii, SourceDown):
            return pending_unavailable(CHECK, sii)
        return decide_sii(subject, sii)
    # The upload's counselling_ref is the allotment reference, not the roll number the
    # list matches exactly, so it is compared after the match instead of sent as roll_no.
    found = await call_source(
        gate,
        "COUNSELLING",
        lambda: adapters.counselling.verify(
            state=subject.state_code,
            year=start_year(subject.cohort_year),
            name=subject.name_normalised,
            dob=subject.dob,
            programme=subject.programme_code,
            institution_aicte_id=subject.institution_aicte_id,
        ),
    )
    if isinstance(found, SourceDown):
        return pending_unavailable(CHECK, found)
    return decide_counselling(subject, found)
