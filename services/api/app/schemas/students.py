"""GET /students/me (API_CONTRACT A.10)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Countersign


class StudentEnrolment(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    programme_code: str
    programme_name: str
    academic_year: str
    year_of_study: int
    status: str
    countersign: Countersign = Field(default_factory=Countersign)


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
    notices: list[Any] = Field(default_factory=list)
    credentials: list[Any] = Field(default_factory=list)
