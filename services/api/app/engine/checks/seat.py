"""SEAT: does the enrolment fit a seat of the approval version (D16, D41)? No source call.

The Seat Ledger derives it from the college's own upload against AICTE's approval, so the
row is never independent enrolment evidence; it cites the cohort approval's current
version. A seated enrolment is also checked for category eligibility as the college
reported it: a breach is Contradicted with the handbook clause and an ELIGIBILITY_BREACH
case; a TFW seat with the income certificate not reported waits as Pending.
"""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet
from app.core.rules import get_rules
from app.engine import eligibility
from app.engine import evidence as ev
from app.engine.checks.base import CheckSubject, flag_intent
from app.engine.contracts import CheckOutcome
from app.engine.flags import seat_flag_key
from app.models.enums import CheckStatus, CheckType, FlagType, SeatType, Severity

SOURCE = "SEAT_LEDGER"
CHECK = CheckType.SEAT


def seat_flag_type(seat_type: SeatType) -> FlagType:
    return FlagType.EXCESS_ADMISSION if seat_type is SeatType.REGULAR else FlagType.QUOTA_BREACH


def _outcome(subject: CheckSubject, status: CheckStatus, detail: dict, flags=()) -> CheckOutcome:
    version = subject.approval_version or 1
    return CheckOutcome(
        type=CHECK,
        status=status,
        source=SOURCE,
        detail=detail,
        flags=tuple(flags),
        supplied_by=ev.approval_line(version, subject.cohort_year),
        independent=False,
    )


def decide(subject: CheckSubject) -> CheckOutcome:
    version = subject.approval_version or 1
    approval = {"approval_id": subject.approval_id, "version": version}
    if subject.seat_code and subject.seat_type and subject.seat_in_cohort_approval:
        verdict = eligibility.check(
            subject.seat_type, subject.nationality, subject.eligibility, get_rules()
        )
        reported = eligibility.markers(subject.eligibility)
        if verdict.state == "BREACH":
            assert verdict.rule and verdict.reported_word and verdict.clause
            case = flag_intent(
                subject,
                FlagType.ELIGIBILITY_BREACH,
                Severity.HIGH if subject.seat_type is SeatType.INTERNATIONAL else Severity.MEDIUM,
                ev.eligibility_breach(
                    seat_code=subject.seat_code,
                    seat_type=subject.seat_type,
                    programme_code=subject.programme_code,
                    cohort_year=subject.cohort_year,
                    reported_word=verdict.reported_word,
                    allowed_words=verdict.allowed_words or "",
                    clause=verdict.clause,
                    related=[subject.enrolment_id],
                ),
            )
            detail = ev.seat_not_eligible(
                subject.seat_code,
                subject.seat_type,
                rule=verdict.rule,
                reported_word=verdict.reported_word,
                clause=verdict.clause,
                reported=reported,
                cohort_year=subject.cohort_year,
                **approval,
            )
            return _outcome(subject, CheckStatus.CONTRADICTED, detail, (case,))
        if verdict.state == "NOT_REPORTED":
            detail = ev.seat_tfw_not_reported(
                subject.seat_code,
                subject.seat_type,
                reported=reported,
                cohort_year=subject.cohort_year,
                **approval,
            )
            return _outcome(subject, CheckStatus.PENDING, detail)
        detail = ev.seat_confirmed(
            subject.seat_code, subject.seat_type, cohort_year=subject.cohort_year, **approval
        )
        return _outcome(subject, CheckStatus.CONFIRMED, detail)
    target = subject.target_seat_type
    flag_type = seat_flag_type(target)
    key = seat_flag_key(subject.programme_id, subject.cohort_year, target)
    if not subject.target_capacity:
        detail = ev.seat_no_pool(
            subject.admission_route,
            target,
            subject.programme_code,
            subject.cohort_year,
            flag_type,
            key,
            **approval,
        )
    else:
        detail = ev.seat_missing(
            target, subject.programme_code, subject.cohort_year, flag_type, key, **approval
        )
    # the EXCESS_ADMISSION or QUOTA_BREACH case is raised by the FLAGS stage with the
    # batch's final numbers
    return _outcome(subject, CheckStatus.CONTRADICTED, detail)


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet | None, gate: asyncio.Semaphore
) -> CheckOutcome:
    return decide(subject)
