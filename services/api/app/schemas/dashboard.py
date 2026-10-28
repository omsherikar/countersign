"""GET /dashboard/summary (API_CONTRACT A.5)."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardScope(BaseModel):
    kind: str  # NATIONAL | REGION | INSTITUTION | UNIVERSITY
    label: str


class Kpis(BaseModel):
    institutions: int
    programmes: int
    approved_seats: int
    admitted: int = 0
    enrolments: int
    flags_open: int = 0
    countersigned_pct: float | None = None
    clear_pct: float | None = None


class StateRow(BaseModel):
    state_code: str
    state_name: str
    region: str
    institutions: int
    programmes: int
    approved_seats: int
    admitted: int = 0
    enrolments: int
    flags_open: int = 0


class RegionRow(BaseModel):
    region: str
    region_name: str
    institutions: int
    approved_seats: int
    admitted: int = 0
    enrolments: int
    flags_open: int = 0


class FlagTypeCount(BaseModel):
    type: str
    open: int


class DashboardSummary(BaseModel):
    academic_year: str
    scope: DashboardScope
    kpis: Kpis
    flags_by_type: list[FlagTypeCount]
    by_state: list[StateRow]
    by_region: list[RegionRow]
