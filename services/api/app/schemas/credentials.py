"""Wallet and verifier shapes (API_CONTRACT A3.16, A3.17, A3.18, A3.20)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.credentials.issuer import ADMIN_REASON, REASON_CODES


class IssuerRef(BaseModel):
    name: str
    url: str


class DisclosableField(BaseModel):
    key: str
    label: str
    always: bool


class PresentationBrief(BaseModel):
    id: str
    created_at: str
    expires_at: str
    disclosed: list[str]
    verify_count: int
    last_verified_at: str | None


class CredentialCard(BaseModel):
    id: str
    kind: str
    status: str
    vct: str
    short_id: str
    issuer: IssuerRef
    enrolment_id: str
    institution_name: str
    programme_name: str
    academic_year: str
    university_name: str | None
    issued_at: str
    expires_at: str | None
    revoked_at: str | None
    revoked_reason_code: str | None
    revoked_reason: str | None
    holder_bound: bool
    disclosable: list[DisclosableField]
    shares: int
    last_verified_at: str | None
    presentations: list[PresentationBrief]


class CredentialClaim(BaseModel):
    key: str
    label: str
    value: str
    disclosable: bool


class CredentialDetail(CredentialCard):
    claims: list[CredentialClaim]


class PresentRequest(BaseModel):
    fields: list[str] = Field(default_factory=list)
    consent: bool = False


class PresentationCreated(BaseModel):
    id: str
    code: str
    url: str
    qr_svg: str
    expires_at: str
    disclosed: list[str]
    total: int


class PresentationRow(BaseModel):
    id: str
    created_at: str
    expires_at: str
    state: Literal["LIVE", "EXPIRED"]
    disclosed: list[str]
    verify_count: int
    first_verified_at: str | None
    last_verified_at: str | None


class RevokeRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]

    @field_validator("reason")
    @classmethod
    def _words_not_a_code(cls, value: str) -> str:
        if value in (*REASON_CODES, ADMIN_REASON):
            raise ValueError("Write the reason in words; reason codes are set by the system.")
        return value


# ---------------------------------------------------------------------- verifier


class DisclosedField(BaseModel):
    key: str
    label: str
    value: str


class VerifyResult(BaseModel):
    result: Literal["VALID", "REVOKED", "EXPIRED", "INVALID"]
    kind: str | None
    issuer: IssuerRef | None
    institution_name: str | None
    university_name: str | None
    issued_at: str | None
    expires_at: str | None
    revoked_at: str | None
    disclosed: list[DisclosedField]
    holder_bound: bool
    status_checked_at: str | None
    method: Literal["signature", "register_lookup"]
    nonce: str | None


class VerifyPasteRequest(BaseModel):
    presentation: Annotated[str, StringConstraints(min_length=1, max_length=16_384)]
