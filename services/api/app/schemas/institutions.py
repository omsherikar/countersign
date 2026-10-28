"""Institution list, detail, seats and enrolments (API_CONTRACT A.6 to A.9 + addendum 1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Countersign, FlagRef, IdName


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


class StudentRef(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    consent_status: str
    provisional_id: str | None
    nationality: str


class EnrolmentRow(BaseModel):
    id: str
    student: StudentRef
    programme_id: str
    programme_code: str
    academic_year: str
    cohort_year: str
    year_of_study: int
    admission_route: str
    counselling_ref: str | None
    category: str
    seat_code: str | None
    status: str
    admission_date: str
    status_date: str
    uploaded_at: str
    upload_batch_id: str | None = None
    source_row_no: int | None = None
    countersign: Countersign = Field(default_factory=Countersign)
    flags: list[FlagRef] = Field(default_factory=list)
    # the record status (D35) and the sentence that explains it
    record_status: str = "AWAITING_EVIDENCE"
    status_reason: str | None = None


class RelatedEnrolmentRow(EnrolmentRow):
    """An EnrolmentRow with its institution, as flag detail lists it."""

    institution: IdName


class InstitutionRecheckBody(BaseModel):
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class InstitutionRecheck(BaseModel):
    institution_id: str
    academic_year: str
    enrolments: int
    rechecked: int
    now_pass: int
    now_fail: int
    now_na: int
    still_pending: int
    flags_raised: int
    duration_ms: int
