"""The five row decision tables (ENGINES.md sections 8 and 17.3, API_CONTRACT §A4.4) on
hand-made subjects."""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from datetime import date

import pytest

from app.adapters.base import (
    AbcResult,
    AdapterRequestError,
    ApaarResult,
    RealAdapterDisabled,
    Semester,
    SourceUnavailable,
)
from app.engine.checks import admission, identity, seat, student, studying
from app.engine.checks.base import CheckSubject
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    ConsentStatus,
    EnrolmentStatus,
    FlagType,
    ProgrammeLevel,
    ProgrammeMode,
    SeatType,
    Severity,
)
from tests.engines.conftest import adapters

GATE = asyncio.Semaphore(4)
E_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
P_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def subject(**overrides) -> CheckSubject:
    base = CheckSubject(
        enrolment_id=E_ID,
        student_id=uuid.uuid4(),
        institution_id=uuid.uuid4(),
        institution_aicte_id="1-ABC-0001",
        institution_name="ABC College of Engineering",
        state_code="MH",
        state_name="Maharashtra",
        programme_id=P_ID,
        programme_code="CSE",
        programme_mode=ProgrammeMode.PHYSICAL,
        programme_level=ProgrammeLevel.UG,
        academic_year="2026-27",
        cohort_year="2026-27",
        year_of_study=1,
        admission_route=AdmissionRoute.COUNSELLING,
        counselling_ref="MHCET-2026-R1-004512",
        status=EnrolmentStatus.ACTIVE,
        seat_code="CSE-R-001",
        seat_type=SeatType.REGULAR,
        seat_in_cohort_approval=True,
        target_seat_type=SeatType.REGULAR,
        target_capacity=114,
        name="Ravi Kumar Sharma",
        name_normalised="ravi kumar sharma",
        dob=date(2007, 3, 21),
        nationality="IN",
        consent_status=ConsentStatus.LINKED,
        apaar_last4="4417",
        apaar_problem=None,
        apaar_problem_masked=None,
        checked_on=date(2026, 10, 28),
        apaar_id="123456784417",
        passport_no=None,
    )
    return dataclasses.replace(base, **overrides)


# ---------------------------------------------------------------------- IDENTITY


@pytest.mark.parametrize(
    ("result", "status", "flag", "severity"),
    [
        (
            ApaarResult(exists=False, name_score=0, dob_match=False),
            "CONTRADICTED",
            "INVALID_APAAR",
            "HIGH",
        ),
        (
            ApaarResult(exists=True, name_score=100, dob_match=False),
            "CONTRADICTED",
            "NAME_MISMATCH",
            "MEDIUM",
        ),
        (ApaarResult(exists=True, name_score=90, dob_match=True), "CONFIRMED", None, None),
        (
            ApaarResult(exists=True, name_score=89, dob_match=True),
            "PENDING",
            "NAME_MISMATCH",
            "LOW",
        ),
        (
            ApaarResult(exists=True, name_score=75, dob_match=True),
            "PENDING",
            "NAME_MISMATCH",
            "LOW",
        ),
        (
            ApaarResult(exists=True, name_score=74, dob_match=True),
            "CONTRADICTED",
            "NAME_MISMATCH",
            "MEDIUM",
        ),
    ],
)
def test_identity_decision_table(result, status, flag, severity) -> None:
    outcome = identity.decide(subject(), result)
    assert outcome.status.value == status
    assert outcome.source == "APAAR"
    assert outcome.calls == ("APAAR",)
    if flag is None:
        assert outcome.flags == ()
    else:
        [intent] = outcome.flags
        assert (intent.type.value, intent.severity.value) == (flag, severity)
        assert intent.dedupe_key == f"{flag}:{E_ID}"
        assert intent.enrolment_id == E_ID and intent.programme_id == P_ID
        assert intent.academic_year == "2026-27"
    assert "123456784417" not in str(outcome.detail)


def test_identity_review_detail() -> None:
    outcome = identity.decide(subject(), ApaarResult(exists=True, name_score=81, dob_match=True))
    assert outcome.detail["needs_review"] is True
    assert outcome.detail["name_score"] == 81
    [intent] = outcome.flags
    facts = {f["label"]: f["value"] for f in intent.evidence["facts"]}
    assert facts["Name on upload"] == "Ravi Kumar Sharma"
    assert facts["Checked at"] == "28 Oct 2026"


async def test_identity_without_a_registry_call() -> None:
    gov = adapters()
    # an international student without a passport on record: Study in India cannot be asked
    intl = await identity.evaluate(
        subject(admission_route=AdmissionRoute.INTERNATIONAL, apaar_id=None), gov, GATE
    )
    assert (intl.status, intl.calls, intl.detail["basis"]) == (
        CheckStatus.PENDING,
        (),
        "SII_NONE",
    )
    refused = await identity.evaluate(
        subject(apaar_id=None, apaar_last4=None, consent_status=ConsentStatus.REFUSED), gov, GATE
    )
    assert refused.status is CheckStatus.NOT_APPLICABLE
    assert (refused.detail["basis"], refused.supplied_by, refused.independent) == (
        "NO_APAAR",
        "",
        False,
    )
    claimed = await identity.evaluate(
        subject(
            apaar_id=None,
            apaar_last4=None,
            consent_status=ConsentStatus.REFUSED,
            digilocker_claimed=True,
        ),
        gov,
        GATE,
    )
    assert (claimed.status, claimed.source, claimed.detail["basis"]) == (
        CheckStatus.CONFIRMED,
        "DIGILOCKER",
        "DIGILOCKER_CLAIM",
    )
    assert (claimed.supplied_by, claimed.independent) == ("Student via DigiLocker sign-in", True)
    malformed = await identity.evaluate(
        subject(apaar_id=None, apaar_problem="has 11 digits, expected 12"), gov, GATE
    )
    assert malformed.status is CheckStatus.CONTRADICTED
    assert (malformed.supplied_by, malformed.independent) == ("College upload", False)
    [intent] = malformed.flags
    assert (intent.type, intent.severity) == (FlagType.INVALID_APAAR, Severity.MEDIUM)
    assert intent.evidence["summary"] == (
        "APAAR as uploaded has 11 digits, expected 12, so it could not be checked."
    )
    assert intent.evidence["facts"][0]["value"] == "<11 characters>"
    letters = await identity.evaluate(
        subject(
            apaar_id=None,
            apaar_problem="contains characters other than digits",
            apaar_problem_masked="<12 characters>",
        ),
        gov,
        GATE,
    )
    assert letters.flags[0].evidence["facts"][0]["value"] == "<12 characters>"


async def test_identity_against_the_registry() -> None:
    gov = adapters()
    gov.apaar.registry["123456784417"] = {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 21)}
    outcome = await identity.evaluate(subject(), gov, GATE)
    assert outcome.status is CheckStatus.CONFIRMED
    assert outcome.detail == {
        "summary": "Name and date of birth match the APAAR registry (similarity 100 of 100).",
        "finding": None,
        "source_line": "APAAR verification · {date}",
        "basis": "APAAR_MATCH",
        "name_score": 100,
        "dob_match": True,
        "apaar_last4": "4417",
    }
    assert (outcome.supplied_by, outcome.independent) == ("APAAR registry", True)


@pytest.mark.parametrize(
    ("error", "keys"),
    [
        (SourceUnavailable("apaar", "HTTP 503"), {"source_error": "HTTP 503"}),
        (RealAdapterDisabled("apaar"), {"source_disabled": True}),
        (AdapterRequestError("apaar", 422, "bad"), {"source_error": "HTTP 422"}),
    ],
)
async def test_source_errors_give_pending_never_fail(error, keys) -> None:
    class Broken:
        async def verify(self, *args, **kwargs):
            raise error

    gov = adapters()
    gov.apaar = Broken()
    outcome = await identity.evaluate(subject(), gov, GATE)
    assert outcome.status is CheckStatus.SOURCE_UNAVAILABLE
    assert outcome.detail["source_unavailable"] is True
    assert outcome.detail["summary"] == (
        "APAAR registry did not respond. "
        "This row is asked again at the next recheck or the next upload."
    )
    assert (outcome.supplied_by, outcome.independent) == ("APAAR registry", False)
    for key, value in keys.items():
        assert outcome.detail[key] == value
    assert outcome.unavailable == ("APAAR",)
    assert outcome.flags == ()


# --------------------------------------------------------------------- ADMISSION


def _joined(gov, **changes) -> None:
    row = {
        "state": "MH",
        "academic_year": "2026-27",
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "roll_no": "MHCET-2026-004512",
        "institution_code": "1-ABC-0001",
        "programme": "CSE",
        "joined_on": "2026-08-02",
        "round": 1,
        "route": "COUNSELLING",
        "category": "GENERAL",
        "apaar_id": "123456784417",
    }
    gov.admission_authority.add({**row, **changes})


async def test_the_joining_record() -> None:
    gov = adapters()
    _joined(gov)
    deadline = date(2026, 9, 30)
    found = await admission.evaluate(subject(joining_year="2026-27"), gov, GATE)
    assert found.status is CheckStatus.CONFIRMED and found.source == "ADMISSION_AUTHORITY"
    assert found.calls == ("ADMISSION_AUTHORITY",)
    assert found.detail["summary"] == (
        "The Maharashtra admission authority records that the student joined CSE at this "
        "college on 2 Aug (round 1)."
    )
    missing = subject(joining_year="2026-27", name_normalised="someone else")
    before = await admission.evaluate(
        dataclasses.replace(missing, checked_on=date(2026, 9, 1), reporting_deadline=deadline),
        gov,
        GATE,
    )
    assert (before.status, before.flags) == (CheckStatus.PENDING, ())
    after = await admission.evaluate(
        dataclasses.replace(missing, checked_on=date(2026, 10, 28), reporting_deadline=deadline),
        gov,
        GATE,
    )
    assert after.status is CheckStatus.CONTRADICTED
    [intent] = after.flags
    assert (intent.type, intent.severity) == (FlagType.NOT_IN_JOINING_RECORD, Severity.MEDIUM)
    assert intent.dedupe_key == f"NOT_IN_JOINING_RECORD:{E_ID}"
    gov.admission_authority.down = True
    down = await admission.evaluate(subject(joining_year="2026-27"), gov, GATE)
    assert down.status is CheckStatus.SOURCE_UNAVAILABLE
    assert (down.unavailable, down.flags) == (("ADMISSION_AUTHORITY",), ())


async def test_every_route_but_international_reads_the_joining_record() -> None:
    gov = adapters()
    for route in (
        AdmissionRoute.MANAGEMENT,
        AdmissionRoute.NRI,
        AdmissionRoute.SPOT,
        AdmissionRoute.LATERAL,
        AdmissionRoute.TFW,
    ):
        outcome = await admission.evaluate(subject(admission_route=route), gov, GATE)
        assert outcome.source == "ADMISSION_AUTHORITY"
        assert outcome.calls == ("ADMISSION_AUTHORITY",)


async def test_study_in_india() -> None:
    gov = adapters()
    gov.sii.admissions["N1234567"] = {
        "name": "Aisha Rahman",
        "nationality": "BD",
        "institution_aicte_id": "1-ABC-0001",
        "programme": "CSE",
        "academic_year": "2026-27",
    }
    intl = dict(
        admission_route=AdmissionRoute.INTERNATIONAL,
        nationality="BD",
        passport_no="N1234567",
        apaar_id=None,
        consent_status=ConsentStatus.INTERNATIONAL,
    )
    ok = await admission.evaluate(subject(**intl), gov, GATE)
    assert ok.status is CheckStatus.CONFIRMED and ok.source == "SII"
    assert ok.detail["summary"] == "Study in India confirms this admission to CSE (2026-27)."
    other = await admission.evaluate(subject(**{**intl, "programme_code": "IT"}), gov, GATE)
    assert other.status is CheckStatus.CONTRADICTED
    [intent] = other.flags
    assert intent.type is FlagType.NOT_IN_JOINING_RECORD
    gov.sii.down = True
    unavailable = await admission.evaluate(subject(**intl), gov, GATE)
    assert unavailable.status is CheckStatus.SOURCE_UNAVAILABLE


# -------------------------------------------------------------------------- SEAT


def test_seat_decision() -> None:
    held = seat.decide(subject(approval_version=2))
    assert held.status is CheckStatus.CONFIRMED
    assert held.detail["summary"] == "Holds seat CSE-R-001 (Regular, AICTE approval v2, 2026-27)."
    assert held.supplied_by == "AICTE approval v2, 2026-27 (Seat Ledger, derived)"
    other_year = seat.decide(subject(seat_in_cohort_approval=False))
    assert other_year.status is CheckStatus.CONTRADICTED
    missing = seat.decide(subject(seat_code=None, seat_type=None))
    assert missing.detail["flag_type"] == "EXCESS_ADMISSION"
    assert missing.detail["flag_dedupe_key"] == f"EXCESS_ADMISSION:{P_ID}:2026-27:REGULAR"
    assert missing.flags == ()  # the FLAGS stage raises it
    nri = seat.decide(subject(seat_code=None, seat_type=None, target_seat_type=SeatType.NRI))
    assert nri.detail["flag_dedupe_key"] == f"QUOTA_BREACH:{P_ID}:2026-27:NRI"
    no_pool = seat.decide(
        subject(
            admission_route=AdmissionRoute.NRI,
            target_seat_type=SeatType.NRI,
            target_capacity=0,
            seat_code=None,
            seat_type=None,
        )
    )
    assert no_pool.detail["summary"] == (
        "NRI admission is not allowed for CSE: approval v1 for 2026-27 has no NRI seats."
    )


# ---------------------------------------------------------------------- STUDYING


def _abc(gov, apaar="123456784417", **years) -> None:
    gov.abc.credits_by_apaar[apaar] = {
        year.replace("_", "-"): [
            {"sem": sem, "credits": credits, "uploaded_at": f"2026-0{sem}-20T00:00:00Z"}
            for sem, credits in sems
        ]
        for year, sems in years.items()
    }


async def test_studying_first_year_and_no_apaar() -> None:
    gov = adapters()
    first = await studying.evaluate(subject(), gov, GATE)
    assert first.status is CheckStatus.NOT_YET_DUE and first.calls == ()
    assert (first.detail["basis"], first.detail["summary"]) == (
        "FIRST_YEAR",
        "First year; no semester result is due yet.",
    )
    second = subject(year_of_study=2, cohort_year="2025-26", apaar_id=None)
    no_apaar = await studying.evaluate(second, gov, GATE)
    assert no_apaar.detail["summary"] == "APAAR not linked; ABC credits cannot be checked."
    unknown = await studying.evaluate(dataclasses.replace(second, apaar_id="999"), gov, GATE)
    assert unknown.status is CheckStatus.NOT_APPLICABLE and unknown.calls == ("ABC",)
    assert unknown.detail["summary"] == "ABC has no record of this APAAR; see the Identity row."


async def test_studying_second_year_with_two_zero_credit_semesters_fails() -> None:
    gov = adapters()
    _abc(gov, **{"2025_26": [(1, 0), (2, 0)]})
    outcome = await studying.evaluate(subject(year_of_study=2, cohort_year="2025-26"), gov, GATE)
    assert outcome.status is CheckStatus.CONTRADICTED
    assert outcome.detail["summary"] == (
        "No credits recorded in ABC for 2 of 2 semesters since admission."
    )
    [intent] = outcome.flags
    assert (intent.type, intent.severity) == (FlagType.NO_ACADEMIC_ACTIVITY, Severity.MEDIUM)
    assert intent.evidence["summary"] == (
        "No credits recorded in ABC for 2 semesters while enrolled in year 2."
    )


async def test_studying_counts_semesters_since_admission() -> None:
    gov = adapters()
    _abc(gov, **{"2024_25": [(1, 22), (2, 24)], "2025_26": [(3, 20), (4, 21)]})
    third = subject(year_of_study=3, cohort_year="2024-25")
    ok = await studying.evaluate(third, gov, GATE)
    assert ok.status is CheckStatus.CONFIRMED
    assert ok.calls == ("ABC", "ABC")
    assert ok.detail["summary"] == "Credits recorded in ABC for all 4 semesters since admission."
    _abc(gov, **{"2024_25": [(1, 22), (2, 24)], "2025_26": [(3, 20)]})
    waiting = await studying.evaluate(third, gov, GATE)
    assert waiting.status is CheckStatus.PENDING
    assert waiting.detail["awaiting_semester"] == 4
    assert waiting.flags == ()
    gov.abc.down = True
    down = await studying.evaluate(third, gov, GATE)
    assert down.status is CheckStatus.SOURCE_UNAVAILABLE and down.unavailable == ("ABC",)


async def test_studying_lateral_entrant_counts_from_year_two() -> None:
    gov = adapters()
    _abc(gov, **{"2025_26": [(1, 22), (2, 24)]})
    second = subject(year_of_study=2, cohort_year="2025-26", admission_route=AdmissionRoute.LATERAL)
    joined = await studying.evaluate(second, gov, GATE)
    assert joined.status is CheckStatus.NOT_YET_DUE and joined.calls == ()
    assert (joined.detail["basis"], joined.detail["summary"]) == (
        "LATERAL_FIRST_YEAR",
        "Lateral entry into year 2; no semester result here is due yet.",
    )
    no_apaar = await studying.evaluate(dataclasses.replace(second, apaar_id=None), gov, GATE)
    assert no_apaar.status is CheckStatus.NOT_YET_DUE and no_apaar.detail == joined.detail

    # year 3: only year 2 (2025-26, semesters 3 and 4) is asked for; year 1 was elsewhere
    third = subject(year_of_study=3, cohort_year="2024-25", admission_route=AdmissionRoute.LATERAL)
    _abc(gov, **{"2025_26": [(3, 20), (4, 21)]})
    ok = await studying.evaluate(third, gov, GATE)
    assert ok.status is CheckStatus.CONFIRMED and ok.calls == ("ABC",)
    assert ok.detail["summary"] == "Credits recorded in ABC for all 2 semesters since admission."
    assert ok.detail["semesters"] == [
        {"academic_year": "2025-26", "sem": 3, "credits": 20},
        {"academic_year": "2025-26", "sem": 4, "credits": 21},
    ]
    _abc(gov, **{"2025_26": [(3, 0), (4, 0)]})
    idle = await studying.evaluate(third, gov, GATE)
    assert idle.status is CheckStatus.CONTRADICTED
    assert idle.detail["summary"] == (
        "No credits recorded in ABC for 2 of 2 semesters since admission."
    )
    [intent] = idle.flags
    assert intent.type is FlagType.NO_ACADEMIC_ACTIVITY


async def test_student_is_pending_until_the_notice() -> None:
    outcome = await student.evaluate(subject(), adapters(), GATE)
    assert outcome.status is CheckStatus.PENDING
    assert outcome.source == "STUDENT_NOTICE"
    assert outcome.detail == {
        "summary": "Notice not sent yet.",
        "finding": "notice not sent yet",
        "source_line": "No notice sent yet",
        "basis": "NOT_SENT",
        "notice_state": "NOT_SENT",
    }


def test_semester_shape() -> None:
    assert Semester(sem=1, credits=0, uploaded_at=None, result="FAIL").credits == 0
    assert AbcResult(apaar_id_known=True).semesters == []
