"""GET and POST /approvals/{id}/versions (API_CONTRACT §A4.17)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import ProgrammeRef


class ApprovalVersionOut(BaseModel):
    version: int
    approved_intake: int
    effective_from: str
    source: str
    created_at: str


class ApprovalInstitution(BaseModel):
    id: str
    name: str
    aicte_permanent_id: str


class ApprovalVersions(BaseModel):
    approval_id: str
    institution: ApprovalInstitution
    programme: ProgrammeRef
    academic_year: str
    current_version: int
    items: list[ApprovalVersionOut]


class ApprovalVersionCreate(BaseModel):
    approved_intake: int = Field(ge=1, le=10_000)
    effective_from: date
    source: str = Field(min_length=3, max_length=200)


class ApprovalEffects(BaseModel):
    seats_added: int
    seats_removed: int
    seated: int
    flags_refreshed: int
    records_changed: int


class ApprovalVersionCreated(ApprovalVersions):
    effects: ApprovalEffects
