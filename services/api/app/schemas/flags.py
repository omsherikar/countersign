"""Flags, their case history and officer actions (API_CONTRACT A2.15, A2.16, A3.9 to A3.14)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import IdName, InstitutionRef, ProgrammeRef
from app.schemas.institutions import RelatedEnrolmentRow

OfficerAction = Literal[
    "UPHOLD", "REQUEST_DOCS", "ESCALATE", "WITHDRAW", "NOTE", "ASSIGN", "REOPEN"
]


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
    # always null for a college
    assignee: IdName | None = None
    response_received: bool = False
    docs_due_on: str | None = None
    last_action_at: str | None = None
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


class ActorRef(BaseModel):
    id: str
    name: str
    role: str


class CaseAttachmentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


class CaseHistoryItem(BaseModel):
    seq: int
    at: str
    action: str
    from_status: str | None
    to_status: str | None
    # null for rows the system wrote
    actor: ActorRef | None
    note: str | None
    due_date: str | None
    assignee: IdName | None
    attachments: list[CaseAttachmentOut]


class FlagDetail(FlagRow):
    evidence: Evidence
    enrolment: RelatedEnrolmentRow | None
    related_enrolments: list[RelatedEnrolmentRow]
    related_hidden: int
    history: list[CaseHistoryItem] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    can_respond: bool = False


class CaseActionIn(BaseModel):
    """POST /flags/{id}/actions. Whether a note, a date or an assignee is needed depends on
    the action and is checked after scope and status, as field rules."""

    action: OfficerAction
    note: str | None = None
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None

    @field_validator("note")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Write at most 2,000 characters.")
        return value or None


class OfficerRow(BaseModel):
    id: str
    name: str
    role: str
    region: str | None
