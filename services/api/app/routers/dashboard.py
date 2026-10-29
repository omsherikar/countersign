"""GET /dashboard/summary (API_CONTRACT A.5, A2.19, §A4.20, D21, D46).

Records are counted by record status (D35); `countersigned_pct` is the COUNTERSIGNED share.
Completeness and deadline states come from the stored reconciliations. The officer-only keys
(`top_institutions`, `signals_new`) are empty or null for a college and a university; a college
gets its own completeness body instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select

from app.core.config import get_settings
from app.core.deps import RequestId, SessionDep, require_roles, scope_institutions
from app.engine import completeness as reconciliation
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.models.enums import FlagType, UserRole
from app.models.institution import Institution
from app.models.user import User
from app.models.verification import Flag
from app.routers._stats import (
    InstitutionStats,
    institution_ref,
    institution_stats_stmt,
    pct,
    region_label,
    stats_of,
)
from app.schemas.dashboard import (
    CasesByAge,
    DashboardScope,
    DashboardSummary,
    FlagTypeCount,
    Kpis,
    RecordsByStatus,
    RegionRow,
    StateRow,
    TopInstitution,
)
from app.signals import service as signals

router = APIRouter(tags=["dashboard"])

DASHBOARD_ROLES = (
    UserRole.AICTE_ADMIN,
    UserRole.RO_OFFICER,
    UserRole.INSTITUTION,
    UserRole.UNIVERSITY,
)
OFFICERS = (UserRole.AICTE_ADMIN, UserRole.RO_OFFICER)
# records_by_status order (API_CONTRACT §A4.20)
BY_STATUS_ORDER = ("COUNTERSIGNED", "AWAITING_EVIDENCE", "UNDER_REVIEW", "DISPUTED")
AGE_BUCKETS = ("UNDER_7_DAYS", "DAYS_7_TO_30", "OVER_30_DAYS")
TOP = 10


def _scope(user: User) -> DashboardScope:
    if user.role is UserRole.RO_OFFICER and user.region is not None:
        return DashboardScope(kind="REGION", label=f"{user.region.name} Region")
    if user.role is UserRole.INSTITUTION and user.institution is not None:
        return DashboardScope(kind="INSTITUTION", label=user.institution.name)
    if user.role is UserRole.UNIVERSITY and user.university is not None:
        return DashboardScope(kind="UNIVERSITY", label=user.university.name)
    return DashboardScope(kind="NATIONAL", label="All India")


@dataclass(slots=True)
class _Sums:
    """Running totals for one group of institutions; percentages come from the sums."""

    joined: int = 0
    uploaded_and_joined: int = 0

    def add(self, row: Kpis | StateRow | RegionRow, stats: InstitutionStats) -> None:
        row.institutions += 1
        if not isinstance(row, RegionRow):
            row.programmes += stats.programmes
        row.approved_seats += stats.approved_seats
        row.admitted += stats.admitted
        row.enrolments += stats.enrolments
        row.flags_open += stats.flags_open
        for status, n in stats.records.items():
            row.records[status] += n
        row.missing_from_upload += stats.missing
        self.joined += stats.joined
        self.uploaded_and_joined += stats.uploaded_and_joined

    def finish(self, row: StateRow | RegionRow) -> None:
        row.countersigned_pct = pct(row.records["COUNTERSIGNED"], row.enrolments)
        row.completeness_pct = pct(self.uploaded_and_joined, self.joined)


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


async def _cases_by_age(session, user: User, year: str) -> list[CasesByAge]:
    days = func.floor(func.extract("epoch", func.now() - Flag.opened_at) / 86400)
    bucket = case(
        (days < 7, "UNDER_7_DAYS"), (days <= 30, "DAYS_7_TO_30"), else_="OVER_30_DAYS"
    ).label("bucket")
    stmt = scope_institutions(
        select(bucket, func.count())
        .join(Institution, Institution.id == Flag.institution_id)
        .where(Flag.academic_year == year, Flag.status.in_(UNRESOLVED_FLAG_STATUSES))
        .group_by(bucket),
        user,
    )
    counts = dict((await session.execute(stmt)).all())
    return [CasesByAge(bucket=b, open=counts.get(b, 0)) for b in AGE_BUCKETS]


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(*DASHBOARD_ROLES))],
    request_id: RequestId,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> DashboardSummary:
    year = academic_year or get_settings().academic_year
    rows = [stats_of(r) for r in (await session.execute(institution_stats_stmt(user, year))).all()]
    officer = user.role in OFFICERS

    kpis = Kpis()
    totals = _Sums()
    by_state: dict[str, tuple[StateRow, _Sums]] = {}
    by_region: dict[str, tuple[RegionRow, _Sums]] = {}
    for stats in rows:
        totals.add(kpis, stats)
        if stats.deadline_state == "LATE":
            kpis.colleges_late += 1
        elif stats.deadline_state == "OVERDUE":
            kpis.colleges_overdue += 1
        srow, ssums = by_state.setdefault(
            stats.state.code,
            (
                StateRow(
                    state_code=stats.state.code,
                    state_name=stats.state.name,
                    region=stats.region.code,
                ),
                _Sums(),
            ),
        )
        ssums.add(srow, stats)
        rrow, rsums = by_region.setdefault(
            stats.region.code,
            (RegionRow(region=stats.region.code, region_name=region_label(stats.region)), _Sums()),
        )
        rsums.add(rrow, stats)
    kpis.countersigned_pct = pct(kpis.records["COUNTERSIGNED"], kpis.enrolments)
    kpis.joined = totals.joined
    kpis.completeness_pct = pct(totals.uploaded_and_joined, totals.joined)
    for row, sums in [*by_state.values(), *by_region.values()]:
        sums.finish(row)
    if officer:
        kpis.signals_new = await signals.new_count(session, user, year)

    top: list[TopInstitution] = []
    if officer:
        ranked = sorted(
            (s for s in rows if s.flags_open),
            key=lambda s: (-s.flags_open, s.institution.name),
        )[:TOP]
        top = [
            TopInstitution(
                institution=institution_ref(s),
                flags_open=s.flags_open,
                disputed=s.disputed,
                under_review=s.under_review,
            )
            for s in ranked
        ]

    completeness = None
    if user.role is UserRole.INSTITUTION and user.institution is not None:
        # the college's own completeness page body, its missing students included (audited)
        completeness = await reconciliation.read(
            session, user, user.institution, year, request_id=request_id
        )

    return DashboardSummary(
        academic_year=year,
        scope=_scope(user),
        kpis=kpis,
        records_by_status=[
            RecordsByStatus(
                status=status,
                count=kpis.records[status],
                pct=pct(kpis.records[status], kpis.enrolments),
            )
            for status in BY_STATUS_ORDER
        ],
        flags_by_type=await _flags_by_type(session, user, year),
        cases_by_age=await _cases_by_age(session, user, year),
        top_institutions=top,
        completeness=completeness,
        by_state=sorted((r for r, _ in by_state.values()), key=lambda r: r.state_name),
        by_region=sorted((r for r, _ in by_region.values()), key=lambda r: r.region_name),
    )
