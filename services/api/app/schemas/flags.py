"""GET /flags and GET /flags/{id} (API_CONTRACT A2.15, A2.16), read-only in Week 2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import IdName, InstitutionRef, ProgrammeRef
from app.schemas.institutions import RelatedEnrolmentRow


class FlagRow(BaseModel):
    id: str
    type: str
    severity: str
    status: str
    institution: InstitutionRef
    programme: ProgrammeRef | None
    enrolment_id: str | None
    academic_year: str | None
    summary: str
    related_count: int
    assignee: IdName | None = None
    created_at: str
    updated_at: str


class FlagPage(BaseModel):
    items: list[FlagRow]
    total: int
    page: int
    page_size: int
    institutions: int


class EvidenceFact(BaseModel):
    label: str
    value: str
    source: str | None


class Evidence(BaseModel):
    summary: str
    facts: list[EvidenceFact]
    related_enrolment_ids: list[str]
    rule_source: str | None


class FlagDetail(FlagRow):
    evidence: Evidence
    enrolment: RelatedEnrolmentRow | None
    related_enrolments: list[RelatedEnrolmentRow]
    related_hidden: int
    history: list[Any] = Field(default_factory=list)
