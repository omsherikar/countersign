"""Approval versions (D41; API_CONTRACT §A4.17; ENGINES §17.5).

`approval_versions` keeps every version of an approval and `approvals.current_version`
names the current one. Only an AICTE officer adds a version. In one transaction: the
version row, the approval's intake and current version, every pool resized from rules.yaml
(a raised pool gains FREE seats and seats its backlog; a lowered pool loses FREE seats), the
Seat rows of the cohort run again so they cite the new version, the seat cases refreshed
and the records' statuses settled. A version that would leave a pool below its assigned
seats is refused and changes nothing.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEntry
from app.core.deps import scope_institutions
from app.core.errors import ApiError, not_found
from app.core.rules import get_rules
from app.engine import checks, flags, ledger, seatpools, status
from app.engine.contracts import PoolRef
from app.models.enums import AuditAction, CheckType, EnrolmentStatus, SeatStatus, SeatType
from app.models.institution import Approval, ApprovalVersion, Institution, Programme
from app.models.seat import Seat, SeatPool
from app.models.student import Enrolment
from app.models.user import User

EFFECTIVE_TOO_EARLY = "A new version must take effect after the current one."
BELOW_ASSIGNED = "The new intake is below the seats already assigned."


def _iso(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z") if value is not None else ""


async def _scoped(
    session: AsyncSession, user: User, approval_id: uuid.UUID, *, lock: bool = False
) -> tuple[Approval, Programme, Institution]:
    stmt = (
        select(Approval, Programme, Institution)
        .join(Programme, Programme.id == Approval.programme_id)
        .join(Institution, Institution.id == Programme.institution_id)
        .where(Approval.id == approval_id)
    )
    if lock:
        stmt = stmt.with_for_update(of=Approval)
    row = (await session.execute(scope_institutions(stmt, user))).first()
    if row is None:
        raise not_found("Approval")
    return row[0], row[1], row[2]


async def _body(
    session: AsyncSession, approval: Approval, programme: Programme, institution: Institution
) -> dict[str, Any]:
    items = (
        (
            await session.execute(
                select(ApprovalVersion)
                .where(ApprovalVersion.approval_id == approval.id)
                .order_by(ApprovalVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "approval_id": str(approval.id),
        "institution": {
            "id": str(institution.id),
            "name": institution.name,
            "aicte_permanent_id": institution.aicte_permanent_id,
        },
        "programme": {"id": str(programme.id), "code": programme.code, "name": programme.name},
        "academic_year": approval.academic_year,
        "current_version": approval.current_version,
        "items": [
            {
                "version": v.version,
                "approved_intake": v.approved_intake,
                "effective_from": v.effective_from.isoformat(),
                "source": v.source,
                "created_at": _iso(v.created_at),
            }
            for v in items
        ],
    }


async def versions(session: AsyncSession, user: User, approval_id: uuid.UUID) -> dict[str, Any]:
    """The approval's versions, newest first; 404 outside the user's scope."""
    approval, programme, institution = await _scoped(session, user, approval_id)
    return await _body(session, approval, programme, institution)


def covers(approval: Approval, pool: SeatType, unseated: int) -> bool:
    """The approval's current version covers the admissions of a seat case on `pool` when,
    under it, no ACTIVE cohort enrolment of that pool is left without a seat (API_CONTRACT
    §A4.10): the backlog was seated when the version was added."""
    return unseated == 0


async def _assigned(session: AsyncSession, approval: Approval) -> dict[SeatType, int]:
    rows = await session.execute(
        select(SeatPool.seat_type, func.count(Seat.id))
        .join(Seat, Seat.pool_id == SeatPool.id)
        .where(SeatPool.approval_id == approval.id, Seat.status == SeatStatus.ASSIGNED)
        .group_by(SeatPool.seat_type)
    )
    return {seat_type: n for seat_type, n in rows.all()}


async def add_version(
    session: AsyncSession,
    user: User,
    approval_id: uuid.UUID,
    *,
    approved_intake: int,
    effective_from: date,
    source: str,
) -> dict[str, Any]:
    """A new version of the approval, with every effect in the caller's transaction."""
    rules = get_rules()
    approval, programme, institution = await _scoped(session, user, approval_id, lock=True)
    current = (
        await session.execute(
            select(ApprovalVersion).where(
                ApprovalVersion.approval_id == approval.id,
                ApprovalVersion.version == approval.current_version,
            )
        )
    ).scalar_one_or_none()
    if current is not None and effective_from < current.effective_from:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"effective_from: {EFFECTIVE_TOO_EARLY}",
            {"fields": [{"field": "effective_from", "message": EFFECTIVE_TOO_EARLY}]},
        )
    pools = list(
        (await session.execute(select(SeatPool).where(SeatPool.approval_id == approval.id)))
        .scalars()
        .all()
    )
    assigned = await _assigned(session, approval)
    changes = seatpools.pool_changes(
        approval, approved_intake, assigned, rules, programme=programme, pools=pools
    )
    short = [c for c in changes if c.below_assigned]
    if short:
        raise ApiError(
            409,
            "APPROVAL_BELOW_ASSIGNED",
            BELOW_ASSIGNED,
            {
                "intake": approved_intake,
                "assigned": sum(assigned.values()),
                "pools": [
                    {
                        "seat_type": c.seat_type.value,
                        "assigned": c.assigned,
                        "new_capacity": c.new_capacity,
                    }
                    for c in short
                ],
            },
        )

    before = {
        "current_version": approval.current_version,
        "approved_intake": approval.approved_intake,
    }
    version = ApprovalVersion(
        approval_id=approval.id,
        version=approval.current_version + 1,
        approved_intake=approved_intake,
        effective_from=effective_from,
        source=source.strip(),
    )
    session.add(version)
    approval.current_version = version.version
    approval.approved_intake = approved_intake
    await session.flush()
    added, removed = await seatpools.apply_resize(
        session, approval, changes, programme=programme, rules=rules
    )

    cohort = (
        await session.execute(
            select(Enrolment.id, Enrolment.seat_id)
            .where(
                Enrolment.programme_id == programme.id,
                Enrolment.cohort_year == approval.academic_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
            )
            .order_by(Enrolment.admission_date, Enrolment.uploaded_at, Enrolment.id)
        )
    ).all()
    backlog = [enrolment_id for enrolment_id, seat_id in cohort if seat_id is None]
    seated = await ledger.assign_seats(session, backlog, actor_id=user.id) if backlog else None
    # every Seat row of the cohort now cites the new version
    await checks.rerun(
        session, [e for e, _ in cohort], None, types=[CheckType.SEAT], actor_id=user.id
    )
    refs = [PoolRef(approval_id=approval.id, seat_type=t) for t in SeatType]
    tally = await flags.refresh_seat_flags(session, refs, actor_id=user.id)
    entries = [
        AuditEntry(
            action=AuditAction.CREATE,
            entity_type="approval_version",
            entity_id=version.id,
            actor_id=user.id,
            after={
                "approval_id": str(approval.id),
                "version": version.version,
                "approved_intake": approved_intake,
                "effective_from": effective_from.isoformat(),
                "source": version.source,
            },
        ),
        AuditEntry(
            action=AuditAction.UPDATE,
            entity_type="approval",
            entity_id=approval.id,
            actor_id=user.id,
            before=before,
            after={"current_version": version.version, "approved_intake": approved_intake},
        ),
    ]
    await audit.record_many(session, entries)
    settled = await status.settle(session)
    body = await _body(session, approval, programme, institution)
    body["effects"] = {
        "seats_added": added,
        "seats_removed": removed,
        "seated": len(seated.seated) if seated else 0,
        "flags_refreshed": tally.created + tally.updated,
        "records_changed": settled.changed,
    }
    return body
