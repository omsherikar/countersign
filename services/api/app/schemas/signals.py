"""Signals (API_CONTRACT §A4.19)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import IdName, Page
from app.schemas.flags import FlagRow

NOTE_MAX = 2000


class SignalInstitution(BaseModel):
    id: str
    name: str
    aicte_permanent_id: str
    state_code: str
    region: str


class SignalCaseRef(BaseModel):
    id: str
    institution_id: str
    status: str


class SignalRow(BaseModel):
    id: str
    type: str
    academic_year: str
    status: str
    summary: str
    member_count: int
    members_hidden: int
    score: float | None
    institutions: list[SignalInstitution]
    institutions_hidden: int
    rule: str
    cases: list[SignalCaseRef]
    created_at: str
    updated_at: str


class SignalPage(Page[SignalRow]):
    pass


class SignalFact(BaseModel):
    label: str
    value: str
    source: str | None


class SignalShared(BaseModel):
    kind: Literal["MOBILE", "EMAIL", "ADDRESS"]
    masked: str
    students: int


class SignalFeature(BaseModel):
    name: str
    value: float
    peer_low: float
    peer_high: float
    peer_median: float
    robust_z: float
    stands_out: bool


class SignalMemberStudent(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    provisional_id: str | None


class SignalMember(BaseModel):
    enrolment_id: str
    student: SignalMemberStudent
    institution: IdName
    programme_code: str
    record_status: str | None


class SignalDismissal(BaseModel):
    note: str
    by: IdName
    at: str


class SignalDetail(SignalRow):
    facts: list[SignalFact]
    shared: list[SignalShared]
    features: list[SignalFeature]
    members: list[SignalMember]
    dismissal: SignalDismissal | None


def _note(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Add a note before you continue.")
    if len(value) > NOTE_MAX:
        raise ValueError("Write at most 2,000 characters.")
    return value


class SignalOpenCaseBody(BaseModel):
    institution_ids: list[str] | None = Field(default=None, max_length=200)
    note: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] | None = None

    _check_note = field_validator("note")(_note)


class SignalOpenCaseResult(BaseModel):
    cases: list[FlagRow]
    signal: SignalDetail


class SignalDismissBody(BaseModel):
    note: str

    _check_note = field_validator("note")(_note)


class SignalRunBody(BaseModel):
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")


class SignalModel(BaseModel):
    name: str
    contamination: float
    n_estimators: int
    random_state: int
    institutions: int


class SignalRunResult(BaseModel):
    academic_year: str
    rings: int
    anomalies: int
    created: int
    updated: int
    duration_ms: int
    model: SignalModel
