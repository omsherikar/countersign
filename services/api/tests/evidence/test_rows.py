"""Rows carry their provenance and their sentences (D34, D38, D41; API_CONTRACT §A4.2, §A4.4).

observed_at stays while a later evaluation gives the same state and source, so the
"Source and date" line does not move on a re-run or an unchanged re-upload; the Seat row
cites the approval version and checks category eligibility; a claimed record's identity is
the student's own DigiLocker sign-in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.engine import checks as checks_module
from app.engine.checks import rerun, run_checks
from app.engine.ledger import assign_seats
from app.engine.status import STATUS_DIRTY
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    ConsentStatus,
    FlagType,
    Severity,
    UserRole,
)
from app.models.seat import SeatPool
from app.models.user import User
from app.models.verification import Check, Flag
from tests.conftest import PASSWORD
from tests.evidence.conftest import joining_row

DOB = date(2007, 3, 21)


async def _rows(session, enrolment) -> dict[CheckType, Check]:
    rows = await session.execute(
        select(Check)
        .where(Check.enrolment_id == enrolment.id)
        .execution_options(populate_existing=True)
    )
    return {c.type: c for c in rows.scalars()}


async def _ravi(world, session, gov, *, joined: bool = True):
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417")
    enrolment = await world.enrol(student, cse)
    gov.apaar.registry["123456784417"] = {"name": "Ravi Kumar Sharma", "dob": DOB}
    gov.admission_authority.add(
        joining_row(
            name="Ravi Kumar Sharma" if joined else "Somebody Else",
            dob=DOB,
            institution_code="1-ABC-0001",
        )
    )
    await assign_seats(session, [enrolment.id], actor_id=None)
    return enrolment


class _Later(datetime):
    """The clock two days on, for the second evaluation."""

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz) + timedelta(days=2)


async def test_observed_at_and_the_source_line_stay_while_nothing_changes(
    world, session, gov, monkeypatch
) -> None:
    enrolment = await _ravi(world, session, gov)
    await run_checks(session, [enrolment.id], gov)
    first = {
        t: (c.observed_at, c.detail["source_line"])
        for t, c in (await _rows(session, enrolment)).items()
    }

    monkeypatch.setattr(checks_module, "datetime", _Later)
    await run_checks(session, [enrolment.id], gov)
    again = {
        t: (c.observed_at, c.detail["source_line"])
        for t, c in (await _rows(session, enrolment)).items()
    }
    assert again == first

    # a change of state moves them
    gov.apaar.registry["123456784417"] = {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 22)}
    await run_checks(session, [enrolment.id], gov)
    identity = (await _rows(session, enrolment))[CheckType.IDENTITY]
    assert identity.status is CheckStatus.CONTRADICTED
    assert identity.observed_at > first[CheckType.IDENTITY][0]


async def test_rows_without_a_source_have_no_date(world, session, gov) -> None:
    enrolment = await _ravi(world, session, gov)
    await run_checks(session, [enrolment.id], gov)
    rows = await _rows(session, enrolment)
    for row_type in (CheckType.STUDYING, CheckType.STUDENT):
        assert (rows[row_type].supplied_by, rows[row_type].observed_at) == ("", None)
    assert rows[CheckType.STUDYING].detail["source_line"] == "First semester not complete"
    assert rows[CheckType.STUDENT].detail["source_line"] == "No notice sent yet"
    assert rows[CheckType.STUDENT].detail["finding"] == "notice not sent yet"
    assert all(
        set(r.detail) >= {"summary", "finding", "source_line", "basis"} for r in rows.values()
    )


# -------------------------------------------------------------------------- SEAT


async def _seated(world, session, gov, *, route, eligibility=None, nationality="IN", passport=None):
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst, intakes={"2026-27": 120})
    student = await world.student("Meera Iyer", DOB, nationality=nationality, passport=passport)
    enrolment = await world.enrol(student, cse, route=route, eligibility=eligibility)
    await assign_seats(session, [enrolment.id], actor_id=None)
    await run_checks(session, [enrolment.id], gov)
    seat = (await _rows(session, enrolment))[CheckType.SEAT]
    cases = (
        (await session.execute(select(Flag).where(Flag.type == FlagType.ELIGIBILITY_BREACH)))
        .scalars()
        .all()
    )
    return seat, list(cases)


async def test_a_seat_that_fits_cites_the_approval_version(world, session, gov) -> None:
    seat, cases = await _seated(
        world, session, gov, route=AdmissionRoute.NRI, eligibility={"nri_sponsored": True}
    )
    assert seat.status is CheckStatus.CONFIRMED
    assert seat.supplied_by == "AICTE approval v1, 2026-27 (Seat Ledger, derived)"
    assert seat.detail["summary"] == "Holds seat CSE-N-001 (NRI, AICTE approval v1, 2026-27)."
    assert (seat.detail["approval_version"], seat.independent) == (1, False)
    assert cases == []


@pytest.mark.parametrize(
    ("route", "eligibility", "nationality", "rule", "summary", "severity"),
    [
        (
            AdmissionRoute.NRI,
            {"nri_sponsored": False},
            "IN",
            "NRI_STATUS",
            "NRI seat held by a student reported as not marked for this category; "
            "APH 2024-27 cl. 2.8(b) does not allow it.",
            Severity.MEDIUM,
        ),
        (
            AdmissionRoute.TFW,
            {"tfw_income_certified": False},
            "IN",
            "TFW_INCOME",
            "TFW seat held by a student reported as without a family income certificate; "
            "APH 2024-27 cl. 6.42(d) does not allow it.",
            Severity.MEDIUM,
        ),
        (
            AdmissionRoute.INTERNATIONAL,
            {},
            "IN",
            "INTERNATIONAL_CIWG",
            "International seat held by a student reported as not marked for this category; "
            "APH 2024-27 cl. 2.9 does not allow it.",
            Severity.HIGH,
        ),
    ],
)
async def test_each_eligibility_breach_contradicts_the_seat_with_a_case(
    world, session, gov, route, eligibility, nationality, rule, summary, severity
) -> None:
    passport = "Z9000009" if route is AdmissionRoute.INTERNATIONAL else None
    seat, cases = await _seated(
        world,
        session,
        gov,
        route=route,
        eligibility=eligibility,
        nationality=nationality,
        passport=passport,
    )
    assert seat.status is CheckStatus.CONTRADICTED
    assert (seat.detail["basis"], seat.detail["eligibility_rule"]) == ("NOT_ELIGIBLE", rule)
    assert seat.detail["finding"] == "not eligible for this seat"
    assert seat.detail["summary"] == summary
    [case] = cases
    assert case.severity is severity
    assert case.dedupe_key == f"ELIGIBILITY_BREACH:{case.enrolment_id}"
    facts = {f["label"]: f["value"] for f in case.evidence["facts"]}
    assert set(facts) == {"Seat", "Reported as", "Allowed for this seat"}


async def test_a_tfw_seat_without_the_certificate_reported_waits(world, session, gov) -> None:
    seat, cases = await _seated(world, session, gov, route=AdmissionRoute.TFW)
    assert seat.status is CheckStatus.PENDING
    assert (seat.detail["basis"], seat.detail["finding"]) == (
        "TFW_NOT_REPORTED",
        "TFW income certificate not reported",
    )
    assert cases == []


async def test_no_pool_of_the_route_type_names_the_version(world, session, gov) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    mba = await world.programme(inst, "MBA", name="MBA", intakes={"2026-27": 10})
    student = await world.student("Kiran Rao", DOB)
    enrolment = await world.enrol(student, mba, route=AdmissionRoute.LATERAL)
    # a lateral admission to a programme whose approval has no lateral seats
    pool = (
        await session.execute(select(SeatPool).where(SeatPool.seat_type == "LATERAL"))
    ).scalar_one()
    pool.capacity = 0
    await session.flush()
    await run_checks(session, [enrolment.id], gov)
    seat = (await _rows(session, enrolment))[CheckType.SEAT]
    assert seat.status is CheckStatus.CONTRADICTED
    assert seat.detail["basis"] == "NO_POOL"
    assert seat.detail["finding"] == "no Lateral seats approved"


# ---------------------------------------------------------------------- IDENTITY


async def test_a_claimed_record_is_confirmed_by_the_student_sign_in(world, session, gov) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student(
        "Priyanka Salunkhe", date(2009, 1, 17), consent=ConsentStatus.REFUSED
    )
    enrolment = await world.enrol(student, cse)
    await run_checks(session, [enrolment.id], gov)
    identity = (await _rows(session, enrolment))[CheckType.IDENTITY]
    assert (identity.status, identity.detail["basis"]) == (CheckStatus.NOT_APPLICABLE, "NO_APAAR")

    session.add(
        User(
            email="priyanka@digilocker.demo",
            password_hash=hash_password(PASSWORD),
            name="Priyanka Salunkhe",
            role=UserRole.STUDENT,
            student_id=student.id,
            digilocker_sub="DL-K9A5-Y8KV",
        )
    )
    await session.flush()
    await run_checks(session, [enrolment.id], gov)
    identity = (await _rows(session, enrolment))[CheckType.IDENTITY]
    assert (identity.status, identity.detail["basis"]) == (
        CheckStatus.CONFIRMED,
        "DIGILOCKER_CLAIM",
    )
    assert (identity.supplied_by, identity.independent) == ("Student via DigiLocker sign-in", True)
    assert identity.source == "DIGILOCKER"
    assert identity.detail["source_line"].startswith("Student sign-in via DigiLocker · ")
    assert "{date}" not in identity.detail["summary"]
    assert identity.observed_at is not None


async def test_a_malformed_apaar_is_the_college_s_own_upload(world, session, gov) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student("Short Id")
    enrolment = await world.enrol(student, cse, apaar_problem="has 11 digits, expected 12")
    await run_checks(session, [enrolment.id], gov)
    identity = (await _rows(session, enrolment))[CheckType.IDENTITY]
    assert (identity.status, identity.detail["basis"]) == (
        CheckStatus.CONTRADICTED,
        "APAAR_MALFORMED",
    )
    assert (identity.supplied_by, identity.independent) == ("College upload", False)
    assert identity.observed_at == enrolment.uploaded_at
    assert identity.detail["source_line"].startswith("College upload · ")
    assert identity.detail["finding"] == "APAAR not valid"


async def test_writing_rows_queues_their_records_for_a_status(world, session, gov) -> None:
    enrolment = await _ravi(world, session, gov)
    session.info.pop(STATUS_DIRTY, None)
    await run_checks(session, [enrolment.id], gov)
    assert enrolment.id in session.info[STATUS_DIRTY]


async def test_rerun_without_adapters_uses_the_configured_sources(world, session, gov) -> None:
    """A claim re-runs only the Identity row; a caller without adapters still gets it."""
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student("Kiran Rao", date(2009, 1, 17), consent=ConsentStatus.REFUSED)
    enrolment = await world.enrol(student, cse)
    session.add(
        User(
            email="kiran@digilocker.demo",
            password_hash=hash_password(PASSWORD),
            name="Kiran Rao",
            role=UserRole.STUDENT,
            student_id=student.id,
            digilocker_sub="DL-KIRAN-0001",
        )
    )
    await session.flush()
    result = await rerun(session, [enrolment.id], None, types=[CheckType.IDENTITY])
    assert result.statuses == {"IDENTITY": {"CONFIRMED": 1}}
    rows = await _rows(session, enrolment)
    assert set(rows) == {CheckType.IDENTITY}
    assert rows[CheckType.IDENTITY].detail["basis"] == "DIGILOCKER_CLAIM"
