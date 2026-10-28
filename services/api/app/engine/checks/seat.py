"""SEAT: the enrolment holds an assigned seat in its cohort approval (D16, D18). No call."""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet
from app.engine import evidence as ev
from app.engine.checks.base import CheckSubject
from app.engine.contracts import CheckOutcome
from app.engine.flags import seat_flag_key
from app.models.enums import CheckStatus, CheckType, FlagType, SeatType

SOURCE = "SEAT_LEDGER"
CHECK = CheckType.SEAT


def seat_flag_type(seat_type: SeatType) -> FlagType:
    return FlagType.EXCESS_ADMISSION if seat_type is SeatType.REGULAR else FlagType.QUOTA_BREACH


def decide(subject: CheckSubject) -> CheckOutcome:
    if subject.seat_code and subject.seat_type and subject.seat_in_cohort_approval:
        detail = ev.seat_holds(subject.seat_code, subject.seat_type, subject.cohort_year)
        return CheckOutcome(type=CHECK, status=CheckStatus.CONFIRMED, source=SOURCE, detail=detail)
    target = subject.target_seat_type
    flag_type = seat_flag_type(target)
    detail = ev.seat_missing(
        target,
        subject.programme_code,
        subject.cohort_year,
        flag_type,
        seat_flag_key(subject.programme_id, subject.cohort_year, target),
    )
    return CheckOutcome(type=CHECK, status=CheckStatus.CONTRADICTED, source=SOURCE, detail=detail)


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    return decide(subject)
