"""GET /students/me (API_CONTRACT A.10)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enrolments import EvidenceRowBrief
from app.schemas.notices import StudentNotice


class StudentEnrolment(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    programme_code: str
    programme_name: str
    academic_year: str
    year_of_study: int
    status: str
    # the five evidence rows, brief, in row order (API_CONTRACT §A4.5)
    checks: list[EvidenceRowBrief] = Field(default_factory=list)


class StudentMe(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    consent_status: str
    provisional_id: str | None
    dob: str
    email: str | None
    mobile_masked: str | None
    enrolments: list[StudentEnrolment]
    notices: list[StudentNotice] = Field(default_factory=list)
    # StudentCredentialBrief (API_CONTRACT §A3.6), shaped by credentials.holder
    credentials: list[dict[str, Any]] = Field(default_factory=list)
