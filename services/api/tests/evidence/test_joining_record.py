"""The Joining record row reads the state admission authority (D39; API_CONTRACT §A4.4).

Found is Confirmed and independent; not found is Pending before the reporting deadline and
Contradicted with one NOT_IN_JOINING_RECORD case after it; an authority that has published
nothing is Not yet due before the deadline and Pending after it; an authority that does
not answer is Source unavailable and never raises a case.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.core.rules import get_rules
from app.engine import status_text as text
from app.engine.checks import run_checks
from app.engine.ledger import assign_seats
from app.models.enums import AdmissionRoute, CheckStatus, CheckType, FlagType, Severity
from app.models.verification import Check, Flag
from tests.evidence.conftest import joining_row

DOB = date(2007, 3, 21)
TODAY = text.ist_date(datetime.now(UTC))


@pytest.fixture
def deadline(monkeypatch):
    """Move the 2026-27 reporting deadline: before or after today."""

    def move(on: date) -> None:
        monkeypatch.setitem(get_rules().reporting.deadline, "2026-27", on)

    return move


async def _record(world, session, gov, *, route=AdmissionRoute.COUNSELLING, published=True):
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417")
    enrolment = await world.enrol(student, cse, route=route)
    gov.apaar.registry["123456784417"] = {"name": "Ravi Kumar Sharma", "dob": DOB}
    if published:  # somebody else's joining: the authority published its 2026-27 record
        gov.admission_authority.add(
            joining_row(name="Asha Patil", dob=date(2007, 5, 2), institution_code="1-ABC-0001")
        )
    await assign_seats(session, [enrolment.id], actor_id=None)
    return enrolment


async def _row(session, enrolment) -> Check:
    return (
        await session.execute(
            select(Check)
            .where(Check.enrolment_id == enrolment.id, Check.type == CheckType.ADMISSION)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def _cases(session) -> list[Flag]:
    return list(
        (
            await session.execute(select(Flag).where(Flag.type == FlagType.NOT_IN_JOINING_RECORD))
        ).scalars()
    )


async def test_found_is_confirmed_and_independent(world, session, gov) -> None:
    enrolment = await _record(world, session, gov)
    gov.admission_authority.add(
        joining_row(
            name="Ravi Kumar Sharma",
            dob=DOB,
            institution_code="1-ABC-0001",
            route="MANAGEMENT",
            round=None,
        )
    )
    await run_checks(session, [enrolment.id], gov)
    found = await _row(session, enrolment)
    assert found.status is CheckStatus.CONFIRMED
    assert (found.source, found.supplied_by, found.independent) == (
        "ADMISSION_AUTHORITY",
        "State admission authority",
        True,
    )
    assert found.detail["basis"] == "JOINED"
    assert found.detail["finding"] == "joined 2 Aug"
    assert found.detail["source_line"] == f"State admission authority · {text.day(TODAY, TODAY)}"
    # the authority says Management, the upload Counselling: shown, still confirmed
    assert (found.detail["route"], found.detail["route_mismatch"]) == ("MANAGEMENT", True)
    assert (found.detail["joining_year"], found.detail["published"]) == ("2026-27", True)


async def test_not_found_before_the_deadline_is_pending(world, session, gov, deadline) -> None:
    deadline(date(TODAY.year + 1, 9, 30))
    enrolment = await _record(world, session, gov)
    await run_checks(session, [enrolment.id], gov)
    pending = await _row(session, enrolment)
    assert pending.status is CheckStatus.PENDING
    assert pending.detail["basis"] == "NOT_YET_IN_RECORD"
    assert pending.detail["finding"] == "not in the joining record yet"
    assert pending.detail["summary"] == (
        "Not in the Maharashtra admission authority's joining record yet; the reporting "
        f"deadline is 30 Sep {TODAY.year + 1}."
    )
    assert await _cases(session) == []


async def test_nothing_published_before_the_deadline_is_not_yet_due(
    world, session, gov, deadline
) -> None:
    deadline(date(TODAY.year + 1, 9, 30))
    enrolment = await _record(world, session, gov, published=False)
    await run_checks(session, [enrolment.id], gov)
    waiting = await _row(session, enrolment)
    assert waiting.status is CheckStatus.NOT_YET_DUE
    assert (waiting.detail["basis"], waiting.detail["finding"]) == ("NOT_PUBLISHED", None)
    assert waiting.detail["source_line"] == f"Published by 30 Sep {TODAY.year + 1}"
    assert waiting.independent is False
    assert await _cases(session) == []


async def test_nothing_published_after_the_deadline_is_pending_not_contradicted(
    world, session, gov
) -> None:
    enrolment = await _record(world, session, gov, published=False)
    await run_checks(session, [enrolment.id], gov)
    late = await _row(session, enrolment)
    assert late.status is CheckStatus.PENDING
    assert (late.detail["basis"], late.detail["finding"]) == (
        "NOT_PUBLISHED_LATE",
        "not published yet",
    )
    assert late.detail["summary"] == (
        "The Maharashtra admission authority has not published its joining record for "
        f"2026-27; it was due by {text.day(date(2026, 9, 30), TODAY)}."
    )
    assert await _cases(session) == []


async def test_not_found_after_the_deadline_is_contradicted_with_one_case(
    world, session, gov
) -> None:
    enrolment = await _record(world, session, gov)
    await run_checks(session, [enrolment.id], gov)
    await run_checks(session, [enrolment.id], gov)  # a second evaluation raises no second case
    missing = await _row(session, enrolment)
    assert missing.status is CheckStatus.CONTRADICTED
    assert (missing.detail["basis"], missing.detail["finding"]) == (
        "NOT_IN_JOINING_RECORD",
        "not found",
    )
    assert missing.detail["case_type"] == "NOT_IN_JOINING_RECORD"
    assert missing.independent is True
    [case] = await _cases(session)
    assert (case.severity, case.enrolment_id) == (Severity.MEDIUM, enrolment.id)
    assert case.dedupe_key == f"NOT_IN_JOINING_RECORD:{enrolment.id}"
    assert case.evidence["rule_source"] == "State admission authority joining record"
    facts = {f["label"]: f["value"] for f in case.evidence["facts"]}
    assert facts["Joining record"] == "Not found"
    assert facts["Programme and year"] == "CSE (2026-27)"


async def test_an_authority_that_does_not_answer_never_raises_a_case(world, session, gov) -> None:
    enrolment = await _record(world, session, gov)
    gov.admission_authority.down = True
    result = await run_checks(session, [enrolment.id], gov)
    down = await _row(session, enrolment)
    assert down.status is CheckStatus.SOURCE_UNAVAILABLE
    assert (down.supplied_by, down.independent) == ("State admission authority", False)
    assert down.detail["source_line"].startswith("State admission authority did not respond · ")
    assert result.unavailable == {"ADMISSION_AUTHORITY": 1}
    assert await _cases(session) == []


async def test_a_lateral_entrant_is_looked_up_in_the_year_it_joined(world, session, gov) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst, intakes={"2025-26": 120, "2026-27": 120})
    student = await world.student("Asha Patil", date(2006, 5, 2), apaar="123456780001")
    enrolment = await world.enrol(student, cse, year_of_study=2, route=AdmissionRoute.LATERAL)
    gov.admission_authority.add(
        joining_row(
            name="Asha Patil",
            dob=date(2006, 5, 2),
            institution_code="1-ABC-0001",
            academic_year="2026-27",
            route="LATERAL",
            round=2,
        )
    )
    await run_checks(session, [enrolment.id], gov)
    found = await _row(session, enrolment)
    assert found.status is CheckStatus.CONFIRMED
    assert found.detail["joining_year"] == "2026-27"


async def test_an_international_admission_reads_study_in_india(world, session, gov) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst)
    student = await world.student("Amina Rahman", nationality="BD", passport="N1000001")
    enrolment = await world.enrol(student, cse, route=AdmissionRoute.INTERNATIONAL)
    await run_checks(session, [enrolment.id], gov)
    absent = await _row(session, enrolment)
    assert absent.status is CheckStatus.CONTRADICTED
    assert (absent.source, absent.detail["basis"]) == ("SII", "SII_NOT_ADMITTED")
    [case] = await _cases(session)
    assert case.evidence["rule_source"] == "Study in India"

    gov.sii.admissions["N1000001"] = {
        "nationality": "BD",
        "institution_aicte_id": "1-ABC-0001",
        "programme": "CSE",
        "academic_year": "2026-27",
    }
    await run_checks(session, [enrolment.id], gov)
    rows = {
        c.type: c
        for c in (
            await session.execute(
                select(Check)
                .where(Check.enrolment_id == enrolment.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    assert rows[CheckType.ADMISSION].status is CheckStatus.CONFIRMED
    # Study in India by passport is the identity too (D36)
    identity = rows[CheckType.IDENTITY]
    assert (identity.status, identity.detail["basis"], identity.supplied_by) == (
        CheckStatus.CONFIRMED,
        "SII_MATCH",
        "Study in India",
    )
    assert identity.independent is True
