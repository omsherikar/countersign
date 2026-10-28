"""Shapes passed between the upload stages (API_CONTRACT §A2.2, §A2.3; ENGINES.md §5)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, Literal

from app.models.enums import (
    AdmissionRoute,
    Category,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
    RowErrorLevel,
)

# Template order: the 16 columns of section E, then status, status_date, admission_date.
UPLOAD_COLUMNS: tuple[str, ...] = (
    "apaar_id",
    "name",
    "dob",
    "gender",
    "mobile",
    "email",
    "address",
    "nationality",
    "passport_no",
    "programme_code",
    "academic_year",
    "year_of_study",
    "admission_route",
    "counselling_ref",
    "category",
    "consent_status",
    "status",
    "status_date",
    "admission_date",
)
REQUIRED_COLUMNS: tuple[str, ...] = (
    "name",
    "dob",
    "programme_code",
    "year_of_study",
    "admission_route",
    "category",
)
FIELD_WORDS: dict[str, str] = {
    "name": "Name",
    "dob": "Date of birth",
    "programme_code": "Programme code",
    "year_of_study": "Year of study",
    "admission_route": "Admission route",
    "category": "Category",
}

DECLARATION_TEXT = (
    "I declare that every student in this file has consented to their APAAR being used to "
    "verify this enrolment, and that the file is true to the college's admission register."
)

# Registrars upload in Indian time; "after the upload date" is judged on that calendar.
INDIA = timezone(timedelta(hours=5, minutes=30), "IST")

FileKind = Literal["csv", "xlsx", "json"]


def upload_date(uploaded_at: datetime) -> date:
    """The calendar date of an upload in India (UTC+05:30)."""
    if uploaded_at.tzinfo is None:
        uploaded_at = uploaded_at.replace(tzinfo=UTC)
    return uploaded_at.astimezone(INDIA).date()


class UploadFileError(Exception):
    """A file-level problem: the whole upload is rejected (API_CONTRACT §A2.4, §A2.7).

    `message` is the exact sentence shown to the registrar, both as the HTTP error message
    and as the batch's `error` when the batch fails in PARSE.
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class RawRow:
    """One data row as read: every known column present, "" when blank."""

    row_no: int
    values: dict[str, str]


@dataclass(slots=True)
class ParsedUpload:
    rows: list[RawRow]
    ignored_columns: list[str] = field(default_factory=list)
    kind: FileKind = "csv"

    @property
    def total_rows(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class RowIssue:
    """One upload_row_errors entry: a problem in one field of one row."""

    row_no: int
    level: RowErrorLevel
    field: str | None
    code: str
    message: str
    value_masked: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProgrammeInfo:
    id: uuid.UUID
    code: str
    duration_years: int
    approval_years: frozenset[str]


@dataclass(frozen=True, slots=True)
class ValidationContext:
    institution_aicte_id: str
    academic_year: str
    upload_date: date
    programmes: Mapping[str, ProgrammeInfo]  # keyed by upper-case code, FIRST shift preferred


@dataclass(slots=True)
class CleanRow:
    """A row that passed validation, with every value parsed and the identity decided.

    Optional student fields are None when the upload left them blank: a new student then
    takes the default, an existing one keeps what is stored.
    """

    row_no: int
    name: str
    dob: date
    programme_id: uuid.UUID
    programme_code: str
    year_of_study: int
    cohort_year: str
    admission_route: AdmissionRoute
    category: Category
    consent_status: ConsentStatus
    apaar_id: str | None = None  # 12 digits; only when it is the identity (consent LINKED)
    apaar_problem: str | None = None
    gender: Gender | None = None
    mobile: str | None = None  # 10 digits
    email: str | None = None
    address: str | None = None
    nationality: str | None = None
    passport_no: str | None = None
    counselling_ref: str | None = None
    status: EnrolmentStatus | None = None
    status_raw: str = ""
    status_date: date | None = None
    admission_date: date | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def effective_nationality(self) -> str:
        return self.nationality or "IN"


@dataclass(slots=True)
class ValidationResult:
    rows: list[CleanRow] = field(default_factory=list)  # accepted
    issues: list[RowIssue] = field(default_factory=list)  # every entry, errors and warnings
    rejected: list[int] = field(default_factory=list)  # row numbers with an ERROR entry

    @property
    def accepted(self) -> int:
        return len(self.rows)


Outcome = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True, slots=True)
class RowOutcome:
    row_no: int
    enrolment_id: uuid.UUID
    student_id: uuid.UUID
    outcome: Outcome
    status: EnrolmentStatus
    released: bool  # this batch moved the enrolment to WITHDRAWN or TRANSFERRED


@dataclass(slots=True)
class UpsertResult:
    outcomes: list[RowOutcome] = field(default_factory=list)
    issues: list[RowIssue] = field(default_factory=list)
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    withdrawn: int = 0
    transferred: int = 0
    students_created: int = 0
    students_updated: int = 0
    versions: int = 0  # enrolment versions written (D42)
