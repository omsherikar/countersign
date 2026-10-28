"""Request and response bodies, exactly as docs/API_CONTRACT.md section C."""

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_APAAR = re.compile(r"^\d{12}$")


def _validate_apaar(value: str) -> str:
    value = value.strip()
    if not _APAAR.fullmatch(value):
        raise ValueError("apaar_id must be 12 digits.")
    return value


class ApaarVerifyRequest(BaseModel):
    apaar_id: str
    name: str = Field(min_length=1)
    dob: date

    _check_apaar = field_validator("apaar_id")(_validate_apaar)


class ApaarVerifyResponse(BaseModel):
    exists: bool
    name_score: int
    dob_match: bool


class CounsellingVerifyRequest(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    year: int
    name: str = Field(min_length=1)
    dob: date
    roll_no: str | None = None
    programme: str = Field(min_length=1)
    institution_aicte_id: str | None = None


class CounsellingVerifyResponse(BaseModel):
    found: bool
    round: int | None
    category: str | None
    allotment_ref: str | None


class AbcCreditsRequest(BaseModel):
    apaar_id: str
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")

    _check_apaar = field_validator("apaar_id")(_validate_apaar)


class AbcSemester(BaseModel):
    sem: int
    credits: int
    uploaded_at: datetime
    result: Literal["PASS", "FAIL", "PENDING"]
    # A university code, or the AICTE permanent id of a college that issues its own credits.
    issuer: str
    issuer_name: str


class AbcCreditsResponse(BaseModel):
    apaar_id_known: bool
    semesters: list[AbcSemester]


class DigiLockerNotifyRequest(BaseModel):
    apaar_id: str
    message: str = Field(min_length=1)
    callback_url: str = Field(min_length=1)

    _check_apaar = field_validator("apaar_id")(_validate_apaar)


class DigiLockerNotifyResponse(BaseModel):
    delivered: bool
    inbox_id: str | None
    reason: str | None = None


class DigiLockerInboxItem(BaseModel):
    inbox_id: str
    message: str
    callback_url: str
    received_at: datetime
    read: bool


class DigiLockerInboxResponse(BaseModel):
    items: list[DigiLockerInboxItem]


class SiiVerifyRequest(BaseModel):
    passport_no: str = Field(min_length=1)
    name: str = Field(min_length=1)
    nationality: str = Field(min_length=2, max_length=2)


class SiiVerifyResponse(BaseModel):
    admitted: bool
    institution_aicte_id: str | None
    programme: str | None
    academic_year: str | None


class JoiningVerifyRequest(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    name: str = Field(min_length=1)
    dob: date
    roll_no: str | None = None
    institution_code: str = Field(min_length=1)
    programme: str = Field(min_length=1)


class JoiningVerifyResponse(BaseModel):
    found: bool
    joined_on: date | None
    round: int | None
    route: str | None
    category: str | None
    # False when the authority holds no joining at all for that state and academic year.
    published: bool


class JoiningListItem(BaseModel):
    roll_no: str | None
    name: str
    dob: date
    programme: str
    joined_on: date
    round: int | None
    route: str
    category: str
    apaar_last4: str | None


class JoiningListResponse(BaseModel):
    institution_code: str
    academic_year: str
    published: bool
    items: list[JoiningListItem]


ChaosSource = Literal[
    "apaar", "counselling", "abc", "digilocker", "sii", "admission_authority", "all"
]


class ChaosEntry(BaseModel):
    latency_ms: int
    fail_rate: float
    down: bool


class ChaosUpdateRequest(BaseModel):
    source: ChaosSource
    latency_ms: int = Field(default=0, ge=0, le=60_000)
    fail_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    down: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
    chaos: dict[str, ChaosEntry]
