"""Flags, their case history and officer actions (API_CONTRACT A2.15, A2.16, A3.9 to A3.14,
A4.8 to A4.11)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import IdName, InstitutionRef, ProgrammeRef
from app.schemas.institutions import RelatedEnrolmentRow

OfficerAction = Literal[
    "UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS", "ESCALATE", "NOTE", "ASSIGN", "REOPEN"
]


class DecisionRef(BaseModel):
    """The latest UPHOLD, CORRECT or WITHDRAW while the case is decided."""

    action: str
    reason_code: str | None
    at: str


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
    # the row the case covers and how it is decided (§A4.10, §A4.11)
    covers: str | None = None
    scope: str = "RECORD"
    decision: DecisionRef | None = None
    # the signal an officer opened the case from; always null for a college
    signal_id: str | None = None
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


class FieldChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class CorrectionOut(BaseModel):
    enrolment_id: str | None
    changes: list[FieldChange]


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
    reason_code: str | None = None
    docs_kind: str | None = None
    approval_version: int | None = None
    correction: CorrectionOut | None = None
    withdrawn_enrolment_ids: list[str] = Field(default_factory=list)


class CaseApproval(BaseModel):
    id: str
    current_version: int
    approved_intake: int
    covers: bool


class MissingStudent(BaseModel):
    name: str
    roll_no: str | None
    programme_code: str
    joined_on: str | None
    round: int | None
    route: str | None
    apaar_masked: str | None


class FlagDetail(FlagRow):
    evidence: Evidence
    enrolment: RelatedEnrolmentRow | None
    related_enrolments: list[RelatedEnrolmentRow]
    related_hidden: int
    outstanding_enrolment_ids: list[str] = Field(default_factory=list)
    approval: CaseApproval | None = None
    missing_students: list[MissingStudent] = Field(default_factory=list)
    history: list[CaseHistoryItem] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    can_respond: bool = False


class RecordChange(BaseModel):
    enrolment_id: str
    status: str
    record_status: str | None
    status_reason: str | None


class SeatChange(BaseModel):
    enrolment_id: str
    seat_code: str


class AttestationChange(BaseModel):
    enrolment_id: str
    credential_id: str
    short_id: str


class ApprovalCited(BaseModel):
    version: int
    approved_intake: int
    cohort_year: str
    programme_code: str


class DecisionEffects(BaseModel):
    """What an action changed, with real values (§A4.9 `effects`)."""

    case_status: str
    records: list[RecordChange] = Field(default_factory=list)
    version: int | None = None
    changes: list[FieldChange] = Field(default_factory=list)
    rows_resolved: int = 0
    rows_rerun: int = 0
    seats_released: list[SeatChange] = Field(default_factory=list)
    seats_assigned: list[SeatChange] = Field(default_factory=list)
    attestations_revoked: list[AttestationChange] = Field(default_factory=list)
    attestations_issued: list[AttestationChange] = Field(default_factory=list)
    approval: ApprovalCited | None = None


class CaseActionResult(FlagDetail):
    effects: DecisionEffects


class DryRunResult(BaseModel):
    dry_run: Literal[True] = True
    effects: DecisionEffects


class CorrectionIn(BaseModel):
    enrolment_id: uuid.UUID | None = None
    fields: dict[str, Any]


class CaseActionIn(BaseModel):
    """POST /flags/{id}/actions. Whether a reason, a note, a date, an assignee, the records
    or a correction is needed depends on the action and the case, and is checked after scope
    and status, as field rules."""

    action: OfficerAction
    reason_code: str | None = Field(default=None, max_length=64)
    note: str | None = None
    docs_kind: str | None = Field(default=None, max_length=32)
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    withdrawn_enrolment_ids: list[uuid.UUID] | None = Field(default=None, max_length=1000)
    correction: CorrectionIn | None = None
    approval_version: int | None = Field(default=None, ge=1)
    dry_run: bool = False

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
