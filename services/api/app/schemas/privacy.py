"""Privacy notice, consents, access log and data requests (API_CONTRACT §A3.22)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.models.enums import DataRequestKind

DETAILS_REQUIRED = "Write a few words so an officer knows what to do."
DETAILS_TOO_LONG = "Write at most 2,000 characters."
RESPONSE_REQUIRED = "Write a reply before you resolve the request."


class NoticeSection(BaseModel):
    id: str
    heading: str
    body: str


class PrivacyNoticeOut(BaseModel):
    version: str
    effective_from: str
    title: str
    sections: list[NoticeSection]
    consent_texts: dict[str, str]


class EnrolmentBrief(BaseModel):
    id: str
    institution_name: str
    programme_name: str
    academic_year: str


class ConsentCurrent(BaseModel):
    purpose: str
    status: str  # GIVEN | WITHDRAWN | REFUSED | NONE
    since: str | None
    can_withdraw: bool


class ConsentRow(BaseModel):
    id: str
    purpose: str
    status: str
    channel: str
    notice_text: str
    notice_version: str
    recorded_at: str
    withdrawn_at: str | None
    enrolment: EnrolmentBrief | None


class ConsentsView(BaseModel):
    current: list[ConsentCurrent]
    items: list[ConsentRow]


class ConsentWithdrawResult(ConsentsView):
    presentations_expired: int


class AccessLogRow(BaseModel):
    at: str
    role: str
    what: str


def _text(value: str | None, *, low: int, required: bool, missing: str) -> str | None:
    value = (value or "").strip() or None
    if value is None:
        if required:
            raise ValueError(missing)
        return None
    if len(value) < low:
        raise ValueError(missing)
    if len(value) > 2000:
        raise ValueError(DETAILS_TOO_LONG)
    return value


class DataRequestCreate(BaseModel):
    kind: DataRequestKind
    details: str | None = Field(default=None, validate_default=True)
    enrolment_id: uuid.UUID | None = None

    @field_validator("details")
    @classmethod
    def _details(cls, value: str | None, info: ValidationInfo) -> str | None:
        # required for a correction or an erasure; an access request may say nothing
        kind = info.data.get("kind")
        required = kind is not None and kind is not DataRequestKind.ACCESS
        return _text(value, low=10, required=required, missing=DETAILS_REQUIRED)


class DataRequestResolve(BaseModel):
    status: Literal["DONE", "REJECTED"]
    response: str

    @field_validator("response")
    @classmethod
    def _response(cls, value: str) -> str:
        text = _text(value, low=10, required=True, missing=RESPONSE_REQUIRED)
        assert text is not None
        return text


class DataRequestRow(BaseModel):
    id: str
    kind: str
    status: str
    details: str | None
    response: str | None
    enrolment: EnrolmentBrief | None
    created_at: str
    resolved_at: str | None
    export_path: str | None


class DataRequestStudent(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    provisional_id: str | None


class ResolvedBy(BaseModel):
    id: str
    name: str


class DataRequestAdminRow(DataRequestRow):
    student: DataRequestStudent
    resolved_by: ResolvedBy | None
