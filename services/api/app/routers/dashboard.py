"""GET /dashboard/summary (API_CONTRACT A.5, A2.19, D21)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import SessionDep, require_roles, scope_institutions
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.engine.score import countersign_state_sq
from app.models.enums import EnrolmentStatus, FlagType, UserRole
from app.models.institution import Institution
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import Flag
from app.routers._stats import institution_stats_stmt, region_label
from app.schemas.dashboard import (
    DashboardScope,
    DashboardSummary,
    FlagTypeCount,
    Kpis,
    RegionRow,
    StateRow,
)

router = APIRouter(tags=["dashboard"])

DASHBOARD_ROLES = (
    UserRole.AICTE_ADMIN,
    UserRole.RO_OFFICER,
    UserRole.INSTITUTION,
    UserRole.UNIVERSITY,
)


def _scope(user: User) -> DashboardScope:
    if user.role is UserRole.RO_OFFICER and user.region is not None:
        return DashboardScope(kind="REGION", label=f"{user.region.name} Region")
    if user.role is UserRole.INSTITUTION and user.institution is not None:
        return DashboardScope(kind="INSTITUTION", label=user.institution.name)
    if user.role is UserRole.UNIVERSITY and user.university is not None:
        return DashboardScope(kind="UNIVERSITY", label=user.university.name)
    return DashboardScope(kind="NATIONAL", label="All India")


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


async def _countersigned(session, user: User, year: str) -> tuple[float | None, float | None]:
    """Shares of in-scope ACTIVE enrolments of the year, among those with any check row."""
    state = countersign_state_sq()
    stmt = scope_institutions(
        select(
            func.count(),
            func.count().filter(state.c.countersigned),
            func.count().filter(state.c.clear),
        )
        .select_from(Enrolment)
        .join(state, state.c.enrolment_id == Enrolment.id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .where(Enrolment.academic_year == year, Enrolment.status == EnrolmentStatus.ACTIVE),
        user,
    )
    checked, countersigned, clear = (await session.execute(stmt)).one()
    return _pct(countersigned, checked), _pct(clear, checked)


async def _flags_by_type(session, user: User, year: str) -> list[FlagTypeCount]:
    stmt = scope_institutions(
        select(Flag.type, func.count())
        .join(Institution, Institution.id == Flag.institution_id)
        .where(Flag.academic_year == year, Flag.status.in_(UNRESOLVED_FLAG_STATUSES))
        .group_by(Flag.type),
        user,
    )
    counts = dict((await session.execute(stmt)).all())
    return [FlagTypeCount(type=t.value, open=counts.get(t, 0)) for t in FlagType]


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(*DASHBOARD_ROLES))],
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> DashboardSummary:
    year = academic_year or get_settings().academic_year
    rows = (await session.execute(institution_stats_stmt(user, year))).all()

    kpis = Kpis(institutions=0, programmes=0, approved_seats=0, admitted=0, enrolments=0)
    by_state: dict[str, StateRow] = {}
    by_region: dict[str, RegionRow] = {}
    for (
        _inst,
        state,
        region,
        _uni,
        programmes,
        approved_seats,
        enrolments,
        admitted,
        flags_open,
    ) in rows:
        kpis.institutions += 1
        kpis.programmes += programmes
        kpis.approved_seats += approved_seats
        kpis.admitted += admitted
        kpis.enrolments += enrolments
        kpis.flags_open += flags_open
        srow = by_state.setdefault(
            state.code,
            StateRow(
                state_code=state.code,
                state_name=state.name,
                region=region.code,
                institutions=0,
                programmes=0,
                approved_seats=0,
                enrolments=0,
            ),
        )
        srow.institutions += 1
        srow.programmes += programmes
        srow.approved_seats += approved_seats
        srow.admitted += admitted
        srow.enrolments += enrolments
        srow.flags_open += flags_open
        rrow = by_region.setdefault(
            region.code,
            RegionRow(
                region=region.code,
                region_name=region_label(region),
                institutions=0,
                approved_seats=0,
                enrolments=0,
            ),
        )
        rrow.institutions += 1
        rrow.approved_seats += approved_seats
        rrow.admitted += admitted
        rrow.enrolments += enrolments
        rrow.flags_open += flags_open

    kpis.countersigned_pct, kpis.clear_pct = await _countersigned(session, user, year)
    return DashboardSummary(
        academic_year=year,
        scope=_scope(user),
        kpis=kpis,
        flags_by_type=await _flags_by_type(session, user, year),
        by_state=sorted(by_state.values(), key=lambda r: r.state_name),
        by_region=sorted(by_region.values(), key=lambda r: r.region_name),
    )
