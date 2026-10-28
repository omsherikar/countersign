"""The five checks (docs/ENGINES.md section 8, DECISIONS D18).

`run_checks` loads one subject per ACTIVE enrolment (one query per chunk), evaluates the
five checks for all of them concurrently with every adapter call behind one semaphore,
then writes check rows, flags and audit entries sequentially. The session is never used
inside the gather. `recheck_pending` does the same for PENDING and SOURCE_UNAVAILABLE checks
other than STUDENT.
`refresh_student` re-derives only the STUDENT check from the notices (ENGINES §16.4).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.adapters.base import AdapterSet
from app.core import audit
from app.core.audit import AuditEntry
from app.core.crypto import decrypt
from app.core.rules import get_rules
from app.engine.checks import admission, identity, seat, student, studying
from app.engine.checks.base import CheckSubject
from app.engine.contracts import (
    CHECK_ORDER,
    DEFAULT_CHECK_CONCURRENCY,
    NOT_COUNTED_STATES,
    RECHECK_STATES,
    CheckOutcome,
    ChecksResult,
    FlagTally,
    RecheckResult,
)
from app.engine.flags import raise_intents
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    SeatType,
)
from app.models.geo import State
from app.models.institution import Approval, Institution, Programme
from app.models.seat import Seat, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadRowError
from app.models.verification import Check
from app.notices import student_check
from app.privacy.service import notice_consent_withdrawn

EVALUATORS = {
    CheckType.IDENTITY: identity.evaluate,
    CheckType.ADMISSION: admission.evaluate,
    CheckType.SEAT: seat.evaluate,
    CheckType.STUDYING: studying.evaluate,
    CheckType.STUDENT: student.evaluate,
}
RECHECKABLE = tuple(t for t in CHECK_ORDER if t is not CheckType.STUDENT)

__all__ = ["CheckSubject", "load_subjects", "recheck_pending", "refresh_student", "run_checks"]


def _decrypt(token: bytes | None) -> str | None:
    if not token:
        return None
    try:
        return decrypt(token)
    except ValueError:
        return None


async def load_subjects(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *, today: date | None = None
) -> list[CheckSubject]:
    """Subjects for the ACTIVE enrolments among the ids, in the order of the ids."""
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return []
    rules = get_rules()
    today = today or datetime.now(UTC).date()
    held_pool = aliased(SeatPool)
    held_approval = aliased(Approval)
    problem_masked = (
        select(UploadRowError.value_masked)
        .where(
            UploadRowError.batch_id == Enrolment.upload_batch_id,
            UploadRowError.row_no == Enrolment.source_row_no,
            UploadRowError.code == "APAAR_FORMAT",
        )
        .limit(1)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(
                Enrolment,
                Student,
                Institution,
                State,
                Programme,
                Seat.seat_code,
                held_pool.seat_type,
                held_approval.programme_id,
                held_approval.academic_year,
                problem_masked,
            )
            .join(Student, Student.id == Enrolment.student_id)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(State, State.id == Institution.state_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .outerjoin(Seat, Seat.id == Enrolment.seat_id)
            .outerjoin(held_pool, held_pool.id == Seat.pool_id)
            .outerjoin(held_approval, held_approval.id == held_pool.approval_id)
            .where(Enrolment.id.in_(ids), Enrolment.status == EnrolmentStatus.ACTIVE)
        )
    ).all()

    cohort_keys = {(e.programme_id, e.cohort_year) for e, *_ in rows}
    capacities: dict[tuple[uuid.UUID, str], dict[SeatType, int]] = {}
    if cohort_keys:
        pool_rows = await session.execute(
            select(
                Approval.programme_id, Approval.academic_year, SeatPool.seat_type, SeatPool.capacity
            )
            .join(SeatPool, SeatPool.approval_id == Approval.id)
            .where(Approval.programme_id.in_({p for p, _ in cohort_keys}))
        )
        for programme_id, year, seat_type, capacity in pool_rows.all():
            capacities.setdefault((programme_id, year), {})[seat_type] = capacity

    notices = await student_check.load_notice_facts(session, [e.id for e, *_ in rows])
    withdrawn = await notice_consent_withdrawn(session, list({s.id for _, s, *_ in rows}))

    by_id: dict[uuid.UUID, CheckSubject] = {}
    for (
        enrolment,
        stu,
        institution,
        state,
        programme,
        seat_code,
        seat_type,
        held_programme_id,
        held_year,
        masked,
    ) in rows:
        target = SeatType(rules.admission_routes[enrolment.admission_route.value].pool)
        pools = capacities.get((enrolment.programme_id, enrolment.cohort_year))
        by_id[enrolment.id] = CheckSubject(
            enrolment_id=enrolment.id,
            student_id=stu.id,
            institution_id=institution.id,
            institution_aicte_id=institution.aicte_permanent_id,
            institution_name=institution.name,
            state_code=state.code,
            state_name=state.name,
            programme_id=programme.id,
            programme_code=programme.code,
            programme_mode=programme.mode,
            programme_level=programme.level,
            academic_year=enrolment.academic_year,
            cohort_year=enrolment.cohort_year,
            year_of_study=enrolment.year_of_study,
            admission_route=enrolment.admission_route,
            counselling_ref=enrolment.counselling_ref,
            status=enrolment.status,
            seat_code=seat_code,
            seat_type=seat_type,
            seat_in_cohort_approval=(
                seat_code is not None
                and held_programme_id == enrolment.programme_id
                and held_year == enrolment.cohort_year
            ),
            target_seat_type=target,
            target_capacity=None if pools is None else pools.get(target, 0),
            name=stu.name,
            name_normalised=stu.name_normalized,
            dob=stu.dob,
            nationality=stu.nationality,
            consent_status=stu.consent_status,
            apaar_last4=stu.apaar_last4,
            apaar_problem=enrolment.apaar_problem,
            apaar_problem_masked=masked,
            checked_on=today,
            apaar_id=_decrypt(stu.apaar_encrypted),
            passport_no=_decrypt(stu.passport_encrypted),
            notices=notices.get(enrolment.id, ()),
            has_email=stu.email is not None,
            notice_consent_withdrawn=stu.id in withdrawn,
        )
    return [by_id[i] for i in ids if i in by_id]


async def evaluate_subject(
    subject: CheckSubject,
    adapters: AdapterSet,
    gate: asyncio.Semaphore,
    types: Iterable[CheckType] = CHECK_ORDER,
) -> list[CheckOutcome]:
    return list(await asyncio.gather(*(EVALUATORS[t](subject, adapters, gate) for t in types)))


async def _existing_checks(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    types: Sequence[CheckType] | None = None,
) -> dict[tuple[uuid.UUID, CheckType], Check]:
    if not enrolment_ids:
        return {}
    stmt = select(Check).where(Check.enrolment_id.in_(enrolment_ids))
    if types is not None:
        stmt = stmt.where(Check.type.in_(types))
    rows = (
        (await session.execute(stmt.order_by(Check.enrolment_id, Check.type).with_for_update()))
        .scalars()
        .all()
    )
    return {(c.enrolment_id, c.type): c for c in rows}


class _Writer:
    """Applies outcomes to check rows and collects counts, flags and audit entries."""

    def __init__(self, session: AsyncSession, existing: dict, actor_id: uuid.UUID | None):
        self.session = session
        self.existing = existing
        self.actor_id = actor_id
        self.now = datetime.now(UTC)
        self.audit: list[AuditEntry] = []
        self.flags = FlagTally()
        self.transitions: list[tuple[CheckType, CheckStatus | None, CheckStatus]] = []

    async def write(self, subject: CheckSubject, outcomes: list[CheckOutcome]) -> int:
        """Upsert the rows of one enrolment; returns how many were created or changed status."""
        before: dict[str, str] = {}
        after: dict[str, str] = {}
        changed = 0
        for outcome in outcomes:
            row = self.existing.get((subject.enrolment_id, outcome.type))
            met_outage = bool(outcome.unavailable)
            if row is None:
                row = Check(
                    enrolment_id=subject.enrolment_id,
                    type=outcome.type,
                    status=outcome.status,
                    source=outcome.source,
                    detail=outcome.detail,
                    checked_at=self.now,
                    attempts=1 if met_outage else 0,
                )
                self.session.add(row)
                self.existing[(subject.enrolment_id, outcome.type)] = row
                self.transitions.append((outcome.type, None, outcome.status))
                after[outcome.type.value] = outcome.status.value
                changed += 1
            else:
                previous = row.status
                self.transitions.append((outcome.type, previous, outcome.status))
                if previous is not outcome.status:
                    before[outcome.type.value] = previous.value
                    after[outcome.type.value] = outcome.status.value
                    changed += 1
                if (
                    previous is not outcome.status
                    or row.detail != outcome.detail
                    or row.source != outcome.source
                ):
                    row.status = outcome.status
                    row.detail = outcome.detail
                    row.source = outcome.source
                    row.checked_at = self.now
                if met_outage:
                    row.attempts = (row.attempts or 0) + 1
            if outcome.flags:
                self.flags.merge(
                    await raise_intents(
                        self.session, outcome.flags, actor_id=self.actor_id, audit_sink=self.audit
                    )
                )
        if after:
            self.audit.append(
                AuditEntry(
                    action=AuditAction.UPDATE,
                    entity_type="enrolment",
                    entity_id=subject.enrolment_id,
                    actor_id=self.actor_id,
                    before={"checks": before},
                    after={"checks": after},
                )
            )
        return changed

    async def finish(self) -> None:
        await self.session.flush()
        await audit.record_many(self.session, self.audit)


def _count_outcomes(result: ChecksResult, outcomes: Iterable[CheckOutcome]) -> None:
    for outcome in outcomes:
        by_status = result.statuses.setdefault(outcome.type.value, {})
        by_status[outcome.status.value] = by_status.get(outcome.status.value, 0) + 1
        for source in outcome.calls:
            result.calls[source] = result.calls.get(source, 0) + 1
        for source in outcome.unavailable:
            result.unavailable[source] = result.unavailable.get(source, 0) + 1


async def run_checks(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    adapters: AdapterSet,
    *,
    concurrency: int = DEFAULT_CHECK_CONCURRENCY,
    actor_id: uuid.UUID | None = None,
) -> ChecksResult:
    """Evaluate all five checks for the ACTIVE enrolments among the ids and write them."""
    subjects = await load_subjects(session, enrolment_ids)
    result = ChecksResult(enrolments=len(subjects))
    if not subjects:
        return result
    existing = await _existing_checks(session, [s.enrolment_id for s in subjects])
    gate = asyncio.Semaphore(max(1, concurrency))
    evaluated = await asyncio.gather(*(evaluate_subject(s, adapters, gate) for s in subjects))
    writer = _Writer(session, existing, actor_id)
    for subject, outcomes in zip(subjects, evaluated, strict=True):
        result.changed += await writer.write(subject, outcomes)
        _count_outcomes(result, outcomes)
    await writer.finish()
    result.flags.merge(writer.flags)
    return result


async def refresh_student(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *, actor_id: uuid.UUID | None = None
) -> ChecksResult:
    """Re-derive the STUDENT check of the ACTIVE enrolments among the ids and write it.

    The one way the notices write the STUDENT row: same writer as `run_checks` (row,
    `checked_at` on change, STUDENT_DENIED through `raise_intents`, one audit UPDATE per
    enrolment whose status changed). Flushes, never commits.
    """
    subjects = await load_subjects(session, enrolment_ids)
    result = ChecksResult(enrolments=len(subjects))
    if not subjects:
        return result
    existing = await _existing_checks(
        session, [s.enrolment_id for s in subjects], [CheckType.STUDENT]
    )
    writer = _Writer(session, existing, actor_id)
    for subject in subjects:
        outcome = student_check.derive(subject, now=writer.now)
        result.changed += await writer.write(subject, [outcome])
        _count_outcomes(result, [outcome])
    await writer.finish()
    result.flags.merge(writer.flags)
    return result


async def recheck_pending(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    adapters: AdapterSet,
    *,
    concurrency: int = DEFAULT_CHECK_CONCURRENCY,
    actor_id: uuid.UUID | None = None,
) -> RecheckResult:
    """Re-run the PENDING and SOURCE_UNAVAILABLE checks other than STUDENT of the ACTIVE
    enrolments among the ids.

    `enrolments` counts the enrolments that had something to re-run.
    """
    result = RecheckResult()
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return result
    pending_rows = (
        await session.execute(
            select(Check.enrolment_id, Check.type)
            .join(Enrolment, Enrolment.id == Check.enrolment_id)
            .where(
                and_(
                    Check.enrolment_id.in_(ids),
                    Check.status.in_(RECHECK_STATES),
                    Check.type.in_(RECHECKABLE),
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
            )
        )
    ).all()
    pending: dict[uuid.UUID, list[CheckType]] = {}
    for enrolment_id, check_type in pending_rows:
        pending.setdefault(enrolment_id, []).append(check_type)
    if not pending:
        return result
    subjects = await load_subjects(session, [i for i in ids if i in pending])
    existing = await _existing_checks(session, [s.enrolment_id for s in subjects])
    gate = asyncio.Semaphore(max(1, concurrency))
    evaluated = await asyncio.gather(
        *(
            evaluate_subject(
                s, adapters, gate, [t for t in CHECK_ORDER if t in pending[s.enrolment_id]]
            )
            for s in subjects
        )
    )
    writer = _Writer(session, existing, actor_id)
    for subject, outcomes in zip(subjects, evaluated, strict=True):
        await writer.write(subject, outcomes)
    await writer.finish()
    result.enrolments = len(subjects)
    for _type, _before, after in writer.transitions:
        result.rechecked += 1
        if after is CheckStatus.CONFIRMED:
            result.now_pass += 1
        elif after is CheckStatus.CONTRADICTED:
            result.now_fail += 1
        elif after in NOT_COUNTED_STATES:
            result.now_na += 1
        else:
            result.still_pending += 1
    result.flags = writer.flags
    return result
