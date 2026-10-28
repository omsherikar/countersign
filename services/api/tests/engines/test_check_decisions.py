"""The five check decision tables (ENGINES.md section 8, D18) on hand-made subjects."""

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
        (ApaarResult(exists=False, name_score=0, dob_match=False), "FAIL", "INVALID_APAAR", "HIGH"),
        (
            ApaarResult(exists=True, name_score=100, dob_match=False),
            "FAIL",
            "NAME_MISMATCH",
            "MEDIUM",
        ),
        (ApaarResult(exists=True, name_score=90, dob_match=True), "PASS", None, None),
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
            "FAIL",
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


async def test_identity_without_a_call() -> None:
    gov = adapters()
    intl = await identity.evaluate(
        subject(admission_route=AdmissionRoute.INTERNATIONAL, apaar_id=None), gov, GATE
    )
    assert intl.status is CheckStatus.NA and intl.calls == ()
    assert intl.detail["summary"].startswith("International student")
    refused = await identity.evaluate(
        subject(apaar_id=None, apaar_last4=None, consent_status=ConsentStatus.REFUSED), gov, GATE
    )
    assert refused.status is CheckStatus.NA
    assert refused.detail == {"summary": "APAAR not linked; admission is not blocked."}
    malformed = await identity.evaluate(
        subject(apaar_id=None, apaar_problem="has 11 digits, expected 12"), gov, GATE
    )
    assert malformed.status is CheckStatus.FAIL
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
    assert outcome.status is CheckStatus.PASS
    assert outcome.detail == {
        "summary": "Name and date of birth match the APAAR registry (similarity 100 of 100).",
        "name_score": 100,
        "dob_match": True,
        "apaar_last4": "4417",
    }


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
    assert outcome.status is CheckStatus.PENDING
    assert outcome.detail["source_unavailable"] is True
    assert outcome.detail["summary"] == (
        "APAAR registry did not respond. "
        "This check stays pending until a recheck or the next upload."
    )
    for key, value in keys.items():
        assert outcome.detail[key] == value
    assert outcome.unavailable == ("APAAR",)
    assert outcome.flags == ()


# --------------------------------------------------------------------- ADMISSION


async def test_counselling_list() -> None:
    gov = adapters()
    row = {
        "state": "MH",
        "year": 2026,
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "roll_no": "MHCET-2026-004512",
        "programme": "CSE",
        "institution_aicte_id": "1-ABC-0001",
        "round": 1,
        "category": "GENERAL",
        "allotment_ref": "MHCET-2026-R1-004512",
    }
    gov.counselling.allotments.append(row)
    found = await admission.evaluate(subject(), gov, GATE)
    assert found.status is CheckStatus.PASS and found.source == "COUNSELLING"
    assert found.detail["summary"] == (
        "Found in the Maharashtra counselling allotments for CSE (2026), round 1."
    )
    assert found.detail["ref_mismatch"] is False
    differs = await admission.evaluate(subject(counselling_ref="MHCET-2026-R1-999999"), gov, GATE)
    assert differs.status is CheckStatus.PASS and differs.detail["ref_mismatch"] is True
    missing = await admission.evaluate(subject(name_normalised="someone else"), gov, GATE)
    assert missing.status is CheckStatus.FAIL
    assert missing.detail["summary"] == (
        "Not found in the Maharashtra counselling allotments for CSE (2026)."
    )
    gov.counselling.down = True
    down = await admission.evaluate(subject(), gov, GATE)
    assert down.status is CheckStatus.PENDING and down.unavailable == ("COUNSELLING",)


async def test_lateral_and_tfw_use_the_counselling_list() -> None:
    gov = adapters()
    for route in (AdmissionRoute.LATERAL, AdmissionRoute.TFW):
        outcome = await admission.evaluate(subject(admission_route=route), gov, GATE)
        assert outcome.source == "COUNSELLING"
        assert outcome.calls == ("COUNSELLING",)


async def test_seat_type_rules() -> None:
    gov = adapters()
    held = await admission.evaluate(subject(admission_route=AdmissionRoute.MANAGEMENT), gov, GATE)
    assert held.status is CheckStatus.PASS and held.source == "SEAT_LEDGER" and held.calls == ()
    assert held.detail["summary"] == (
        "Management admission is allowed for CSE and holds a Regular seat."
    )
    no_seat = await admission.evaluate(
        subject(admission_route=AdmissionRoute.SPOT, seat_code=None, seat_type=None), gov, GATE
    )
    assert no_seat.status is CheckStatus.FAIL
    assert no_seat.detail["summary"] == "Spot admission has no Regular seat in CSE (2026-27)."
    no_pool = await admission.evaluate(
        subject(
            admission_route=AdmissionRoute.NRI,
            target_seat_type=SeatType.NRI,
            target_capacity=0,
            seat_code=None,
            seat_type=None,
        ),
        gov,
        GATE,
    )
    assert no_pool.detail["summary"] == (
        "NRI admission is not allowed for CSE: the 2026-27 approval has no NRI seats."
    )


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
    assert ok.status is CheckStatus.PASS and ok.source == "SII"
    assert ok.detail["summary"] == "Study in India confirms this admission to CSE (2026-27)."
    other = await admission.evaluate(subject(**{**intl, "programme_code": "IT"}), gov, GATE)
    assert other.status is CheckStatus.FAIL
    gov.sii.down = True
    assert (await admission.evaluate(subject(**intl), gov, GATE)).status is CheckStatus.PENDING


# -------------------------------------------------------------------------- SEAT


def test_seat_decision() -> None:
    held = seat.decide(subject())
    assert held.status is CheckStatus.PASS
    assert held.detail["summary"] == "Holds seat CSE-R-001 (Regular, 2026-27 approval)."
    other_year = seat.decide(subject(seat_in_cohort_approval=False))
    assert other_year.status is CheckStatus.FAIL
    missing = seat.decide(subject(seat_code=None, seat_type=None))
    assert missing.detail["flag_type"] == "EXCESS_ADMISSION"
    assert missing.detail["flag_dedupe_key"] == f"EXCESS_ADMISSION:{P_ID}:2026-27:REGULAR"
    assert missing.flags == ()  # the FLAGS stage raises it
    nri = seat.decide(subject(seat_code=None, seat_type=None, target_seat_type=SeatType.NRI))
    assert nri.detail["flag_dedupe_key"] == f"QUOTA_BREACH:{P_ID}:2026-27:NRI"


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
    assert first.status is CheckStatus.NA and first.calls == ()
    assert first.detail == {"summary": "First year, no result yet."}
    second = subject(year_of_study=2, cohort_year="2025-26", apaar_id=None)
    no_apaar = await studying.evaluate(second, gov, GATE)
    assert no_apaar.detail == {"summary": "APAAR not linked; ABC credits cannot be checked."}
    unknown = await studying.evaluate(dataclasses.replace(second, apaar_id="999"), gov, GATE)
    assert unknown.status is CheckStatus.NA and unknown.calls == ("ABC",)
    assert unknown.detail["summary"] == "ABC has no record of this APAAR; see the Identity check."


async def test_studying_second_year_with_two_zero_credit_semesters_fails() -> None:
    gov = adapters()
    _abc(gov, **{"2025_26": [(1, 0), (2, 0)]})
    outcome = await studying.evaluate(subject(year_of_study=2, cohort_year="2025-26"), gov, GATE)
    assert outcome.status is CheckStatus.FAIL
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
    assert ok.status is CheckStatus.PASS
    assert ok.calls == ("ABC", "ABC")
    assert ok.detail["summary"] == "Credits recorded in ABC for all 4 semesters since admission."
    _abc(gov, **{"2024_25": [(1, 22), (2, 24)], "2025_26": [(3, 20)]})
    waiting = await studying.evaluate(third, gov, GATE)
    assert waiting.status is CheckStatus.PENDING
    assert waiting.detail["awaiting_semester"] == 4
    assert waiting.flags == ()
    gov.abc.down = True
    down = await studying.evaluate(third, gov, GATE)
    assert down.status is CheckStatus.PENDING and down.unavailable == ("ABC",)


async def test_student_is_pending_until_the_notice() -> None:
    outcome = await student.evaluate(subject(), adapters(), GATE)
    assert outcome.status is CheckStatus.PENDING
    assert outcome.source == "STUDENT_NOTICE"
    assert outcome.detail == {"summary": "Notice not sent yet."}


def test_semester_shape() -> None:
    assert Semester(sem=1, credits=0, uploaded_at=None, result="FAIL").credits == 0
    assert AbcResult(apaar_id_known=True).semesters == []
