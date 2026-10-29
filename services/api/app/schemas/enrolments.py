"""Enrolment rows, the record card and the rechecks (API_CONTRACT §A4.2, §A4.5 to §A4.7).

A record has five evidence rows in the deck's order and one record status; there is no
score. Lists carry the brief rows, the detail the full ones.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import FlagRef, FlagSummary, IdName, InstitutionRef, Page, ProgrammeRef
from app.schemas.notices import EnrolmentNotice, ResendState


class StudentRef(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    consent_status: str
    provisional_id: str | None
    nationality: str


class Eligibility(BaseModel):
    """What the college reported for the category markers (D41); None is not reported."""

    tfw_income_certified: bool | None = None
    nri_sponsored: bool | None = None
    ciwg: bool | None = None


class EvidenceRowBrief(BaseModel):
    """A row as lists carry it (API_CONTRACT §A4.2)."""

    type: str
    state: str
    finding: str | None = None
    independent: bool = False
    resolved: bool = False


class EvidenceRow(BaseModel):
    """A full row of the record card (API_CONTRACT §A4.2)."""

    type: str
    state: str
    finding: str | None
    source_line: str
    summary: str
    supplied_by: str
    observed_at: str | None
    independent: bool
    # {outcome, case_id, case_action_seq, reason_code, at, by: {id, name, role}, line}
    resolved: dict[str, Any] | None
    source: str
    checked_at: str | None
    attempts: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class RecordFields(BaseModel):
    """The record status (D35): null on a record that is not ACTIVE."""

    record_status: str | None = None
    status_reason: str | None = None
    next_step: str | None = None
    record_status_at: str | None = None


class EnrolmentRow(RecordFields):
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
    eligibility: Eligibility = Field(default_factory=Eligibility)
    seat_code: str | None
    status: str
    admission_date: str
    status_date: str
    uploaded_at: str
    upload_batch_id: str | None = None
    source_row_no: int | None = None
    checks: list[EvidenceRowBrief] = Field(default_factory=list)
    flags: list[FlagRef] = Field(default_factory=list)


class RelatedEnrolmentRow(EnrolmentRow):
    """An EnrolmentRow with its institution, as case detail lists it."""

    institution: IdName


class EnrolmentPage(Page[EnrolmentRow]):
    # ACTIVE records matching every filter but record_status and status, by status
    status_counts: dict[str, int]


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


class ApprovalRef(BaseModel):
    """The cohort approval the Seat row was checked against, at its current version."""

    id: str
    academic_year: str
    version: int
    approved_intake: int
    effective_from: str | None
    source: str | None


class ClaimRef(BaseModel):
    claimed: bool
    claimed_at: str | None


class FieldChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class EnrolmentVersion(BaseModel):
    version: int
    at: str
    source: str
    actor: dict[str, Any] | None
    batch: dict[str, Any] | None
    case: dict[str, Any] | None
    changes: list[FieldChange]


class EnrolmentDetail(RecordFields):
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
    eligibility: Eligibility
    status: str
    status_date: str
    admission_date: str
    uploaded_at: str
    upload: UploadRef | None
    seat: SeatRef | None
    approval: ApprovalRef | None
    claim: ClaimRef | None
    checks: list[EvidenceRow]
    flags: list[FlagSummary]
    notices: list[EnrolmentNotice]
    resend: ResendState
    # CredentialRef (API_CONTRACT §A3.7, §A4.14), shaped by credentials.holder
    credentials: list[dict[str, Any]]
    versions: list[EnrolmentVersion]
    history_count: int


class EnrolmentHistory(Page[EnrolmentVersion]):
    pass


class CheckTransition(BaseModel):
    type: str
    before: str
    after: str


class EnrolmentRecheck(BaseModel):
    enrolment_id: str
    rechecked: int
    results: list[CheckTransition]
    flags_raised: int
    record_status: str | None
    checks: list[EvidenceRowBrief]


class InstitutionRecheckBody(BaseModel):
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class InstitutionRecheck(BaseModel):
    institution_id: str
    academic_year: str
    enrolments: int
    rechecked: int
    # the new state of every row re-run, by EvidenceState
    outcomes: dict[str, int]
    flags_raised: int
    duration_ms: int
