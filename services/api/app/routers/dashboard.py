"""GET /dashboard/summary (API_CONTRACT A.5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.core.deps import SessionDep, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.routers._stats import institution_stats_stmt, region_label
from app.schemas.dashboard import DashboardScope, DashboardSummary, Kpis, RegionRow, StateRow

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


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(*DASHBOARD_ROLES))],
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> DashboardSummary:
    year = academic_year or get_settings().academic_year
    rows = (await session.execute(institution_stats_stmt(user, year))).all()

    kpis = Kpis(institutions=0, programmes=0, approved_seats=0, enrolments=0)
    by_state: dict[str, StateRow] = {}
    by_region: dict[str, RegionRow] = {}
    for _inst, state, region, _uni, programmes, approved_seats, enrolments in rows:
        kpis.institutions += 1
        kpis.programmes += programmes
        kpis.approved_seats += approved_seats
        kpis.enrolments += enrolments
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
        srow.enrolments += enrolments
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
        rrow.enrolments += enrolments

    return DashboardSummary(
        academic_year=year,
        scope=_scope(user),
        kpis=kpis,
        by_state=sorted(by_state.values(), key=lambda r: r.state_name),
        by_region=sorted(by_region.values(), key=lambda r: r.region_name),
    )
