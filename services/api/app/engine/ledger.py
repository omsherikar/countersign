"""Seat Ledger (docs/ENGINES.md section 7, DECISIONS D16).

The target pool of an ACTIVE enrolment is the pool of seat type
`rules.admission_routes[route].pool` in the approval for (programme, cohort_year).
Releases run first; then every touched pool seats its queue, the unseated ACTIVE
enrolments of that pool including earlier ones (the backlog), oldest admission first,
taking FREE seats with `SELECT ... FOR UPDATE SKIP LOCKED`. Seat events are append-only
and every assignment and release is audited. A seat released because the enrolment was
withdrawn or transferred also revokes the enrolment's credentials (D26).
EXCESS_ADMISSION and QUOTA_BREACH are left to `flags.refresh_seat_flags`; the ledger only
raises LATE_REFILL.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import credentials
from app.core import audit
from app.core.audit import AuditEntry
from app.core.rules import Rules, get_rules
from app.engine import evidence as ev
from app.engine.contracts import LedgerResult, PoolRef
from app.engine.flags import dedupe_key, raise_flag
from app.engine.seatpools import CIWG
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    EnrolmentStatus,
    FlagType,
    SeatEventKind,
    SeatStatus,
    SeatType,
    Severity,
)
from app.models.institution import Approval, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch

RELEASE_REASONS = {
    EnrolmentStatus.WITHDRAWN: "withdrawal",
    EnrolmentStatus.TRANSFERRED: "transfer",
    EnrolmentStatus.GRADUATED: "graduation",
}
REVOKE_REASONS = {
    EnrolmentStatus.WITHDRAWN: "Enrolment withdrawn",
    EnrolmentStatus.TRANSFERRED: "Enrolment transferred",
}
ROUTE_OR_YEAR_CHANGED = "route or year changed"
LATE_REFILL_REASON = "late refill"


@dataclass(frozen=True, slots=True)
class _Pool:
    id: uuid.UUID
    approval_id: uuid.UUID
    seat_type: SeatType
    programme_id: uuid.UUID
    cohort_year: str
    cutoff_date: date | None

    @property
    def ref(self) -> PoolRef:
        return PoolRef(approval_id=self.approval_id, seat_type=self.seat_type)


def target_seat_type(route: AdmissionRoute, rules: Rules | None = None) -> SeatType:
    rules = rules or get_rules()
    return SeatType(rules.admission_routes[route.value].pool)


def is_ciwg(route: AdmissionRoute, nationality: str | None) -> bool:
    """A child of an Indian worker in the Gulf: international route, Indian national."""
    return route is AdmissionRoute.INTERNATIONAL and (nationality or "").upper() == "IN"


async def _pools_for(
    session: AsyncSession, cohorts: set[tuple[uuid.UUID, str]]
) -> dict[tuple[uuid.UUID, str, SeatType], _Pool]:
    if not cohorts:
        return {}
    rows = await session.execute(
        select(SeatPool.id, SeatPool.approval_id, SeatPool.seat_type, Approval)
        .join(Approval, Approval.id == SeatPool.approval_id)
        .where(Approval.programme_id.in_({p for p, _ in cohorts}))
    )
    out: dict[tuple[uuid.UUID, str, SeatType], _Pool] = {}
    for pool_id, approval_id, seat_type, approval in rows.all():
        if (approval.programme_id, approval.academic_year) not in cohorts:
            continue
        out[(approval.programme_id, approval.academic_year, seat_type)] = _Pool(
            id=pool_id,
            approval_id=approval_id,
            seat_type=seat_type,
            programme_id=approval.programme_id,
            cohort_year=approval.academic_year,
            cutoff_date=approval.cutoff_date,
        )
    return out


def _seat_entry(
    seat: Seat,
    before_status: SeatStatus,
    before_holder: uuid.UUID | None,
    event: SeatEventKind,
    reason: str | None,
    effective: date,
    actor_id: uuid.UUID | None,
) -> AuditEntry:
    return AuditEntry(
        action=AuditAction.UPDATE,
        entity_type="seat",
        entity_id=seat.id,
        actor_id=actor_id,
        before={
            "status": before_status.value,
            "enrolment_id": str(before_holder) if before_holder else None,
        },
        after={
            "status": seat.status.value,
            "enrolment_id": str(seat.enrolment_id) if seat.enrolment_id else None,
            "event": event.value,
            "reason": reason,
            "effective_date": effective.isoformat(),
        },
    )


async def assign_seats(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *, actor_id: uuid.UUID | None
) -> LedgerResult:
    """Release and assign seats for the given enrolments; idempotent."""
    result = LedgerResult()
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return result
    rules = get_rules()
    position = {enrolment_id: n for n, enrolment_id in enumerate(ids)}
    enrolments = sorted(
        (await session.execute(select(Enrolment).where(Enrolment.id.in_(ids)))).scalars().all(),
        key=lambda e: position[e.id],
    )
    held_ids = [e.seat_id for e in enrolments if e.seat_id is not None]
    held: dict[uuid.UUID, tuple[Seat, SeatPool]] = {}
    cohorts = {(e.programme_id, e.cohort_year) for e in enrolments}
    if held_ids:
        for seat, pool, programme_id, year in (
            await session.execute(
                select(Seat, SeatPool, Approval.programme_id, Approval.academic_year)
                .join(SeatPool, SeatPool.id == Seat.pool_id)
                .join(Approval, Approval.id == SeatPool.approval_id)
                .where(Seat.id.in_(held_ids))
                .order_by(Seat.id)
                .with_for_update(of=Seat)
            )
        ).all():
            held[seat.id] = (seat, pool)
            cohorts.add((programme_id, year))  # a released seat's pool seats its backlog too
    pools = await _pools_for(session, cohorts)

    def target_of(enrolment: Enrolment) -> _Pool | None:
        if enrolment.status is not EnrolmentStatus.ACTIVE:
            return None
        seat_type = target_seat_type(enrolment.admission_route, rules)
        return pools.get((enrolment.programme_id, enrolment.cohort_year, seat_type))

    entries: list[AuditEntry] = []
    touched: set[_Pool] = set()
    pool_by_id = {p.id: p for p in pools.values()}

    # 1. Releases: not ACTIVE any more, or holding a seat outside the target pool.
    for enrolment in enrolments:
        if enrolment.seat_id is None or enrolment.seat_id not in held:
            continue
        seat, pool = held[enrolment.seat_id]
        target = target_of(enrolment)
        if target is not None and target.id == pool.id:
            continue
        reason = RELEASE_REASONS.get(enrolment.status, ROUTE_OR_YEAR_CHANGED)
        before_status, before_holder = seat.status, seat.enrolment_id
        seat.status = SeatStatus.FREE
        seat.enrolment_id = None
        enrolment.seat_id = None
        session.add(
            SeatEvent(
                seat_id=seat.id,
                enrolment_id=enrolment.id,
                kind=SeatEventKind.RELEASE,
                actor_id=actor_id,
                reason=reason,
                effective_date=enrolment.status_date,
            )
        )
        entries.append(
            _seat_entry(
                seat,
                before_status,
                before_holder,
                SeatEventKind.RELEASE,
                reason,
                enrolment.status_date,
                actor_id,
            )
        )
        if enrolment.status in REVOKE_REASONS:
            await credentials.revoke_for_enrolment(
                session,
                enrolment.id,
                REVOKE_REASONS[enrolment.status],
                actor_id,
                audit_sink=entries,
            )
        result.released.append(enrolment.id)
        result.touched_pools.add(PoolRef(approval_id=pool.approval_id, seat_type=pool.seat_type))
        touched.add(pool_by_id[pool.id])
    await session.flush()  # free the seats before anyone is assigned one

    # 2. Assignments: every touched pool seats its whole queue, backlog first.
    for enrolment in enrolments:
        target = target_of(enrolment)
        if target is not None:
            touched.add(target)
    flag_sink: list[AuditEntry] = []
    for pool in sorted(touched, key=lambda p: (str(p.approval_id), p.seat_type.value)):
        seated = await _seat_queue(session, pool, rules, actor_id, entries, flag_sink, result)
        if seated:
            result.touched_pools.add(pool.ref)
    await session.flush()

    # 3. Input enrolments still ACTIVE and without a seat.
    for enrolment in enrolments:
        target = target_of(enrolment)
        if enrolment.status is EnrolmentStatus.ACTIVE and enrolment.seat_id is None:
            result.unseated.append(enrolment.id)
            if target is not None:
                result.touched_pools.add(target.ref)
    await audit.record_many(session, [*entries, *flag_sink])
    return result


async def _seat_queue(
    session: AsyncSession,
    pool: _Pool,
    rules: Rules,
    actor_id: uuid.UUID | None,
    entries: list[AuditEntry],
    flag_sink: list[AuditEntry],
    result: LedgerResult,
) -> int:
    routes = [r for r in AdmissionRoute if target_seat_type(r, rules) is pool.seat_type]
    queue = (
        await session.execute(
            select(Enrolment, Student.nationality)
            .join(Student, Student.id == Enrolment.student_id)
            .where(
                Enrolment.programme_id == pool.programme_id,
                Enrolment.cohort_year == pool.cohort_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
                Enrolment.admission_route.in_(routes),
                Enrolment.seat_id.is_(None),
            )
            .order_by(
                Enrolment.admission_date,
                Enrolment.uploaded_at,
                Enrolment.source_row_no.nulls_last(),
                Enrolment.id,
            )
        )
    ).all()
    if not queue:
        return 0

    international = pool.seat_type is SeatType.INTERNATIONAL
    free_stmt = (
        select(Seat)
        .where(Seat.pool_id == pool.id, Seat.status == SeatStatus.FREE)
        .order_by(Seat.seat_code)
        .with_for_update(skip_locked=True)
    )
    if not international:
        free_stmt = free_stmt.limit(len(queue))
    free = list((await session.execute(free_stmt)).scalars().all())
    if not free:
        return 0
    unreserved = [s for s in free if s.reserved_for is None]
    reserved = [s for s in free if s.reserved_for == CIWG]
    if not international:
        unreserved, reserved = free, []

    chosen: list[tuple[Enrolment, Seat]] = []
    for enrolment, nationality in queue:
        if international and is_ciwg(enrolment.admission_route, nationality) and reserved:
            seat = reserved.pop(0)
        elif unreserved:
            seat = unreserved.pop(0)
        else:
            continue
        chosen.append((enrolment, seat))
    if not chosen:
        return 0

    released_on = await _last_release(session, [s.id for _, s in chosen])
    late = [
        (e, s)
        for e, s in chosen
        if s.id in released_on
        and pool.cutoff_date is not None
        and e.admission_date > pool.cutoff_date
    ]
    late_ids = {e.id for e, _ in late}
    for enrolment, seat in chosen:
        before_status, before_holder = seat.status, seat.enrolment_id
        seat.status = SeatStatus.ASSIGNED
        seat.enrolment_id = enrolment.id
        enrolment.seat_id = seat.id
        reason = LATE_REFILL_REASON if enrolment.id in late_ids else None
        session.add(
            SeatEvent(
                seat_id=seat.id,
                enrolment_id=enrolment.id,
                kind=SeatEventKind.ASSIGN,
                actor_id=actor_id,
                reason=reason,
                effective_date=enrolment.admission_date,
            )
        )
        entries.append(
            _seat_entry(
                seat,
                before_status,
                before_holder,
                SeatEventKind.ASSIGN,
                reason,
                enrolment.admission_date,
                actor_id,
            )
        )
        result.seated.append(enrolment.id)
    await session.flush()

    if late:
        batches = await _batch_names(session, {e.upload_batch_id for e, _ in late})
        programme = await session.get(Programme, pool.programme_id)
        assert programme is not None and pool.cutoff_date is not None
        for enrolment, seat in late:
            evidence = ev.late_refill(
                seat_code=seat.seat_code,
                released_on=released_on[seat.id],
                assigned_on=enrolment.admission_date,
                cutoff=pool.cutoff_date,
                cohort_year=pool.cohort_year,
                filename=batches.get(enrolment.upload_batch_id),
                row_no=enrolment.source_row_no,
                related=[enrolment.id],
            )
            raised = await raise_flag(
                session,
                type=FlagType.LATE_REFILL,
                severity=Severity.MEDIUM,
                institution_id=programme.institution_id,
                programme_id=programme.id,
                enrolment_id=enrolment.id,
                academic_year=enrolment.academic_year,
                dedupe_key=dedupe_key(FlagType.LATE_REFILL, seat.id, enrolment.id),
                evidence=evidence,
                actor_id=actor_id,
                audit_sink=flag_sink,
            )
            result.flags.count(raised)
            result.late_refills.append(enrolment.id)
    return len(chosen)


async def _last_release(session: AsyncSession, seat_ids: list[uuid.UUID]) -> dict[uuid.UUID, date]:
    """Seats among the ids that were released before, with the date of the latest release."""
    if not seat_ids:
        return {}
    rows = await session.execute(
        select(
            SeatEvent.seat_id,
            func.max(func.coalesce(SeatEvent.effective_date, func.date(SeatEvent.at))),
        )
        .where(SeatEvent.seat_id.in_(seat_ids), SeatEvent.kind == SeatEventKind.RELEASE)
        .group_by(SeatEvent.seat_id)
    )
    return {seat_id: released for seat_id, released in rows.all()}


async def _batch_names(
    session: AsyncSession, batch_ids: set[uuid.UUID | None]
) -> dict[uuid.UUID | None, str]:
    wanted = [b for b in batch_ids if b is not None]
    if not wanted:
        return {}
    rows = await session.execute(
        select(UploadBatch.id, UploadBatch.filename).where(UploadBatch.id.in_(wanted))
    )
    return {batch_id: filename for batch_id, filename in rows.all()}
