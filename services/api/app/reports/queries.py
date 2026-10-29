"""Report rows: SQL aggregates over the per-institution figures the dashboard reads.

Each function takes the session, the scope and the academic year and returns the rows in the
report's order, one dict per row keyed by the report's columns. Percentages are recomputed
from the summed counts (one decimal); dates are `YYYY-MM-DD`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.service import FLAG_NAMES
from app.engine.upload.types import INDIA
from app.models.enums import (
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    SignalStatus,
)
from app.models.geo import Region, State
from app.models.institution import Institution
from app.models.signal import Signal
from app.models.student import Enrolment
from app.models.verification import Check, Flag
from app.routers._stats import deadline_for, figures_sq, pct

if TYPE_CHECKING:
    from app.reports.registry import ReportScope

BY_STATE = (
    "academic_year", "state_code", "state_name", "region", "institutions", "approved_seats",
    "admitted", "records", "countersigned", "awaiting_evidence", "under_review", "disputed",
    "countersigned_pct", "cases_open", "joined", "missing_from_upload", "completeness_pct",
)  # fmt: skip
BY_INSTITUTION_TYPE = (
    "academic_year", "institution_type", "institutions", "approved_seats", "admitted",
    "records", "countersigned", "awaiting_evidence", "under_review", "disputed",
    "countersigned_pct", "cases_open", "completeness_pct",
)  # fmt: skip
CASES_BY_TYPE = (
    "academic_year", "case_type", "case_name", "open", "docs_requested", "escalated",
    "upheld", "corrected", "withdrawn", "total", "median_days_to_decision",
)  # fmt: skip
COVERAGE = (
    "academic_year", "aicte_permanent_id", "institution_name", "state_code",
    "institution_type", "records", "countersigned", "awaiting_evidence", "under_review",
    "disputed", "countersigned_pct", "independent_joining_record", "independent_credits",
    "independent_student",
)  # fmt: skip
COMPLETENESS = (
    "academic_year", "aicte_permanent_id", "institution_name", "state_code", "joined",
    "uploaded_and_joined", "missing", "uploaded_not_joined", "completeness_pct", "deadline",
    "first_upload_on", "deadline_state", "case_status",
)  # fmt: skip
DECIDED = (FlagStatus.UPHELD, FlagStatus.CORRECTED, FlagStatus.WITHDRAWN)
UNRESOLVED = (FlagStatus.OPEN, FlagStatus.DOCS_REQUESTED, FlagStatus.ESCALATED)


def in_scope(stmt: Select, scope: ReportScope) -> Select:
    """Restrict a statement joined to `institutions` to the report's scope."""
    if scope.state_id is not None:
        return stmt.where(Institution.state_id == scope.state_id)
    if scope.region_id is not None:
        return stmt.where(Institution.region_id == scope.region_id)
    return stmt


def _figures(academic_year: str):
    return figures_sq(academic_year)


def _sum(column):
    return func.coalesce(func.sum(column), 0)


def _status_sums(fig) -> list:
    return [
        func.count(Institution.id).label("institutions"),
        _sum(fig.c.approved_seats).label("approved_seats"),
        _sum(fig.c.admitted).label("admitted"),
        _sum(fig.c.enrolments).label("records"),
        _sum(fig.c.countersigned).label("countersigned"),
        _sum(fig.c.awaiting_evidence).label("awaiting_evidence"),
        _sum(fig.c.under_review).label("under_review"),
        _sum(fig.c.disputed).label("disputed"),
        _sum(fig.c.flags_open).label("cases_open"),
        _sum(fig.c.joined).label("joined"),
        _sum(fig.c.uploaded_and_joined).label("uploaded_and_joined"),
        _sum(fig.c.missing).label("missing_from_upload"),
    ]


def _with_shares(row: dict[str, Any]) -> dict[str, Any]:
    row = {k: int(v) if isinstance(v, Decimal) else v for k, v in row.items()}
    row["countersigned_pct"] = pct(row["countersigned"], row["records"])
    row["completeness_pct"] = pct(row.pop("uploaded_and_joined"), row["joined"])
    return row


async def by_state(session: AsyncSession, scope: ReportScope, academic_year: str) -> list[dict]:
    fig = _figures(academic_year)
    stmt = in_scope(
        select(
            State.code.label("state_code"),
            State.name.label("state_name"),
            Region.code.label("region"),
            *_status_sums(fig),
        )
        .select_from(Institution)
        .join(fig, fig.c.institution_id == Institution.id)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .group_by(State.code, State.name, Region.code)
        .order_by(State.name),
        scope,
    )
    rows = [_with_shares(dict(r._mapping)) for r in (await session.execute(stmt)).all()]
    return [{"academic_year": academic_year, **{c: r.get(c) for c in BY_STATE[1:]}} for r in rows]


async def by_institution_type(
    session: AsyncSession, scope: ReportScope, academic_year: str
) -> list[dict]:
    fig = _figures(academic_year)
    stmt = in_scope(
        select(Institution.type.label("institution_type"), *_status_sums(fig))
        .select_from(Institution)
        .join(fig, fig.c.institution_id == Institution.id)
        .group_by(Institution.type),
        scope,
    )
    rows = [_with_shares(dict(r._mapping)) for r in (await session.execute(stmt)).all()]
    for row in rows:
        row["institution_type"] = row["institution_type"].value
    rows.sort(key=lambda r: r["institution_type"])
    return [
        {"academic_year": academic_year, **{c: r.get(c) for c in BY_INSTITUTION_TYPE[1:]}}
        for r in rows
    ]


async def cases_by_type_and_outcome(
    session: AsyncSession, scope: ReportScope, academic_year: str
) -> list[dict]:
    days = func.extract("epoch", Flag.resolved_at - Flag.opened_at) / 86400
    counts = [func.count().filter(Flag.status == s).label(s.value.lower()) for s in FlagStatus]
    stmt = in_scope(
        select(
            Flag.type,
            *counts,
            func.count().label("total"),
            func.percentile_cont(0.5)
            .within_group(days)
            .filter(Flag.status.in_(DECIDED), Flag.resolved_at.is_not(None))
            .label("median_days"),
        )
        .join(Institution, Institution.id == Flag.institution_id)
        .where(Flag.academic_year == academic_year)
        .group_by(Flag.type),
        scope,
    )
    found = {r.type: r for r in (await session.execute(stmt)).all()}
    out = []
    for flag_type in sorted(FlagType, key=lambda t: t.value):
        r = found.get(flag_type)
        median = None if r is None or r.median_days is None else round(float(r.median_days), 1)
        out.append(
            {
                "academic_year": academic_year,
                "case_type": flag_type.value,
                "case_name": FLAG_NAMES.get(flag_type, flag_type.value),
                "open": r.open if r else 0,
                "docs_requested": r.docs_requested if r else 0,
                "escalated": r.escalated if r else 0,
                "upheld": r.upheld if r else 0,
                "corrected": r.corrected if r else 0,
                "withdrawn": r.withdrawn if r else 0,
                "total": r.total if r else 0,
                "median_days_to_decision": median,
            }
        )
    return out


def _independent_sq(academic_year: str):
    """ACTIVE records of the year with each enrolment row CONFIRMED by an independent source."""
    return (
        select(
            Enrolment.institution_id.label("institution_id"),
            func.count().filter(Check.type == CheckType.ADMISSION).label("joining"),
            func.count().filter(Check.type == CheckType.STUDYING).label("credits"),
            func.count().filter(Check.type == CheckType.STUDENT).label("student"),
        )
        .join(Check, Check.enrolment_id == Enrolment.id)
        .where(
            Enrolment.academic_year == academic_year,
            Enrolment.status == EnrolmentStatus.ACTIVE,
            Check.status == CheckStatus.CONFIRMED,
            Check.independent.is_(True),
        )
        .group_by(Enrolment.institution_id)
        .subquery("ind")
    )


async def countersign_coverage(
    session: AsyncSession, scope: ReportScope, academic_year: str
) -> list[dict]:
    fig = _figures(academic_year)
    ind = _independent_sq(academic_year)
    stmt = in_scope(
        select(
            Institution.aicte_permanent_id,
            Institution.name,
            State.code,
            Institution.type,
            fig.c.enrolments,
            fig.c.countersigned,
            fig.c.awaiting_evidence,
            fig.c.under_review,
            fig.c.disputed,
            func.coalesce(ind.c.joining, 0),
            func.coalesce(ind.c.credits, 0),
            func.coalesce(ind.c.student, 0),
        )
        .join(fig, fig.c.institution_id == Institution.id)
        .join(State, State.id == Institution.state_id)
        .outerjoin(ind, ind.c.institution_id == Institution.id)
        .order_by(Institution.name, Institution.aicte_permanent_id),
        scope,
    )
    out = []
    for aid, name, state, kind, records, cs, awaiting, review, disputed, j, c, s in (
        await session.execute(stmt)
    ).all():
        out.append(
            {
                "academic_year": academic_year,
                "aicte_permanent_id": aid,
                "institution_name": name,
                "state_code": state,
                "institution_type": kind.value,
                "records": records,
                "countersigned": cs,
                "awaiting_evidence": awaiting,
                "under_review": review,
                "disputed": disputed,
                "countersigned_pct": pct(cs, records),
                "independent_joining_record": j,
                "independent_credits": c,
                "independent_student": s,
            }
        )
    return out


async def completeness(session: AsyncSession, scope: ReportScope, academic_year: str) -> list[dict]:
    fig = _figures(academic_year)
    case_flag = (
        select(Flag.institution_id.label("institution_id"), Flag.status.label("status"))
        .where(Flag.type == FlagType.MISSING_FROM_UPLOAD, Flag.academic_year == academic_year)
        .subquery("mfu")
    )
    stmt = in_scope(
        select(
            Institution.aicte_permanent_id,
            Institution.name,
            State.code,
            fig.c.joined,
            fig.c.uploaded_and_joined,
            fig.c.missing,
            fig.c.uploaded_not_joined,
            fig.c.completeness_pct,
            fig.c.first_upload_at,
            fig.c.deadline_state,
            case_flag.c.status,
        )
        .join(fig, fig.c.institution_id == Institution.id)
        .join(State, State.id == Institution.state_id)
        .outerjoin(case_flag, case_flag.c.institution_id == Institution.id)
        .order_by(fig.c.completeness_pct.asc().nulls_last(), Institution.name),
        scope,
    )
    deadline = deadline_for(academic_year).isoformat()
    out = []
    for aid, name, state, joined, matched, missing, not_joined, pct_value, first, dstate, case in (
        await session.execute(stmt)
    ).all():
        out.append(
            {
                "academic_year": academic_year,
                "aicte_permanent_id": aid,
                "institution_name": name,
                "state_code": state,
                "joined": joined,
                "uploaded_and_joined": matched,
                "missing": missing,
                "uploaded_not_joined": not_joined,
                "completeness_pct": None if pct_value is None else round(float(pct_value), 1),
                "deadline": deadline,
                "first_upload_on": first.astimezone(INDIA).date().isoformat() if first else None,
                "deadline_state": dstate,
                "case_status": case.value if case else None,
            }
        )
    return out


async def summary(session: AsyncSession, scope: ReportScope, academic_year: str) -> dict:
    """The one-page summary: KPIs, records by status, open cases by type, the ten colleges
    with most unresolved cases, and the late and overdue colleges."""
    fig = _figures(academic_year)
    base = (
        select(
            Institution.name,
            Institution.aicte_permanent_id,
            *[fig.c[c] for c in fig.c.keys() if c != "institution_id"],
        )
        .join(fig, fig.c.institution_id == Institution.id)
        .order_by(Institution.name)
    )
    rows = [dict(r._mapping) for r in (await session.execute(in_scope(base, scope))).all()]

    def total(key: str) -> int:
        return sum(int(r[key]) for r in rows)

    records = {
        "COUNTERSIGNED": total("countersigned"),
        "AWAITING_EVIDENCE": total("awaiting_evidence"),
        "UNDER_REVIEW": total("under_review"),
        "DISPUTED": total("disputed"),
    }
    enrolments = total("enrolments")
    open_by_type = dict(
        (
            await session.execute(
                in_scope(
                    select(Flag.type, func.count())
                    .join(Institution, Institution.id == Flag.institution_id)
                    .where(Flag.academic_year == academic_year, Flag.status.in_(UNRESOLVED))
                    .group_by(Flag.type),
                    scope,
                )
            )
        ).all()
    )
    signals_new = (
        await session.execute(
            select(func.count())
            .select_from(Signal)
            .where(
                Signal.academic_year == academic_year,
                Signal.status == SignalStatus.NEW,
                Signal.institution_ids.op("&&")(
                    func.array(in_scope(select(Institution.id), scope).scalar_subquery())
                ),
            )
        )
    ).scalar_one()
    top = sorted((r for r in rows if r["flags_open"]), key=lambda r: (-r["flags_open"], r["name"]))
    return {
        "kpis": {
            "institutions": len(rows),
            "approved_seats": total("approved_seats"),
            "admitted": total("admitted"),
            "records": enrolments,
            "countersigned_pct": pct(records["COUNTERSIGNED"], enrolments),
            "cases_open": total("flags_open"),
            "joined": total("joined"),
            "missing_from_upload": total("missing"),
            "completeness_pct": pct(total("uploaded_and_joined"), total("joined")),
            "colleges_late": sum(1 for r in rows if r["deadline_state"] == "LATE"),
            "colleges_overdue": sum(1 for r in rows if r["deadline_state"] == "OVERDUE"),
            "signals_new": signals_new,
        },
        "records_by_status": [
            {"status": s, "count": n, "pct": pct(n, enrolments)} for s, n in records.items()
        ],
        "cases_by_type": [
            {"case_type": t.value, "case_name": FLAG_NAMES.get(t, t.value), "open": open_by_type[t]}
            for t in FlagType
            if open_by_type.get(t)
        ],
        "top_institutions": [
            {
                "institution_name": r["name"],
                "aicte_permanent_id": r["aicte_permanent_id"],
                "cases_open": r["flags_open"],
                "under_review": r["under_review"],
                "disputed": r["disputed"],
            }
            for r in top[:10]
        ],
        "late_and_overdue": [
            {
                "institution_name": r["name"],
                "aicte_permanent_id": r["aicte_permanent_id"],
                "deadline_state": r["deadline_state"],
            }
            for r in rows
            if r["deadline_state"] in ("LATE", "OVERDUE")
        ],
        "deadline": deadline_for(academic_year).isoformat(),
    }
