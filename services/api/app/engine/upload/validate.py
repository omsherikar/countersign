"""VALIDATE and FILE_DUPLICATES: field rules and row errors (API_CONTRACT §A2.2, §A2.3).

Pure functions: every problem in a row is reported, one entry per field; a row with any
ERROR entry is rejected, a row with only WARNING entries is accepted.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cohort import cohort_year, start_year
from app.engine.upload.mask import mask_value, masked_row
from app.engine.upload.types import (
    ELIGIBILITY_COLUMNS,
    FIELD_WORDS,
    REQUIRED_COLUMNS,
    CleanRow,
    ParsedUpload,
    ProgrammeInfo,
    RawRow,
    RowIssue,
    ValidationContext,
    ValidationResult,
)
from app.models.enums import (
    AdmissionRoute,
    Category,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
    RowErrorLevel,
    Shift,
)
from app.models.institution import Approval, Institution, Programme

ERROR, WARNING = RowErrorLevel.ERROR, RowErrorLevel.WARNING
MIN_AGE, MAX_AGE = 14, 60
MAX_YEAR_UNKNOWN_PROGRAMME = 6
NAME_MAX = 200

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")

GENDERS = {"M": Gender.M, "F": Gender.F, "O": Gender.O, "U": Gender.U}
# eligibility markers (API_CONTRACT §A4.16): any case; anything else is not reported
MARKER_VALUES = {"YES": True, "Y": True, "TRUE": True, "1": True}
MARKER_VALUES |= {"NO": False, "N": False, "FALSE": False, "0": False}
GENDERS |= {"MALE": Gender.M, "FEMALE": Gender.F, "OTHER": Gender.O}
UPLOAD_STATUSES = (EnrolmentStatus.ACTIVE, EnrolmentStatus.WITHDRAWN, EnrolmentStatus.TRANSFERRED)

BAD_ENUM_MESSAGES = {
    "admission_route": (
        "Admission route must be one of Counselling, Management, NRI, Spot, Lateral, "
        "International, TFW"
    ),
    "category": "Category must be one of General, EWS, OBC, SC, ST, Other",
    "consent_status": "Consent status must be Linked, Refused, Pending or International",
    "status": "Status must be Active, Withdrawn or Transferred",
    "gender": "Gender must be M, F, O or U; recorded as U",
}
DATE_WORDS = {"status_date": "Status date", "admission_date": "Admission date"}
CONSENT_WORDS = {
    ConsentStatus.REFUSED: "Refused",
    ConsentStatus.PENDING: "Pending",
    ConsentStatus.INTERNATIONAL: "International",
}
STATUS_WORDS = {EnrolmentStatus.WITHDRAWN: "Withdrawn", EnrolmentStatus.TRANSFERRED: "Transferred"}


async def load_context(
    session: AsyncSession, institution: Institution, academic_year: str, on: date
) -> ValidationContext:
    """The institution's programmes and approval years, in one query."""
    rows = (
        await session.execute(
            select(Programme, Approval.academic_year)
            .outerjoin(Approval, Approval.programme_id == Programme.id)
            .where(Programme.institution_id == institution.id)
        )
    ).all()
    found: dict[tuple[str, Shift], tuple[Programme, set[str]]] = {}
    for programme, year in rows:
        _, years = found.setdefault((programme.code.upper(), programme.shift), (programme, set()))
        if year:
            years.add(year)
    programmes: dict[str, ProgrammeInfo] = {}
    # FIRST shift wins when a code exists in both shifts (ENGINES.md §5 rule 7)
    for (code, _shift), (programme, years) in sorted(
        found.items(), key=lambda item: (item[0][0], item[0][1] is not Shift.FIRST)
    ):
        programmes.setdefault(
            code,
            ProgrammeInfo(
                id=programme.id,
                code=programme.code,
                duration_years=programme.duration_years,
                approval_years=frozenset(years),
            ),
        )
    return ValidationContext(
        institution_aicte_id=institution.aicte_permanent_id,
        academic_year=academic_year,
        upload_date=on,
        programmes=programmes,
    )


def enum_key(raw: str) -> str:
    """Enum values match case-insensitively with spaces and hyphens read as underscores."""
    return raw.strip().upper().replace(" ", "_").replace("-", "_")


def parse_iso_date(raw: str) -> date | None:
    if not _ISO_DATE.match(raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def clean_mobile(raw: str) -> str | None:
    """10 digits after removing spaces and a leading +91 or 0; None when not a mobile."""
    value = raw.replace(" ", "")
    if len(value) == 13 and value.startswith("+91"):
        value = value[3:]
    elif len(value) == 11 and value.startswith("0"):
        value = value[1:]
    return value if len(value) == 10 and value.isdigit() else None


def apaar_problem(raw: str) -> str | None:
    """Why an uploaded APAAR is unusable ("has 11 digits, expected 12"), or None when fine."""
    clean = raw.replace(" ", "")
    if not clean:
        return None
    if not clean.isdigit():
        return "contains characters other than digits"
    if len(clean) != 12:
        return f"has {len(clean)} digits, expected 12"
    return None


def consent_conflict(consent: ConsentStatus) -> str:
    return f"APAAR given but consent is {CONSENT_WORDS[consent]}; the APAAR was not used"


def age_on(dob: date, day: date) -> int:
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))


class _Row:
    """Collects one row's issues; one entry per field."""

    def __init__(self, raw: RawRow) -> None:
        self.raw = raw
        self.values = raw.values
        self.masked = masked_row(raw.values)
        self.issues: list[RowIssue] = []

    def get(self, column: str) -> str:
        return (self.values.get(column) or "").strip()

    def add(self, level: RowErrorLevel, column: str, code: str, message: str) -> None:
        self.issues.append(
            RowIssue(
                row_no=self.raw.row_no,
                level=level,
                field=column,
                code=code,
                message=message,
                value_masked=mask_value(column, self.values.get(column)),
                raw=self.masked,
            )
        )

    @property
    def rejected(self) -> bool:
        return any(issue.level is ERROR for issue in self.issues)

    def enum(self, column: str, enum_cls: Any, allowed: Any = None) -> Any:
        raw = self.get(column)
        if not raw:
            return None
        try:
            value = enum_cls(enum_key(raw))
        except ValueError:
            value = None
        if value is None or (allowed is not None and value not in allowed):
            self.add(ERROR, column, "BAD_ENUM", BAD_ENUM_MESSAGES[column])
            return None
        return value

    def marker(self, column: str) -> bool | None:
        """yes or no; blank is not reported, and anything else is a warning, not reported."""
        raw = self.get(column)
        if not raw:
            return None
        value = MARKER_VALUES.get(raw.upper())
        if value is None:
            message = f"{FIELD_WORDS[column]} must be yes or no; recorded as not reported"
            self.add(WARNING, column, "BAD_ENUM", message)
        return value

    def optional_date(self, column: str, upload_day: date) -> date | None:
        raw = self.get(column)
        if not raw:
            return None
        value = parse_iso_date(raw)
        if value is None:
            self.add(ERROR, column, "DATE_FORMAT", f"{DATE_WORDS[column]} must be YYYY-MM-DD")
        elif value > upload_day:
            message = f"{DATE_WORDS[column]} {raw} is after the upload date"
            self.add(ERROR, column, "DATE_IN_FUTURE", message)
            return None
        return value


def validate_row(raw: RawRow, ctx: ValidationContext) -> tuple[CleanRow | None, list[RowIssue]]:
    row = _Row(raw)

    for column in REQUIRED_COLUMNS:
        if not row.get(column):
            row.add(ERROR, column, "MISSING_REQUIRED", f"{FIELD_WORDS[column]} is required")

    # programme, academic year, year of study, cohort
    programme: ProgrammeInfo | None = None
    code = row.get("programme_code")
    if code:
        programme = ctx.programmes.get(code.upper())
        if programme is None:
            row.add(
                ERROR,
                "programme_code",
                "UNKNOWN_PROGRAMME",
                f"Programme code {code} is not approved for your college",
            )
    year_raw = row.get("academic_year")
    if year_raw and year_raw != ctx.academic_year:
        row.add(
            ERROR,
            "academic_year",
            "YEAR_MISMATCH",
            f"Academic year {year_raw} does not match this upload's academic year "
            f"{ctx.academic_year}",
        )
    year_of_study: int | None = None
    cohort: str | None = None
    yos_raw = row.get("year_of_study")
    if yos_raw:
        limit = programme.duration_years if programme else MAX_YEAR_UNKNOWN_PROGRAMME
        if yos_raw.isdigit() and 1 <= int(yos_raw) <= limit:
            year_of_study = int(yos_raw)
            cohort = cohort_year(ctx.academic_year, year_of_study)
            if programme is not None and cohort not in programme.approval_years:
                row.add(
                    ERROR,
                    "year_of_study",
                    "NO_APPROVAL_FOR_COHORT",
                    f"{programme.code} has no approval for {cohort}, the intake of a year "
                    f"{year_of_study} student in {ctx.academic_year}",
                )
        else:
            row.add(
                ERROR,
                "year_of_study",
                "YEAR_OF_STUDY_INVALID",
                f"Year of study must be a whole number between 1 and {limit}",
            )

    # date of birth
    dob: date | None = None
    dob_raw = row.get("dob")
    if dob_raw:
        dob = parse_iso_date(dob_raw)
        if dob is None:
            row.add(ERROR, "dob", "DOB_FORMAT", "Date of birth must be YYYY-MM-DD")
        else:
            intake = start_year(cohort or ctx.academic_year)
            age = age_on(dob, date(intake, 7, 1))
            if dob > ctx.upload_date or not MIN_AGE <= age <= MAX_AGE:
                row.add(
                    ERROR,
                    "dob",
                    "DOB_IMPLAUSIBLE",
                    f"Date of birth {dob_raw} gives an age of {age} at admission; "
                    f"expected {MIN_AGE} to {MAX_AGE}",
                )

    # enums
    route: AdmissionRoute | None = row.enum("admission_route", AdmissionRoute)
    category: Category | None = row.enum("category", Category)
    consent_given: ConsentStatus | None = row.enum("consent_status", ConsentStatus)
    status: EnrolmentStatus | None = row.enum("status", EnrolmentStatus, UPLOAD_STATUSES)
    gender: Gender | None = None
    gender_raw = row.get("gender")
    if gender_raw:
        gender = GENDERS.get(enum_key(gender_raw))
        if gender is None:
            row.add(WARNING, "gender", "BAD_ENUM", BAD_ENUM_MESSAGES["gender"])
            gender = Gender.U

    # nationality and passport
    nationality: str | None = None
    nationality_raw = row.get("nationality")
    nationality_ok = True
    if nationality_raw:
        nationality = nationality_raw.upper()
        if not _COUNTRY.match(nationality):
            nationality_ok = False
            nationality = None
            row.add(
                ERROR,
                "nationality",
                "NATIONALITY_FORMAT",
                "Nationality must be a two-letter country code, e.g. IN",
            )
    foreign = nationality_ok and nationality is not None and nationality != "IN"
    international_row = route is AdmissionRoute.INTERNATIONAL or foreign
    passport = row.get("passport_no").replace(" ", "").upper() or None
    needs_passport = (
        route is AdmissionRoute.INTERNATIONAL
        or consent_given is ConsentStatus.INTERNATIONAL
        or foreign
    )
    if needs_passport and passport is None:
        message = "International students need a passport number"
        row.add(ERROR, "passport_no", "PASSPORT_REQUIRED", message)

    # contact details: a bad value is a warning and is not used
    mobile: str | None = None
    if row.get("mobile"):
        mobile = clean_mobile(row.get("mobile"))
        if mobile is None:
            message = "Mobile must be 10 digits; the value was not used"
            row.add(WARNING, "mobile", "MOBILE_FORMAT", message)
    email: str | None = None
    if row.get("email"):
        if _EMAIL.match(row.get("email")):
            email = row.get("email")
        else:
            row.add(
                WARNING,
                "email",
                "EMAIL_FORMAT",
                "Email address is not valid; the value was not used",
            )

    # dates
    status_date = row.optional_date("status_date", ctx.upload_date)
    admission_date = row.optional_date("admission_date", ctx.upload_date)

    # eligibility markers (D41): stored as reported, checked by the Seat Ledger
    eligibility = {column: row.marker(column) for column in ELIGIBILITY_COLUMNS}

    # APAAR and consent (ENGINES.md §5 rules 3 and 4)
    apaar_raw = row.get("apaar_id")
    problem = apaar_problem(apaar_raw)
    apaar: str | None = None
    stored_problem: str | None = None
    consent = consent_given
    if problem is not None:
        row.add(WARNING, "apaar_id", "APAAR_FORMAT", "APAAR must be 12 digits")
    if apaar_raw and problem is None:
        if consent_given in (None, ConsentStatus.LINKED):
            consent = ConsentStatus.LINKED
            apaar = apaar_raw.replace(" ", "")
        else:
            row.add(WARNING, "consent_status", "CONSENT_CONFLICT", consent_conflict(consent_given))
    elif apaar_raw:
        would_use = consent_given is ConsentStatus.LINKED or (
            consent_given is None and not international_row
        )
        if would_use:
            stored_problem = problem
            consent = ConsentStatus.PENDING
        elif consent_given is not None:
            row.add(WARNING, "consent_status", "CONSENT_CONFLICT", consent_conflict(consent_given))
    elif consent_given is ConsentStatus.LINKED:
        consent = ConsentStatus.PENDING
        row.add(
            WARNING,
            "consent_status",
            "CONSENT_CONFLICT",
            "Consent is Linked but no APAAR was given; recorded as Pending",
        )
    if consent is None:
        consent = ConsentStatus.INTERNATIONAL if international_row else ConsentStatus.PENDING

    if row.rejected:
        return None, row.issues
    assert dob and programme and year_of_study and cohort and route and category
    return (
        CleanRow(
            row_no=raw.row_no,
            name=row.get("name")[:NAME_MAX],
            dob=dob,
            programme_id=programme.id,
            programme_code=programme.code,
            year_of_study=year_of_study,
            cohort_year=cohort,
            admission_route=route,
            category=category,
            consent_status=consent,
            apaar_id=apaar,
            apaar_problem=stored_problem,
            gender=gender,
            mobile=mobile,
            email=email,
            address=row.get("address") or None,
            nationality=nationality,
            passport_no=passport,
            counselling_ref=row.get("counselling_ref") or None,
            status=status,
            status_raw=row.get("status"),
            status_date=status_date,
            admission_date=admission_date,
            eligibility=eligibility,
            raw=row.masked,
        ),
        row.issues,
    )


def validate_rows(parsed: ParsedUpload, ctx: ValidationContext) -> ValidationResult:
    result = ValidationResult()
    for raw in parsed.rows:
        clean, issues = validate_row(raw, ctx)
        result.issues.extend(issues)
        if clean is None:
            result.rejected.append(raw.row_no)
        else:
            result.rows.append(clean)
    return result


def file_duplicates(rows: list[CleanRow], normalise_name: Callable[[str], str]) -> ValidationResult:
    """The same student twice in one file: the later row is rejected with DUPLICATE_IN_FILE.

    Keys, first match wins: the APAAR used as identity, then the passport number, then
    (normalised name, date of birth, mobile) for rows without either.
    """
    result = ValidationResult()
    by_apaar: dict[str, int] = {}
    by_passport: dict[str, int] = {}
    by_person: dict[tuple[str, date, str], int] = {}
    for row in rows:
        issue: RowIssue | None = None
        person = (normalise_name(row.name), row.dob, row.mobile or "")
        if row.apaar_id and row.apaar_id in by_apaar:
            issue = _duplicate(
                row, "apaar_id", f"Same APAAR appears on row {by_apaar[row.apaar_id]}"
            )
        elif row.passport_no and row.passport_no in by_passport:
            issue = _duplicate(
                row,
                "passport_no",
                f"Same passport number appears on row {by_passport[row.passport_no]}",
            )
        elif not row.apaar_id and not row.passport_no and person in by_person:
            issue = _duplicate(
                row,
                "name",
                f"Same student (name, date of birth and mobile) appears on row {by_person[person]}",
            )
        if issue is not None:
            result.issues.append(issue)
            result.rejected.append(row.row_no)
            continue
        if row.apaar_id:
            by_apaar[row.apaar_id] = row.row_no
        if row.passport_no:
            by_passport.setdefault(row.passport_no, row.row_no)
        if not row.apaar_id and not row.passport_no:
            by_person[person] = row.row_no
        result.rows.append(row)
    return result


def _duplicate(row: CleanRow, column: str, message: str) -> RowIssue:
    value = {"apaar_id": row.apaar_id, "passport_no": row.passport_no, "name": row.name}[column]
    return RowIssue(
        row_no=row.row_no,
        level=ERROR,
        field=column,
        code="DUPLICATE_IN_FILE",
        message=message,
        value_masked=mask_value(column, value),
        raw=row.raw,
    )
