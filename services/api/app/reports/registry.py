"""The reports, their columns and formats, and the scope a caller reads them in."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models.enums import UserRole
from app.models.geo import Region, State
from app.models.user import User
from app.reports import queries

FORMATS = ("csv", "xlsx", "pdf")
STATE_UNKNOWN = "Choose a state from the list."
STATE_OUTSIDE = "Choose a state in your region."
REGION_UNKNOWN = "Choose a region from the list."


@dataclass(frozen=True, slots=True)
class ReportScope:
    kind: Literal["NATIONAL", "REGION", "STATE"]
    region_id: uuid.UUID | None
    state_id: uuid.UUID | None
    label: str  # "All India", "Western Region", "Maharashtra"
    slug: str  # "national", "WEST", "MH"


Rows = Callable[[AsyncSession, ReportScope, str], Awaitable[list[dict[str, Any]]]]


@dataclass(frozen=True, slots=True)
class ReportSpec:
    name: str
    title: str
    columns: tuple[str, ...]
    formats: tuple[str, ...]
    rows: Rows


async def _no_rows(session: AsyncSession, scope: ReportScope, academic_year: str) -> list:
    return []


# copy deck report.name.*; columns in API_CONTRACT §A4.21 order
REPORTS: Mapping[str, ReportSpec] = {
    spec.name: spec
    for spec in (
        ReportSpec("by-state", "Records by state", queries.BY_STATE, FORMATS, queries.by_state),
        ReportSpec(
            "by-institution-type",
            "Records by institution type",
            queries.BY_INSTITUTION_TYPE,
            FORMATS,
            queries.by_institution_type,
        ),
        ReportSpec(
            "cases-by-type-and-outcome",
            "Cases by type and outcome",
            queries.CASES_BY_TYPE,
            FORMATS,
            queries.cases_by_type_and_outcome,
        ),
        ReportSpec(
            "countersign-coverage",
            "Countersign coverage",
            queries.COVERAGE,
            FORMATS,
            queries.countersign_coverage,
        ),
        ReportSpec(
            "completeness",
            "Completeness and deadlines",
            queries.COMPLETENESS,
            FORMATS,
            queries.completeness,
        ),
        ReportSpec("summary", "One-page summary", (), ("pdf",), _no_rows),
    )
}


def find(name: str, fmt: str) -> ReportSpec | None:
    spec = REPORTS.get(name)
    if spec is None or fmt not in spec.formats:
        return None
    return spec


def _invalid(field_name: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field_name}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field_name, "message": message}]},
    )


async def scope_for(
    session: AsyncSession, user: User, *, region: str | None, state: str | None
) -> ReportScope:
    """AICTE: national, or one region or state when asked. A regional officer: its region, or
    one of its states; `region` is ignored."""
    regional = user.role is UserRole.RO_OFFICER
    if state:
        found = (
            await session.execute(select(State).where(State.code == state.strip().upper()))
        ).scalar_one_or_none()
        if found is None:
            raise _invalid("state", STATE_UNKNOWN)
        if regional and found.region_id != user.region_id:
            raise _invalid("state", STATE_OUTSIDE)
        return ReportScope("STATE", found.region_id, found.id, found.name, found.code)
    if regional:
        own = user.region
        assert own is not None
        return ReportScope("REGION", own.id, None, f"{own.name} Region", own.code)
    if region:
        found_region = (
            await session.execute(select(Region).where(Region.code == region.strip().upper()))
        ).scalar_one_or_none()
        if found_region is None:
            raise _invalid("region", REGION_UNKNOWN)
        return ReportScope(
            "REGION", found_region.id, None, f"{found_region.name} Region", found_region.code
        )
    return ReportScope("NATIONAL", None, None, "All India", "national")
