"""DefaultEngines drives one batch's stages in pipeline order (ENGINES.md sections 3 and 4)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.engine.contracts import CHUNK_SIZE, EngineSuite
from app.engine.suite import DefaultEngines, default_engines
from app.models.enums import AdmissionRoute, FlagType
from app.models.verification import Flag


def test_protocol_shape() -> None:
    suite: EngineSuite = default_engines()
    assert isinstance(suite, DefaultEngines)
    assert suite.normalise_name("Shri. R. K. Sharma") == "r k sharma"
    assert suite.name_key("R. K. Sharma", date(2007, 3, 21)) == "2007-03-21|r|XRM"
    assert CHUNK_SIZE == 500


async def test_stages_in_pipeline_order(world, session, gov) -> None:
    inst = await world.institution("ABC College of Engineering", "1-ABC-0001")
    cse = await world.programme(inst, "CSE")
    batch = await world.batch(inst)
    regular = await world.cohort(cse, 126, batch=batch)
    nri = await world.cohort(cse, 6, batch=batch, route=AdmissionRoute.NRI)
    for enrolment in nri:  # the college reports them as NRI-sponsored (D41)
        enrolment.eligibility = {"nri_sponsored": True}
    ids = [e.id for e in regular + nri]
    suite = DefaultEngines()

    ledger = await suite.assign_seats(session, ids, actor_id=None)
    checks = await suite.run_checks(session, ids + ledger.seated, gov, concurrency=8)
    dupes = await suite.detect_duplicates(session, inst.id, "2026-27", ids)
    tally = await suite.refresh_seat_flags(
        session, sorted(ledger.touched_pools, key=lambda p: (str(p.approval_id), p.seat_type))
    )
    assert (len(ledger.seated), len(ledger.unseated)) == (120, 12)
    assert checks.enrolments == 132
    assert checks.statuses["SEAT"] == {"CONFIRMED": 120, "CONTRADICTED": 12}
    assert dupes.within == 0
    assert tally.created == 1
    [flag] = (
        (await session.execute(select(Flag).where(Flag.type == FlagType.EXCESS_ADMISSION)))
        .scalars()
        .all()
    )
    assert flag.evidence["summary"] == (
        "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat."
    )
