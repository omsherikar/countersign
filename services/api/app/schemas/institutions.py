"""Institution list, detail, seats and enrolments (API_CONTRACT A.6 to A.9 + addendum 1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# the enrolment rows and the rechecks are the record card's (API_CONTRACT §A4.5, §A4.6)
from app.schemas.enrolments import (  # noqa: F401
    EnrolmentRow,
    InstitutionRecheck,
    InstitutionRecheckBody,
    RelatedEnrolmentRow,
    StudentRef,
)


class InstitutionRow(BaseModel):
    id: str
    aicte_permanent_id: str
    name: str
    type: str
    state_code: str
    state_name: str
    region: str
    region_name: str
    university_id: str | None
    university_name: str | None
    programmes: int
    approved_seats: int
    admitted: int = 0
    enrolments: int
    flags_open: int = 0
    integrity_index: float | None = None


class ApprovalOut(BaseModel):
    academic_year: str
    approved_intake: int
    cutoff_date: str | None = None


class SeatPoolOut(BaseModel):
    seat_type: str
    capacity: int
    is_supernumerary: bool
    assigned: int
    free: int
    reserved_for: str | None
    rule_source: str


class ProgrammeDetail(BaseModel):
    id: str
    code: str
    name: str
    level: str
    discipline: str
    shift: str
    mode: str = "PHYSICAL"
    approval: ApprovalOut
    enrolments: int
    seated: int = 0
    unseated: int
    pools: list[SeatPoolOut]


class LastUpload(BaseModel):
    batch_id: str
    uploaded_at: str
    rows: int
    errors: int
    status: str


class InstitutionDetail(BaseModel):
    id: str
    aicte_permanent_id: str
    name: str
    type: str
    state_code: str
    state_name: str
    region: str
    region_name: str
    university_id: str | None
    university_name: str | None
    address_city: str | None
    established_year: int | None
    integrity_index: float | None = None
    integrity_components: dict[str, Any] | None = None
    # Same totals as the list row: approved intake for the year, every ACTIVE
    # enrolment in the current academic year (all years of study).
    approved_seats: int = 0
    admitted: int = 0
    enrolments: int = 0
    flags_open: int = 0
    last_upload: LastUpload | None = None
    programmes: list[ProgrammeDetail]


class SeatRow(BaseModel):
    id: str
    seat_code: str
    programme_code: str
    academic_year: str
    seat_type: str
    status: str
    reserved_for: str | None
    enrolment_id: str | None
    student_name: str | None
    assigned_at: str | None
