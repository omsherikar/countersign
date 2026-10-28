"""Every row error code of API_CONTRACT §A2.3, with its level, field, message and masked value."""

import uuid
from datetime import date

import pytest

from app.engine.upload.mask import mask_value
from app.engine.upload.types import (
    UPLOAD_COLUMNS,
    ParsedUpload,
    ProgrammeInfo,
    RawRow,
    ValidationContext,
)
from app.engine.upload.validate import apaar_problem, file_duplicates, validate_row, validate_rows
from app.models.enums import (
    AdmissionRoute,
    Category,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
)
from tests.pipeline.fakes import FakeEngines

CSE = ProgrammeInfo(uuid.uuid4(), "CSE", 4, frozenset({"2025-26", "2026-27"}))
MBA = ProgrammeInfo(uuid.uuid4(), "MBA", 2, frozenset({"2026-27"}))
CTX = ValidationContext(
    institution_aicte_id="1-ABC-0001",
    academic_year="2026-27",
    upload_date=date(2026, 10, 28),
    programmes={"CSE": CSE, "MBA": MBA},
)
GOOD = {
    "apaar_id": "123456784417",
    "name": "Ravi Kumar Sharma",
    "dob": "2007-03-21",
    "gender": "M",
    "mobile": "9876504521",
    "email": "ravi.sharma@example.demo",
    "address": "12 Shivaji Nagar, Pune",
    "nationality": "IN",
    "programme_code": "CSE",
    "academic_year": "2026-27",
    "year_of_study": "1",
    "admission_route": "COUNSELLING",
    "counselling_ref": "MHCET-2026-R1-004512",
    "category": "GENERAL",
    "consent_status": "LINKED",
}


def row(row_no: int = 2, **changes: str) -> RawRow:
    values = dict.fromkeys(UPLOAD_COLUMNS, "")
    values.update(GOOD)
    values.update(changes)
    return RawRow(row_no=row_no, values=values)


def issues(**changes: str) -> list[tuple]:
    _, found = validate_row(row(**changes), CTX)
    return [(i.level.value, i.field, i.code, i.message, i.value_masked) for i in found]


def test_a_good_row_is_parsed():
    clean, found = validate_row(row(), CTX)
    assert found == []
    assert clean.name == "Ravi Kumar Sharma" and clean.dob == date(2007, 3, 21)
    assert clean.programme_id == CSE.id and clean.cohort_year == "2026-27"
    assert clean.admission_route is AdmissionRoute.COUNSELLING
    assert clean.category is Category.GENERAL
    assert clean.consent_status is ConsentStatus.LINKED and clean.apaar_id == "123456784417"
    assert clean.gender is Gender.M and clean.mobile == "9876504521"
    assert clean.status is None and clean.admission_date is None
    assert clean.raw == {
        "apaar_id": "XXXX XXXX 4417",
        "name": "Ravi Kumar Sharma",
        "programme_code": "CSE",
        "academic_year": "2026-27",
        "admission_route": "COUNSELLING",
    }


def test_lenient_forms_are_accepted():
    clean, found = validate_row(
        row(
            apaar_id="1234 5678 4417",
            admission_route="counselling",
            category="general",
            gender="Female",
            mobile="+91 98765 04521",
            nationality="in",
            programme_code="cse",
            academic_year="",
            consent_status="",
            status="Withdrawn",
            status_date="2026-10-20",
            admission_date="2026-08-02",
        ),
        CTX,
    )
    assert found == []
    assert clean.apaar_id == "123456784417" and clean.consent_status is ConsentStatus.LINKED
    assert clean.gender is Gender.F and clean.mobile == "9876504521" and clean.nationality == "IN"
    assert clean.status is EnrolmentStatus.WITHDRAWN and clean.status_date == date(2026, 10, 20)
    assert clean.admission_date == date(2026, 8, 2)
    assert validate_row(row(mobile="09876504521"), CTX)[0].mobile == "9876504521"
    assert validate_row(row(admission_route="spot"), CTX)[0].admission_route is AdmissionRoute.SPOT


@pytest.mark.parametrize(
    ("column", "word"),
    [
        ("name", "Name"),
        ("dob", "Date of birth"),
        ("programme_code", "Programme code"),
        ("year_of_study", "Year of study"),
        ("admission_route", "Admission route"),
        ("category", "Category"),
    ],
)
def test_missing_required(column, word):
    assert ("ERROR", column, "MISSING_REQUIRED", f"{word} is required", None) in issues(
        **{column: ""}
    )


def test_apaar_format_is_a_warning_and_keeps_the_row():
    clean, found = validate_row(row(apaar_id="12345678441"), CTX)
    assert [(i.level.value, i.field, i.code, i.message, i.value_masked) for i in found] == [
        ("WARNING", "apaar_id", "APAAR_FORMAT", "APAAR must be 12 digits", "<11 characters>")
    ]
    assert clean is not None and clean.apaar_id is None
    assert clean.apaar_problem == "has 11 digits, expected 12"
    assert clean.consent_status is ConsentStatus.PENDING  # not CONSENT_CONFLICT
    letters, _ = validate_row(row(apaar_id="2026000003A09", consent_status=""), CTX)
    assert letters.apaar_problem == "contains characters other than digits"
    assert letters.consent_status is ConsentStatus.PENDING
    assert apaar_problem("") is None and apaar_problem("1234 5678 4417") is None


def test_unknown_programme_and_no_approval_for_cohort():
    assert issues(programme_code="ME") == [
        (
            "ERROR",
            "programme_code",
            "UNKNOWN_PROGRAMME",
            "Programme code ME is not approved for your college",
            "ME",
        )
    ]
    assert issues(programme_code="MBA", year_of_study="2", dob="2003-01-01") == [
        (
            "ERROR",
            "year_of_study",
            "NO_APPROVAL_FOR_COHORT",
            "MBA has no approval for 2025-26, the intake of a year 2 student in 2026-27",
            "2",
        )
    ]


def test_dates_of_birth():
    assert issues(dob="21/03/2007") == [
        ("ERROR", "dob", "DOB_FORMAT", "Date of birth must be YYYY-MM-DD", "21/03/2007")
    ]
    assert issues(dob="2007-02-30")[0][2] == "DOB_FORMAT"
    assert issues(dob="2020-01-01") == [
        (
            "ERROR",
            "dob",
            "DOB_IMPLAUSIBLE",
            "Date of birth 2020-01-01 gives an age of 6 at admission; expected 14 to 60",
            "2020-01-01",
        )
    ]
    assert issues(dob="1950-01-01")[0][3].endswith("an age of 76 at admission; expected 14 to 60")
    assert issues(dob="2027-01-01")[0][2] == "DOB_IMPLAUSIBLE"
    # age is taken on 1 July of the cohort start year: a year-2 row started in 2025
    assert issues(dob="2011-06-30", year_of_study="2") == []
    assert issues(dob="2011-07-02", year_of_study="2")[0][3] == (
        "Date of birth 2011-07-02 gives an age of 13 at admission; expected 14 to 60"
    )


def test_bad_enums():
    assert issues(admission_route="Quota") == [
        (
            "ERROR",
            "admission_route",
            "BAD_ENUM",
            "Admission route must be one of Counselling, Management, NRI, Spot, Lateral, "
            "International, TFW",
            "Quota",
        )
    ]
    assert issues(category="BC") == [
        ("ERROR", "category", "BAD_ENUM",
         "Category must be one of General, EWS, OBC, SC, ST, Other", "BC")
    ]  # fmt: skip
    assert issues(consent_status="Yes") == [
        (
            "ERROR",
            "consent_status",
            "BAD_ENUM",
            "Consent status must be Linked, Refused, Pending or International",
            "Yes",
        )
    ]
    for status in ("Graduated", "left"):
        assert issues(status=status) == [
            ("ERROR", "status", "BAD_ENUM", "Status must be Active, Withdrawn or Transferred",
             status)
        ]  # fmt: skip
    clean, found = validate_row(row(gender="X"), CTX)
    assert [(i.level.value, i.code, i.message) for i in found] == [
        ("WARNING", "BAD_ENUM", "Gender must be M, F, O or U; recorded as U")
    ]
    assert clean.gender is Gender.U


def test_year_of_study_and_academic_year():
    for value in ("0", "5", "1.5", "one"):
        assert issues(year_of_study=value) == [
            ("ERROR", "year_of_study", "YEAR_OF_STUDY_INVALID",
             "Year of study must be a whole number between 1 and 4", value)
        ]  # fmt: skip
    unknown = issues(programme_code="ME", year_of_study="7")
    assert ("ERROR", "year_of_study", "YEAR_OF_STUDY_INVALID",
            "Year of study must be a whole number between 1 and 6", "7") in unknown  # fmt: skip
    assert issues(academic_year="2025-26") == [
        (
            "ERROR",
            "academic_year",
            "YEAR_MISMATCH",
            "Academic year 2025-26 does not match this upload's academic year 2026-27",
            "2025-26",
        )
    ]


def test_passport_and_nationality():
    msg = ("ERROR", "passport_no", "PASSPORT_REQUIRED",
           "International students need a passport number", None)  # fmt: skip
    assert msg in issues(apaar_id="", admission_route="INTERNATIONAL", consent_status="")
    assert msg in issues(apaar_id="", consent_status="INTERNATIONAL")
    assert msg in issues(apaar_id="", nationality="BD", consent_status="")
    assert issues(nationality="IND") == [
        (
            "ERROR",
            "nationality",
            "NATIONALITY_FORMAT",
            "Nationality must be a two-letter country code, e.g. IN",
            "IND",
        )
    ]
    clean, found = validate_row(
        row(
            apaar_id="",
            nationality="BD",
            passport_no="n 1234567",
            admission_route="INTERNATIONAL",
            consent_status="",
        ),
        CTX,
    )
    assert found == [] and clean.passport_no == "N1234567"
    assert clean.consent_status is ConsentStatus.INTERNATIONAL and clean.nationality == "BD"
    ciwg, found = validate_row(
        row(
            apaar_id="", admission_route="INTERNATIONAL", passport_no="Z7654321", consent_status=""
        ),  # fmt: skip
        CTX,
    )
    assert found == [] and ciwg.effective_nationality == "IN"


def test_status_and_admission_dates():
    assert issues(status_date="20-10-2026") == [
        ("ERROR", "status_date", "DATE_FORMAT", "Status date must be YYYY-MM-DD", "20-10-2026")
    ]
    assert issues(admission_date="2026/08/02") == [
        ("ERROR", "admission_date", "DATE_FORMAT", "Admission date must be YYYY-MM-DD",
         "2026/08/02")
    ]  # fmt: skip
    assert issues(status_date="2026-10-29") == [
        ("ERROR", "status_date", "DATE_IN_FUTURE",
         "Status date 2026-10-29 is after the upload date", "2026-10-29")
    ]  # fmt: skip
    assert issues(admission_date="2026-11-01") == [
        ("ERROR", "admission_date", "DATE_IN_FUTURE",
         "Admission date 2026-11-01 is after the upload date", "2026-11-01")
    ]  # fmt: skip
    assert issues(status_date="2026-10-28", admission_date="2026-10-28") == []


def test_contact_warnings_mask_values():
    clean, found = validate_row(row(mobile="98765", email="ravi.sharma@example"), CTX)
    assert [(i.level.value, i.field, i.code, i.message, i.value_masked) for i in found] == [
        ("WARNING", "mobile", "MOBILE_FORMAT", "Mobile must be 10 digits; the value was not used",
         "XXXXXX8765"),
        ("WARNING", "email", "EMAIL_FORMAT", "Email address is not valid; the value was not used",
         "r***@example"),
    ]  # fmt: skip
    assert clean.mobile is None and clean.email is None
    assert issues(mobile="981")[0][4] == "<3 characters>"
    assert issues(email="a@b@c.d")[0][2] == "EMAIL_FORMAT"


def test_consent_conflicts():
    pairs = (("REFUSED", "Refused"), ("pending", "Pending"), ("International", "International"))
    for consent, word in pairs:
        changes = {"consent_status": consent}
        if consent == "International":
            changes["passport_no"] = "N1234567"
        clean, found = validate_row(row(**changes), CTX)
        assert [(i.level.value, i.field, i.code, i.message) for i in found] == [
            ("WARNING", "consent_status", "CONSENT_CONFLICT",
             f"APAAR given but consent is {word}; the APAAR was not used")
        ]  # fmt: skip
        assert clean.apaar_id is None and clean.consent_status.value == consent.upper()
    clean, found = validate_row(row(apaar_id=""), CTX)
    assert [(i.code, i.message) for i in found] == [
        ("CONSENT_CONFLICT", "Consent is Linked but no APAAR was given; recorded as Pending")
    ]
    assert clean.consent_status is ConsentStatus.PENDING
    blank, found = validate_row(row(apaar_id="", consent_status=""), CTX)
    assert found == [] and blank.consent_status is ConsentStatus.PENDING


def test_every_problem_in_a_row_is_reported_once_per_field():
    clean, found = validate_row(
        row(
            name="",
            dob="yesterday",
            programme_code="ME",
            year_of_study="9",
            admission_route="x",
            category="",
            mobile="1",
            apaar_id="123",
        ),
        CTX,
    )
    assert clean is None
    fields = [i.field for i in found]
    assert len(fields) == len(set(fields))
    assert set(fields) == {
        "name", "dob", "programme_code", "year_of_study", "admission_route", "category",
        "mobile", "apaar_id",
    }  # fmt: skip
    assert all(i.raw["apaar_id"] == "<3 characters>" for i in found)


def test_validate_rows_splits_accepted_and_rejected():
    parsed = ParsedUpload(rows=[row(2), row(3, name=""), row(4, mobile="1")])
    result = validate_rows(parsed, CTX)
    assert [r.row_no for r in result.rows] == [2, 4] and result.rejected == [3]
    assert [(i.row_no, i.code) for i in result.issues] == [
        (3, "MISSING_REQUIRED"),
        (4, "MOBILE_FORMAT"),
    ]


def test_duplicates_in_file():
    norm = FakeEngines().normalise_name
    rows = [
        validate_row(row(2), CTX)[0],
        validate_row(row(3, name="Someone Else"), CTX)[0],  # same APAAR
        validate_row(
            row(4, apaar_id="", consent_status="", nationality="BD", passport_no="N1234567",
                admission_route="INTERNATIONAL", name="Aisha Rahman", dob="2006-07-07"),
            CTX,
        )[0],
        validate_row(
            row(5, apaar_id="", consent_status="", nationality="BD", passport_no="n1234567",
                admission_route="INTERNATIONAL", name="Aisha R", dob="2006-07-07"),
            CTX,
        )[0],
        validate_row(row(6, apaar_id="", consent_status="", name="R. K. Sharma"), CTX)[0],
        validate_row(row(7, apaar_id="", consent_status="", name="r k sharma"), CTX)[0],
        validate_row(row(8, apaar_id="", consent_status="", name="R K Sharma", mobile=""), CTX)[0],
        validate_row(row(9, apaar_id="", consent_status="", name="R K Sharma", mobile=""), CTX)[0],
    ]  # fmt: skip
    result = file_duplicates(rows, norm)
    assert [r.row_no for r in result.rows] == [2, 4, 6, 8]
    assert result.rejected == [3, 5, 7, 9]
    assert [(i.row_no, i.level.value, i.field, i.code, i.message, i.value_masked)
            for i in result.issues] == [
        (3, "ERROR", "apaar_id", "DUPLICATE_IN_FILE", "Same APAAR appears on row 2",
         "XXXX XXXX 4417"),
        (5, "ERROR", "passport_no", "DUPLICATE_IN_FILE",
         "Same passport number appears on row 4", "XXXXX567"),
        (7, "ERROR", "name", "DUPLICATE_IN_FILE",
         "Same student (name, date of birth and mobile) appears on row 6", "r k sharma"),
        (9, "ERROR", "name", "DUPLICATE_IN_FILE",
         "Same student (name, date of birth and mobile) appears on row 8", "R K Sharma"),
    ]  # fmt: skip


def test_mask_value():
    assert mask_value("apaar_id", "1234 5678 4417") == "XXXX XXXX 4417"
    assert mask_value("apaar_id", "2026000003A09") == "<13 characters>"
    assert mask_value("apaar_id", "1") == "<1 character>"
    assert mask_value("passport_no", "N1234567") == "XXXXX567"
    assert mask_value("mobile", "9876504521") == "XXXXXX4521"
    assert mask_value("email", "ravi@example.com") == "r***@example.com"
    assert mask_value("email", "nonsense") == "n***"
    assert mask_value("address", "12 Shivaji Nagar") is None
    assert mask_value("name", "x" * 80) == "x" * 64
    assert mask_value("name", "  ") is None
