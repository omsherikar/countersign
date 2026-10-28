"""Flags: raised only by engines, deduplicated, never deleted (docs/ENGINES.md section 10, D20).

`raise_flag` is an upsert by `dedupe_key`. A new flag opens OPEN; an existing one gets the
new evidence, the union of related enrolments and the higher severity, and keeps its
status, assignee and opening time. `refresh_seat_flags` recomputes EXCESS_ADMISSION and
QUOTA_BREACH from the ledger once per batch, with the final numbers.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.rules import Rules, get_rules
from app.engine import evidence as ev
from app.engine.contracts import FlagIntent, FlagTally, PoolRef, RaisedFlag
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    SeatStatus,
    SeatType,
    Severity,
)
from app.models.institution import Approval, Programme
from app.models.seat import Seat, SeatPool
from app.models.student import Enrolment
from app.models.verification import Flag

SEVERITY_RANK = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}


def dedupe_key(type: FlagType, *parts: object) -> str:
    """`<TYPE>:<part>:<part>...`; UUIDs print in canonical lower case."""
    return ":".join([type.value, *map(str, parts)])


def seat_flag_key(programme_id: uuid.UUID, cohort_year: str, seat_type: SeatType) -> str:
    """The EXCESS_ADMISSION (REGULAR pool) or QUOTA_BREACH key of one cohort pool."""
    if seat_type is SeatType.REGULAR:
        return dedupe_key(FlagType.EXCESS_ADMISSION, programme_id, cohort_year, SeatType.REGULAR)
    return dedupe_key(FlagType.QUOTA_BREACH, programme_id, cohort_year, seat_type.value)


def pair_key(type: FlagType, a: uuid.UUID, b: uuid.UUID, *rest: object) -> str:
    low, high = sorted([str(a), str(b)])
    return dedupe_key(type, low, high, *rest)


def validate_evidence(evidence: dict[str, Any]) -> None:
    """The D20 evidence schema; raises ValueError when it is not met."""
    summary = evidence.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("evidence needs a non-empty summary")
    facts = evidence.get("facts")
    if not isinstance(facts, list) or not all(
        isinstance(f, dict) and {"label", "value", "source"} <= f.keys() for f in facts
    ):
        raise ValueError("evidence facts must be a list of {label, value, source}")
    if not isinstance(evidence.get("related_enrolment_ids"), list):
        raise ValueError("evidence related_enrolment_ids must be a list")


def _uuid_list(values: Iterable[Any]) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    for value in values:
        item = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        if item not in out:
            out.append(item)
    return out


def _audit_after(flag: Flag) -> dict[str, Any]:
    return {
        "type": flag.type.value,
        "severity": flag.severity.value,
        "status": flag.status.value,
        "dedupe_key": flag.dedupe_key,
        "summary": flag.evidence.get("summary"),
    }


async def raise_flag(
    session: AsyncSession,
    *,
    type: FlagType,
    severity: Severity,
    institution_id: uuid.UUID,
    programme_id: uuid.UUID | None,
    enrolment_id: uuid.UUID | None,
    academic_year: str,
    dedupe_key: str,
    evidence: dict[str, Any],
    actor_id: uuid.UUID | None,
    replace_related: bool = False,
    audit_sink: list[AuditEntry] | None = None,
) -> RaisedFlag:
    """Upsert one flag. With `audit_sink` the audit entry is appended there for the caller
    to write in one `record_many`; without it the entry is written at once."""
    validate_evidence(evidence)
    related = _uuid_list(evidence["related_enrolment_ids"])
    stored = {**evidence, "related_enrolment_ids": [str(i) for i in related]}
    inserted = (
        await session.execute(
            pg_insert(Flag)
            .values(
                id=uuid.uuid4(),
                type=type,
                severity=severity,
                status=FlagStatus.OPEN,
                institution_id=institution_id,
                programme_id=programme_id,
                enrolment_id=enrolment_id,
                academic_year=academic_year,
                related_enrolment_ids=related,
                evidence=stored,
                dedupe_key=dedupe_key,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(Flag.id)
        )
    ).scalar_one_or_none()
    flag = (
        await session.execute(
            select(Flag)
            .where(Flag.dedupe_key == dedupe_key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()

    entries: list[AuditEntry] = []
    created = inserted is not None
    changed = False
    if created:
        entries.append(
            AuditEntry(
                action=AuditAction.CREATE,
                entity_type="flag",
                entity_id=flag.id,
                actor_id=actor_id,
                after=_audit_after(flag),
            )
        )
    else:
        old_related = list(flag.related_enrolment_ids or [])
        new_related = related if replace_related else _uuid_list([*old_related, *related])
        new_evidence = {**stored, "related_enrolment_ids": [str(i) for i in new_related]}
        new_severity = max(flag.severity, severity, key=SEVERITY_RANK.__getitem__)
        before = {"severity": flag.severity.value, "summary": flag.evidence.get("summary")}
        if new_evidence != flag.evidence:
            flag.evidence = new_evidence
            changed = True
        if new_related != old_related:
            flag.related_enrolment_ids = new_related
            changed = True
        if new_severity is not flag.severity:
            flag.severity = new_severity
            changed = True
        for column, value in (
            ("programme_id", programme_id),
            ("enrolment_id", enrolment_id),
            ("academic_year", academic_year),
        ):
            if getattr(flag, column) is None and value is not None:
                setattr(flag, column, value)
                changed = True
        if changed:
            await session.flush()
            entries.append(
                AuditEntry(
                    action=AuditAction.UPDATE,
                    entity_type="flag",
                    entity_id=flag.id,
                    actor_id=actor_id,
                    before=before,
                    after=_audit_after(flag),
                )
            )
    if audit_sink is not None:
        audit_sink.extend(entries)
    elif entries:
        await audit.record_many(session, entries)
    return RaisedFlag(flag=flag, created=created, changed=changed)


async def raise_intents(
    session: AsyncSession,
    intents: Iterable[FlagIntent],
    *,
    actor_id: uuid.UUID | None,
    audit_sink: list[AuditEntry],
) -> FlagTally:
    tally = FlagTally()
    for intent in intents:
        raised = await raise_flag(
            session,
            type=intent.type,
            severity=intent.severity,
            institution_id=intent.institution_id,
            programme_id=intent.programme_id,
            enrolment_id=intent.enrolment_id,
            academic_year=intent.academic_year,
            dedupe_key=intent.dedupe_key,
            evidence=intent.evidence,
            actor_id=actor_id,
            audit_sink=audit_sink,
        )
        tally.count(raised)
    return tally


# ------------------------------------------------------------------ seat flags


def routes_for(seat_type: SeatType, rules: Rules | None = None) -> list[AdmissionRoute]:
    rules = rules or get_rules()
    return [r for r in AdmissionRoute if rules.admission_routes[r.value].pool == seat_type.value]


def pool_share(seat_type: SeatType, programme: Programme, rules: Rules) -> float | None:
    pools = rules.seat_pools
    if seat_type is SeatType.NRI:
        return pools.NRI.share
    if seat_type is SeatType.TFW:
        return pools.TFW.share
    if seat_type is SeatType.LATERAL:
        return pools.LATERAL.share
    if seat_type is SeatType.INTERNATIONAL:
        slab = pools.INTERNATIONAL.slab_for(programme.discipline.value, programme.level.value)
        return slab.share if slab else None
    return None


@dataclass(slots=True)
class _PoolView:
    admitted: int = 0
    unseated_ids: list[uuid.UUID] | None = None
    seated: int = 0


async def _peak(session: AsyncSession, key: str, unseated: int) -> int:
    data = (
        await session.execute(select(Flag.evidence["data"]).where(Flag.dedupe_key == key))
    ).scalar_one_or_none()
    previous = int(data.get("peak_unseated", 0)) if isinstance(data, dict) else 0
    return max(previous, unseated)


async def _flag_exists(session: AsyncSession, key: str) -> bool:
    found = await session.execute(select(Flag.id).where(Flag.dedupe_key == key))
    return found.scalar_one_or_none() is not None


async def refresh_seat_flags(
    session: AsyncSession, pools: Sequence[PoolRef], *, actor_id: uuid.UUID | None = None
) -> FlagTally:
    """Raise or refresh EXCESS_ADMISSION and QUOTA_BREACH for the pools a batch touched."""
    rules = get_rules()
    tally = FlagTally()
    sink: list[AuditEntry] = []
    by_approval: dict[uuid.UUID, set[SeatType]] = {}
    for ref in pools:
        by_approval.setdefault(ref.approval_id, set()).add(SeatType(ref.seat_type))
    for approval_id in sorted(by_approval, key=str):
        approval = await session.get(Approval, approval_id)
        if approval is None:
            continue
        programme = await session.get(Programme, approval.programme_id)
        assert programme is not None
        pool_rows = (
            (await session.execute(select(SeatPool).where(SeatPool.approval_id == approval.id)))
            .scalars()
            .all()
        )
        pool_by_type = {p.seat_type: p for p in pool_rows}
        views = await _pool_views(session, approval, programme, pool_by_type)
        year = await _roll_year(session, approval, programme)

        # EXCESS_ADMISSION: the intake (REGULAR and NRI pools) against approved_intake.
        key = seat_flag_key(programme.id, approval.academic_year, SeatType.REGULAR)
        regular = views[SeatType.REGULAR]
        if (regular.unseated_ids or []) or await _flag_exists(session, key):
            nri = views[SeatType.NRI]
            admitted = regular.admitted + nri.admitted
            seated = regular.seated + nri.seated
            related = [*(regular.unseated_ids or []), *(nri.unseated_ids or [])]
            evidence = ev.excess_admission(
                programme_code=programme.code,
                cohort_year=approval.academic_year,
                approved=approval.approved_intake,
                admitted=admitted,
                seated=seated,
                peak_unseated=await _peak(session, key, admitted - seated),
                rule_source=pool_by_type[SeatType.REGULAR].rule_source
                if SeatType.REGULAR in pool_by_type
                else "AICTE approved intake",
                related=related,
            )
            tally.count(
                await raise_flag(
                    session,
                    type=FlagType.EXCESS_ADMISSION,
                    severity=Severity.HIGH,
                    institution_id=programme.institution_id,
                    programme_id=programme.id,
                    enrolment_id=None,
                    academic_year=year,
                    dedupe_key=key,
                    evidence=evidence,
                    actor_id=actor_id,
                    replace_related=True,
                    audit_sink=sink,
                )
            )

        # QUOTA_BREACH: each touched pool outside the intake, against its own capacity.
        for seat_type in sorted(by_approval[approval_id] - {SeatType.REGULAR}):
            pool = pool_by_type.get(seat_type)
            view = views[seat_type]
            unseated_ids = view.unseated_ids or []
            key = seat_flag_key(programme.id, approval.academic_year, seat_type)
            if not unseated_ids and not await _flag_exists(session, key):
                continue
            unseated = len(unseated_ids)
            severity = (
                Severity.HIGH
                if seat_type in (SeatType.INTERNATIONAL, SeatType.NRI) and unseated > 2
                else Severity.MEDIUM
            )
            evidence = ev.quota_breach(
                seat_type=seat_type,
                programme_code=programme.code,
                cohort_year=approval.academic_year,
                capacity=pool.capacity if pool else 0,
                admitted=view.admitted,
                seated=view.seated,
                unseated=unseated,
                peak_unseated=await _peak(session, key, unseated),
                routes=routes_for(seat_type, rules),
                share=pool_share(seat_type, programme, rules),
                approved=approval.approved_intake,
                rule_source=pool.rule_source if pool else f"No {seat_type.value} pool",
                related=unseated_ids,
            )
            tally.count(
                await raise_flag(
                    session,
                    type=FlagType.QUOTA_BREACH,
                    severity=severity,
                    institution_id=programme.institution_id,
                    programme_id=programme.id,
                    enrolment_id=None,
                    academic_year=year,
                    dedupe_key=key,
                    evidence=evidence,
                    actor_id=actor_id,
                    replace_related=True,
                    audit_sink=sink,
                )
            )
    await audit.record_many(session, sink)
    return tally


async def _pool_views(
    session: AsyncSession,
    approval: Approval,
    programme: Programme,
    pool_by_type: dict[SeatType, SeatPool],
) -> dict[SeatType, _PoolView]:
    """Admitted, seated and the unseated enrolments, per seat type of one cohort approval."""
    rules = get_rules()
    route_pool = {r: SeatType(rules.admission_routes[r.value].pool) for r in AdmissionRoute}
    views = {t: _PoolView(unseated_ids=[]) for t in SeatType}
    rows = (
        await session.execute(
            select(Enrolment.id, Enrolment.admission_route, Enrolment.seat_id)
            .where(
                Enrolment.programme_id == programme.id,
                Enrolment.cohort_year == approval.academic_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
            )
            .order_by(
                Enrolment.admission_date,
                Enrolment.uploaded_at,
                Enrolment.source_row_no.nulls_last(),
                Enrolment.id,
            )
        )
    ).all()
    for enrolment_id, route, seat_id in rows:
        view = views[route_pool[route]]
        view.admitted += 1
        if seat_id is None:
            assert view.unseated_ids is not None
            view.unseated_ids.append(enrolment_id)
    pool_ids = {p.id: t for t, p in pool_by_type.items()}
    if pool_ids:
        counts = await session.execute(
            select(Seat.pool_id, func.count())
            .where(Seat.pool_id.in_(pool_ids), Seat.status == SeatStatus.ASSIGNED)
            .group_by(Seat.pool_id)
        )
        for pool_id, n in counts.all():
            views[pool_ids[pool_id]].seated = n
    return views


async def _roll_year(session: AsyncSession, approval: Approval, programme: Programme) -> str:
    """The roll year of the cohort's ACTIVE enrolments (the upload's academic year)."""
    year = (
        await session.execute(
            select(func.max(Enrolment.academic_year)).where(
                Enrolment.programme_id == programme.id,
                Enrolment.cohort_year == approval.academic_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    return year or get_settings().academic_year
