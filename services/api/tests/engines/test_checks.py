"""run_checks and recheck_pending against the database with the InMemory adapters."""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import func, select

from app.adapters.base import ApaarResult
from app.engine.checks import recheck_pending, run_checks
from app.engine.ledger import assign_seats
from app.engine.score import countersign
from app.models.audit import AuditLog
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagType,
    RowErrorLevel,
    Severity,
)
from app.models.upload import UploadRowError
from app.models.verification import Check, Flag

RAVI = "123456784417"


async def _checks(session, enrolment_id) -> dict[CheckType, Check]:
    rows = await session.execute(
        select(Check)
        .where(Check.enrolment_id == enrolment_id)
        .execution_options(populate_existing=True)
    )
    return {c.type: c for c in rows.scalars().all()}


async def _ravi(world, gov, *, year_of_study: int = 1):
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst, "CSE", intakes={"2025-26": 120, "2026-27": 120})
    stu = await world.student(
        "Ravi Kumar Sharma", date(2007, 3, 21), apaar=RAVI, mobile="9876504521"
    )
    enrolment = await world.enrol(
        stu, cse, year_of_study=year_of_study, counselling_ref="MHCET-2026-R1-004512"
    )
    gov.apaar.registry[RAVI] = {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 21)}
    gov.counselling.allotments.append(
        {
            "state": "MH",
            "year": 2026 - (year_of_study - 1),
            "name": "Ravi Kumar Sharma",
            "dob": "2007-03-21",
            "roll_no": "MHCET-2026-004512",
            "programme": "CSE",
            "institution_aicte_id": "1-ABC-0001",
            "round": 1,
            "category": "GENERAL",
            "allotment_ref": "MHCET-2026-R1-004512",
        }
    )
    return inst, cse, enrolment


async def test_five_checks_written_once(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov)
    await assign_seats(session, [enrolment.id], actor_id=None)
    result = await run_checks(session, [enrolment.id], gov)
    assert result.enrolments == 1
    assert result.changed == 5
    assert result.calls == {"APAAR": 1, "COUNSELLING": 1}
    assert result.unavailable == {}
    assert result.statuses == {
        "IDENTITY": {"CONFIRMED": 1},
        "ADMISSION": {"CONFIRMED": 1},
        "SEAT": {"CONFIRMED": 1},
        "STUDYING": {"NOT_YET_DUE": 1},
        "STUDENT": {"PENDING": 1},
    }
    checks = await _checks(session, enrolment.id)
    assert {t: c.status for t, c in checks.items()} == {
        CheckType.IDENTITY: CheckStatus.CONFIRMED,
        CheckType.ADMISSION: CheckStatus.CONFIRMED,
        CheckType.SEAT: CheckStatus.CONFIRMED,
        CheckType.STUDYING: CheckStatus.NOT_YET_DUE,
        CheckType.STUDENT: CheckStatus.PENDING,
    }
    assert countersign(checks.values())["score"] == {"passes": 3, "applicable": 4}
    assert checks[CheckType.SEAT].detail["summary"] == (
        "Holds seat CSE-R-001 (Regular, 2026-27 approval)."
    )
    assert checks[CheckType.ADMISSION].source == "COUNSELLING"
    assert all(c.attempts == 0 and c.checked_at is not None for c in checks.values())
    audits = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_type == "enrolment").order_by(AuditLog.seq)
            )
        )
        .scalars()
        .all()
    )
    assert [a.after for a in audits] == [
        {
            "checks": {
                "IDENTITY": "CONFIRMED",
                "ADMISSION": "CONFIRMED",
                "SEAT": "CONFIRMED",
                "STUDYING": "NOT_YET_DUE",
                "STUDENT": "PENDING",
            }
        },
        # the record's status moved too
        {"record_status": "COUNTERSIGNED"},
    ]
    first_checked = {t: c.checked_at for t, c in checks.items()}

    again = await run_checks(session, [enrolment.id], gov)
    assert again.changed == 0
    assert again.flags.created == again.flags.updated == 0
    checks = await _checks(session, enrolment.id)
    assert {t: c.checked_at for t, c in checks.items()} == first_checked
    count = select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "enrolment")
    # nothing changed on the second run, so nothing more is audited
    assert (await session.execute(count)).scalar_one() == 2


async def test_unseated_enrolment_fails_seat_and_points_at_the_flag(world, session, gov) -> None:
    _, cse, enrolment = await _ravi(world, gov)
    await run_checks(session, [enrolment.id], gov)
    seat = (await _checks(session, enrolment.id))[CheckType.SEAT]
    assert seat.status is CheckStatus.CONTRADICTED
    assert seat.detail["flag_dedupe_key"] == f"EXCESS_ADMISSION:{cse.id}:2026-27:REGULAR"
    assert seat.detail["summary"] == (
        "No Regular seat is free in CSE (2026-27); see the Excess admission flag."
    )


async def test_second_year_with_zero_credits_fails_studying(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov, year_of_study=2)
    gov.abc.credits_by_apaar[RAVI] = {
        "2025-26": [
            {"sem": 1, "credits": 0, "uploaded_at": "2026-01-20T00:00:00Z", "result": "FAIL"},
            {"sem": 2, "credits": 0, "uploaded_at": "2026-06-30T00:00:00Z", "result": "FAIL"},
        ]
    }
    result = await run_checks(session, [enrolment.id], gov)
    assert result.calls["ABC"] == 1
    studying = (await _checks(session, enrolment.id))[CheckType.STUDYING]
    assert studying.status is CheckStatus.CONTRADICTED
    assert studying.detail["missing"] == 2 and studying.detail["expected"] == 2
    [flag] = (
        (await session.execute(select(Flag).where(Flag.type == FlagType.NO_ACADEMIC_ACTIVITY)))
        .scalars()
        .all()
    )
    assert flag.severity is Severity.MEDIUM
    assert flag.enrolment_id == enrolment.id
    assert flag.dedupe_key == f"NO_ACADEMIC_ACTIVITY:{enrolment.id}"
    assert flag.evidence["summary"] == (
        "No credits recorded in ABC for 2 semesters while enrolled in year 2."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Last ABC entry"] == "30 Jun 2026"
    assert result.flags.created == 1


async def test_each_row_says_who_supplied_it_when_and_whether_independent(
    world, session, gov
) -> None:
    _, _, enrolment = await _ravi(world, gov)
    await assign_seats(session, [enrolment.id], actor_id=None)
    await run_checks(session, [enrolment.id], gov)
    checks = await _checks(session, enrolment.id)
    provenance = {
        t: (c.supplied_by, c.independent, c.observed_at is not None) for t, c in checks.items()
    }
    assert provenance == {
        CheckType.IDENTITY: ("APAAR registry", True, True),
        CheckType.ADMISSION: ("Counselling list", True, True),
        CheckType.SEAT: ("AICTE approval 2026-27 (Seat Ledger, derived)", False, True),
        # first year: credits are not due, so no source answered
        CheckType.STUDYING: ("", False, False),
        # no reply yet
        CheckType.STUDENT: ("", False, False),
    }
    assert all(c.resolved is None for c in checks.values())


async def test_credits_name_abc_and_are_not_independent_yet(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov, year_of_study=2)
    gov.abc.credits_by_apaar[RAVI] = {
        "2025-26": [{"sem": 1, "credits": 22}, {"sem": 2, "credits": 24}]
    }
    await run_checks(session, [enrolment.id], gov)
    studying = (await _checks(session, enrolment.id))[CheckType.STUDYING]
    assert studying.status is CheckStatus.CONFIRMED
    assert (studying.supplied_by, studying.independent) == ("ABC credits", False)
    assert studying.observed_at is not None


async def test_apaar_down_leaves_identity_unavailable_and_recheck_confirms(
    world, session, gov
) -> None:
    _, _, enrolment = await _ravi(world, gov)
    gov.apaar.down = True
    result = await run_checks(session, [enrolment.id], gov)
    assert result.unavailable == {"APAAR": 1}
    identity = (await _checks(session, enrolment.id))[CheckType.IDENTITY]
    assert identity.status is CheckStatus.SOURCE_UNAVAILABLE
    assert identity.detail["source_unavailable"] is True
    assert identity.attempts == 1
    # the registry was asked but observed nothing
    assert (identity.supplied_by, identity.observed_at) == ("APAAR registry", None)
    assert await session.scalar(select(func.count()).select_from(Flag)) == 0

    still = await recheck_pending(session, [enrolment.id], gov)
    assert (still.enrolments, still.rechecked, still.still_pending) == (1, 1, 1)
    assert (await _checks(session, enrolment.id))[CheckType.IDENTITY].attempts == 2

    gov.apaar.down = False
    recovered = await recheck_pending(session, [enrolment.id], gov)
    assert (recovered.rechecked, recovered.now_pass, recovered.still_pending) == (1, 1, 0)
    checks = await _checks(session, enrolment.id)
    assert checks[CheckType.IDENTITY].status is CheckStatus.CONFIRMED
    assert checks[CheckType.IDENTITY].detail["summary"].startswith("Name and date of birth match")
    assert checks[CheckType.IDENTITY].attempts == 2  # outages met, not evaluations
    assert checks[CheckType.IDENTITY].observed_at is not None
    assert checks[CheckType.STUDENT].status is CheckStatus.PENDING  # never rechecked here

    nothing = await recheck_pending(session, [enrolment.id], gov)
    assert (nothing.enrolments, nothing.rechecked) == (0, 0)


async def test_registry_findings_raise_identity_flags(world, session, gov) -> None:
    inst = await world.institution()
    cse = await world.programme(inst)
    batch = await world.batch(inst)
    ghost = await world.enrol(
        await world.student("Ghost Student", apaar="999988887777"), cse, batch=batch, row_no=2
    )
    malformed = await world.enrol(
        await world.student("Short Id"),
        cse,
        batch=batch,
        row_no=3,
        apaar_problem="contains characters other than digits",
    )
    session.add(
        UploadRowError(
            batch_id=batch.id,
            row_no=3,
            level=RowErrorLevel.WARNING,
            field="apaar_id",
            code="APAAR_FORMAT",
            message="APAAR must be 12 digits",
            value_masked="<12 characters>",
            raw={},
        )
    )
    await session.flush()
    await run_checks(session, [ghost.id, malformed.id], gov)
    flags = {f.enrolment_id: f for f in (await session.execute(select(Flag))).scalars().all()}
    assert flags[ghost.id].type is FlagType.INVALID_APAAR
    assert flags[ghost.id].severity is Severity.HIGH
    assert flags[ghost.id].evidence["summary"] == (
        "APAAR ending 7777 is not in the APAAR registry."
    )
    assert flags[malformed.id].severity is Severity.MEDIUM
    assert flags[malformed.id].evidence["facts"][0]["value"] == "<12 characters>"
    assert (await _checks(session, malformed.id))[CheckType.IDENTITY].detail["summary"] == (
        "APAAR as uploaded contains characters other than digits; the enrolment was kept "
        "without it."
    )


async def test_only_active_enrolments_are_checked(world, session, gov) -> None:
    _, cse, enrolment = await _ravi(world, gov)
    enrolment.status = EnrolmentStatus.WITHDRAWN
    await session.flush()
    result = await run_checks(session, [enrolment.id], gov)
    assert result.enrolments == 0
    assert await _checks(session, enrolment.id) == {}


async def test_semaphore_bounds_adapter_calls(world, session, gov) -> None:
    inst = await world.institution()
    cse = await world.programme(inst)
    enrolments = []
    for i in range(12):
        apaar = f"4000000000{i:02d}"
        enrolments.append(await world.enrol(await world.student(f"Student {i}", apaar=apaar), cse))

    class Slow:
        in_flight = 0
        peak = 0

        async def verify(self, apaar_id, name, dob):
            Slow.in_flight += 1
            Slow.peak = max(Slow.peak, Slow.in_flight)
            await asyncio.sleep(0.01)
            Slow.in_flight -= 1
            return ApaarResult(exists=True, name_score=100, dob_match=True)

    gov.apaar = Slow()
    result = await run_checks(session, [e.id for e in enrolments], gov, concurrency=3)
    assert result.calls["APAAR"] == 12
    assert 1 < Slow.peak <= 3


async def test_admission_route_rules_through_run_checks(world, session, gov) -> None:
    inst = await world.institution()
    cse = await world.programme(inst)
    [mgmt] = await world.cohort(cse, 1, route=AdmissionRoute.MANAGEMENT)
    await assign_seats(session, [mgmt.id], actor_id=None)
    await run_checks(session, [mgmt.id], gov)
    admission = (await _checks(session, mgmt.id))[CheckType.ADMISSION]
    assert admission.status is CheckStatus.CONFIRMED
    assert admission.source == "SEAT_LEDGER"
