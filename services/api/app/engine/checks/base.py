"""What every check evaluator shares: the subject, the gated source call, flag intents.

Evaluators never touch the database session. `run_checks` loads one `CheckSubject` per
enrolment, the evaluators turn it into `CheckOutcome`s (calling adapters through the
shared semaphore), and `run_checks` writes the rows.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from app.adapters.base import AdapterRequestError, RealAdapterDisabled, SourceUnavailable
from app.engine import evidence
from app.engine.contracts import CheckOutcome, FlagIntent
from app.engine.flags import dedupe_key
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    ConsentStatus,
    EnrolmentStatus,
    FlagType,
    ProgrammeLevel,
    ProgrammeMode,
    SeatType,
    Severity,
)

if TYPE_CHECKING:
    from app.notices.student_check import NoticeFact

log = logging.getLogger("countersign.checks")


@dataclass(frozen=True, slots=True)
class CheckSubject:
    """Everything the five evaluators need about one enrolment."""

    enrolment_id: uuid.UUID
    student_id: uuid.UUID
    institution_id: uuid.UUID
    institution_aicte_id: str
    institution_name: str
    state_code: str
    state_name: str
    programme_id: uuid.UUID
    programme_code: str
    programme_mode: ProgrammeMode
    programme_level: ProgrammeLevel | None
    academic_year: str
    cohort_year: str
    year_of_study: int
    admission_route: AdmissionRoute
    counselling_ref: str | None
    status: EnrolmentStatus
    # the held seat; seat_in_cohort_approval says whether its pool belongs to the
    # approval for (programme, cohort_year)
    seat_code: str | None
    seat_type: SeatType | None
    seat_in_cohort_approval: bool
    # the pool the route maps to, and its capacity in the cohort approval (None: no approval)
    target_seat_type: SeatType
    target_capacity: int | None
    name: str
    name_normalised: str
    dob: date
    nationality: str
    consent_status: ConsentStatus
    apaar_last4: str | None
    apaar_problem: str | None
    apaar_problem_masked: str | None
    checked_on: date
    # decrypted in memory only; never logged, never put in a detail or evidence
    apaar_id: str | None = field(default=None, repr=False)
    passport_no: str | None = field(default=None, repr=False)
    # the STUDENT check (ENGINES §16.4): every notice of the enrolment, oldest first; an
    # email address on record; the latest NOTICE consent is WITHDRAWN
    notices: tuple[NoticeFact, ...] = ()
    has_email: bool = False
    notice_consent_withdrawn: bool = False


@dataclass(frozen=True, slots=True)
class SourceDown:
    """A source call that met an outage, a disabled real adapter or a 4xx."""

    source: str
    detail: dict[str, Any]


async def call_source[T](
    gate: asyncio.Semaphore, source: str, call: Callable[[], Awaitable[T]]
) -> T | SourceDown:
    """Run one adapter call inside the semaphore; outages become SourceDown, never CONTRADICTED."""
    try:
        async with gate:
            return await call()
    except SourceUnavailable as exc:
        return SourceDown(source, evidence.source_unavailable(source, exc.detail))
    except RealAdapterDisabled:
        return SourceDown(source, evidence.source_unavailable(source, disabled=True))
    except AdapterRequestError as exc:
        log.error(
            "source rejected a check request", extra={"source": source, "status": exc.status_code}
        )
        return SourceDown(source, evidence.source_unavailable(source, f"HTTP {exc.status_code}"))


def unavailable_outcome(check: CheckType, down: SourceDown, calls: int = 1) -> CheckOutcome:
    """SOURCE_UNAVAILABLE: the source did not answer, so the row never contradicts (R4)."""
    return CheckOutcome(
        type=check,
        status=CheckStatus.SOURCE_UNAVAILABLE,
        source=down.source,
        detail=down.detail,
        calls=(down.source,) * calls,
        unavailable=(down.source,),
    )


def flag_intent(
    subject: CheckSubject,
    flag_type: FlagType,
    severity: Severity,
    evidence_: dict[str, Any],
) -> FlagIntent:
    """A flag about this one enrolment, keyed `<TYPE>:<enrolment_id>`."""
    return FlagIntent(
        type=flag_type,
        severity=severity,
        institution_id=subject.institution_id,
        academic_year=subject.academic_year,
        dedupe_key=dedupe_key(flag_type, subject.enrolment_id),
        evidence=evidence_,
        programme_id=subject.programme_id,
        enrolment_id=subject.enrolment_id,
    )


_DIGIT_COUNT = re.compile(r"has (\d+) digits")


def masked_problem_value(subject: CheckSubject) -> str:
    """The malformed APAAR as the registrar may see it: its length only."""
    if subject.apaar_problem_masked:
        return subject.apaar_problem_masked
    match = _DIGIT_COUNT.search(subject.apaar_problem or "")
    if match:
        return f"<{match.group(1)} characters>"
    return "Not stored"
