"""Student notices on the wire (API_CONTRACT §A3.3 to §A3.7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NoticeChannelWire = Literal["EMAIL", "DIGILOCKER"]
NoticeResponseWire = Literal["YES", "NO"]
NoticeDeliveryWire = Literal["QUEUED", "SENT", "FAILED"]
NoticeStateWire = Literal["QUEUED", "AWAITING", "ANSWERED", "EXPIRED", "FAILED"]
ResendBlock = Literal[
    "LIVE", "ANSWERED", "LIMIT", "CONSENT_WITHDRAWN", "NO_CHANNEL", "NOT_ACTIVE", "ROLE"
]


class NoticePublic(BaseModel):
    """GET /notices/{token}: the claim and the answer, no name, birth date or full id."""

    channel: NoticeChannelWire
    institution_name: str
    programme_code: str
    programme_name: str
    academic_year: str
    year_of_study: int
    id_kind: Literal["APAAR", "PROVISIONAL"]
    id_masked: str
    uploaded_at: str
    sent_at: str | None
    expires_at: str
    response: NoticeResponseWire | None
    responded_at: str | None
    previous_response: NoticeResponseWire | None
    changed_at: str | None
    can_change_until: str | None
    consent_text: str
    notice_version: str


class NoticeRespondRequest(BaseModel):
    response: NoticeResponseWire
    # kept only with NO
    comment: str | None = Field(default=None, max_length=500)


class StudentNotice(BaseModel):
    id: str
    enrolment_id: str
    channel: NoticeChannelWire
    institution_name: str
    programme_name: str
    academic_year: str
    state: NoticeStateWire
    delivery_status: NoticeDeliveryWire
    sent_at: str | None
    expires_at: str
    response: NoticeResponseWire | None
    responded_at: str | None
    changed_at: str | None
    can_change_until: str | None


class EnrolmentNotice(BaseModel):
    id: str
    channel: NoticeChannelWire
    state: NoticeStateWire
    delivery_status: NoticeDeliveryWire
    attempts: int
    last_error: str | None
    sent_at: str | None
    expires_at: str
    response: NoticeResponseWire | None
    responded_at: str | None
    previous_response: NoticeResponseWire | None
    changed_at: str | None
    resent: bool


class ResendState(BaseModel):
    allowed: bool
    blocked_by: ResendBlock | None
    resends_left: int


class NoticeResendResult(BaseModel):
    enrolment_id: str
    notices: list[EnrolmentNotice]
    resend: ResendState
