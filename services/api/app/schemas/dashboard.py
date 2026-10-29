"""GET /dashboard/summary (API_CONTRACT A.5, A2.19, §A4.20)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import InstitutionRef


class DashboardScope(BaseModel):
    kind: str  # NATIONAL | REGION | INSTITUTION | UNIVERSITY
    label: str


def _no_records() -> dict[str, int]:
    return {"AWAITING_EVIDENCE": 0, "COUNTERSIGNED": 0, "UNDER_REVIEW": 0, "DISPUTED": 0}


class Kpis(BaseModel):
    institutions: int = 0
    programmes: int = 0
    approved_seats: int = 0
    admitted: int = 0
    enrolments: int = 0
    flags_open: int = 0
    # the COUNTERSIGNED share of in-scope ACTIVE records of the year
    countersigned_pct: float | None = None
    records: dict[str, int] = Field(default_factory=_no_records)
    joined: int = 0
    missing_from_upload: int = 0
    completeness_pct: float | None = None
    colleges_late: int = 0
    colleges_overdue: int = 0
    # officers only; null for other roles
    signals_new: int | None = None


class RecordsByStatus(BaseModel):
    status: str
    count: int
    pct: float | None


class StateRow(BaseModel):
    state_code: str
    state_name: str
    region: str
    institutions: int = 0
    programmes: int = 0
    approved_seats: int = 0
    admitted: int = 0
    enrolments: int = 0
    flags_open: int = 0
    records: dict[str, int] = Field(default_factory=_no_records)
    countersigned_pct: float | None = None
    completeness_pct: float | None = None
    missing_from_upload: int = 0


class RegionRow(BaseModel):
    region: str
    region_name: str
    institutions: int = 0
    approved_seats: int = 0
    admitted: int = 0
    enrolments: int = 0
    flags_open: int = 0
    records: dict[str, int] = Field(default_factory=_no_records)
    countersigned_pct: float | None = None
    completeness_pct: float | None = None
    missing_from_upload: int = 0


class FlagTypeCount(BaseModel):
    type: str
    open: int


class CasesByAge(BaseModel):
    bucket: str  # UNDER_7_DAYS | DAYS_7_TO_30 | OVER_30_DAYS
    open: int


class TopInstitution(BaseModel):
    institution: InstitutionRef
    flags_open: int
    disputed: int
    under_review: int


class DashboardSummary(BaseModel):
    academic_year: str
    scope: DashboardScope
    kpis: Kpis
    records_by_status: list[RecordsByStatus]
    flags_by_type: list[FlagTypeCount]
    cases_by_age: list[CasesByAge]
    top_institutions: list[TopInstitution]
    # an INSTITUTION caller's own §A4.18 body without `institution`; null for other roles
    completeness: dict[str, Any] | None = None
    by_state: list[StateRow]
    by_region: list[RegionRow]
