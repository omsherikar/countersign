"""GET /enrolments/{id} and the recheck endpoints (API_CONTRACT A2.11 to A2.13)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.common import CheckOut, Countersign, FlagSummary, InstitutionRef, ProgrammeRef
from app.schemas.institutions import StudentRef
from app.schemas.notices import EnrolmentNotice, ResendState


class StudentDetail(StudentRef):
    dob: str
    gender: str
    mobile_masked: str | None


class ProgrammeDetailRef(ProgrammeRef):
    level: str
    mode: str
    duration_years: int


class UploadRef(BaseModel):
    batch_id: str
    filename: str
    row_no: int | None


class SeatRef(BaseModel):
    id: str
    seat_code: str
    seat_type: str
    academic_year: str
    assigned_at: str | None


class EnrolmentDetail(BaseModel):
    id: str
    institution: InstitutionRef
    student: StudentDetail
    programme: ProgrammeDetailRef
    academic_year: str
    cohort_year: str
    year_of_study: int
    admission_route: str
    counselling_ref: str | None
    category: str
    status: str
    status_date: str
    admission_date: str
    uploaded_at: str
    upload: UploadRef | None
    seat: SeatRef | None
    countersign: Countersign
    checks: list[CheckOut]
    flags: list[FlagSummary]
    notices: list[EnrolmentNotice]
    resend: ResendState
    # CredentialRef (API_CONTRACT §A3.7), shaped by credentials.holder
    credentials: list[dict[str, Any]]


class CheckTransition(BaseModel):
    type: str
    before: str
    after: str


class EnrolmentRecheck(BaseModel):
    enrolment_id: str
    rechecked: int
    results: list[CheckTransition]
    flags_raised: int
    countersign: Countersign
