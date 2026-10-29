"""GET /students/me and the student's own answer (API_CONTRACT A.10, §A4.5, §A4.13)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.notices import NoticeResponseWire, StudentNotice


class EvidenceRowBrief(BaseModel):
    type: str
    state: str
    finding: str | None = None
    # who supplied the evidence and when ("State admission authority · 20 Aug"), as on the
    # officer's card; no student data
    source_line: str | None = None
    independent: bool = False
    resolved: bool = False


class StudentDecision(BaseModel):
    """The latest decision or escalation of the student's dispute (never the note or the
    officer)."""

    outcome: Literal["UPHELD", "CORRECTED", "WITHDRAWN", "ESCALATED"]
    reason_code: str | None
    at: str


class StudentEnrolment(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    programme_code: str
    programme_name: str
    academic_year: str
    year_of_study: int
    status: str
    record_status: str | None = None
    status_reason: str | None = None
    next_step: str | None = None
    checks: list[EvidenceRowBrief] = Field(default_factory=list)
    response: NoticeResponseWire | None = None
    can_respond: bool = False
    claimed: bool = False
    decision: StudentDecision | None = None


class StudentMe(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    consent_status: str
    provisional_id: str | None
    dob: str
    email: str | None
    mobile_masked: str | None
    signed_in_with: Literal["DIGILOCKER"] = "DIGILOCKER"
    enrolments: list[StudentEnrolment]
    notices: list[StudentNotice] = Field(default_factory=list)
    # StudentCredentialBrief (API_CONTRACT §A3.6), shaped by credentials.holder
    credentials: list[dict[str, Any]] = Field(default_factory=list)
