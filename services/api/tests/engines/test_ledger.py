"""Seat Ledger (ENGINES.md section 7, D16): pools, backlog, releases, LATE_REFILL, seat flags."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.engine.flags import refresh_seat_flags
from app.engine.ledger import assign_seats
from app.models.audit import AuditLog
from app.models.enums import (
    AdmissionRoute,
    EnrolmentStatus,
    FlagType,
    SeatEventKind,
    SeatStatus,
    SeatType,
    Severity,
)
from app.models.institution import Approval
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.verification import Flag


async def _flags(session, flag_type: FlagType | None = None) -> list[Flag]:
    stmt = select(Flag).order_by(Flag.dedupe_key)
    if flag_type is not None:
        stmt = stmt.where(Flag.type == flag_type)
    return list((await session.execute(stmt)).scalars().all())


async def _count(session, model, *where) -> int:
    return (
        await session.execute(select(func.count()).select_from(model).where(*where))
    ).scalar_one()


async def test_abc_cse_shape_132_admitted_against_120(world, session) -> None:
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst, "CSE")
    capacities = dict(
        (
            await session.execute(
                select(SeatPool.seat_type, SeatPool.capacity)
                .join(Approval, Approval.id == SeatPool.approval_id)
                .where(Approval.programme_id == cse.id)
            )
        ).all()
    )
    assert capacities == {
        SeatType.REGULAR: 114,
        SeatType.NRI: 6,
        SeatType.TFW: 6,
        SeatType.LATERAL: 12,
        SeatType.INTERNATIONAL: 18,
    }
    batch = await world.batch(inst)
    regular = await world.cohort(cse, 126, batch=batch, start_row=2)
    nri = await world.cohort(cse, 6, route=AdmissionRoute.NRI, batch=batch, start_row=128)
    ids = [e.id for e in regular + nri]

    result = await assign_seats(session, ids, actor_id=None)
    assert len(result.seated) == 120
    assert len(result.unseated) == 12
    assert result.released == [] and result.late_refills == []
    # oldest first: the first 114 regular-route rows hold the REGULAR seats
    assert set(result.unseated) == {e.id for e in regular[114:]}
    assert {r.seat_type for r in result.touched_pools} == {SeatType.REGULAR, SeatType.NRI}
    assert await _count(session, SeatEvent, SeatEvent.kind == SeatEventKind.ASSIGN) == 120
    assert await _count(session, AuditLog, AuditLog.entity_type == "seat") == 120

    tally = await refresh_seat_flags(session, sorted(result.touched_pools, key=str))
    assert (tally.created, tally.updated) == (1, 0)
    [flag] = await _flags(session)
    assert flag.type is FlagType.EXCESS_ADMISSION
    assert flag.severity is Severity.HIGH
    assert flag.dedupe_key == f"EXCESS_ADMISSION:{cse.id}:2026-27:REGULAR"
    assert flag.evidence["summary"] == (
        "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat."
    )
    assert flag.evidence["summary"].startswith(
        "132 admitted against 120 approved seats in CSE (2026-27)"
    )
    assert flag.evidence["data"] == {
        "approved": 120,
        "admitted": 132,
        "seated": 120,
        "unseated": 12,
        "peak_unseated": 12,
    }
    assert set(flag.related_enrolment_ids) == {e.id for e in regular[114:]}
    assert flag.evidence["related_enrolment_ids"] == [str(i) for i in flag.related_enrolment_ids]
    assert flag.academic_year == "2026-27"
    assert flag.programme_id == cse.id and flag.enrolment_id is None

    # Idempotent: a second run seats nobody, writes no event and changes no flag.
    again = await assign_seats(session, ids, actor_id=None)
    assert again.seated == [] and again.released == []
    assert len(again.unseated) == 12
    assert await _count(session, SeatEvent) == 120
    tally = await refresh_seat_flags(session, sorted(again.touched_pools, key=str))
    assert (tally.created, tally.updated, tally.unchanged) == (0, 0, 1)


async def test_nri_overflow_raises_quota_breach(world, session) -> None:
    inst = await world.institution()
    cse = await world.programme(inst, "CSE")
    regular = await world.cohort(cse, 100)
    nri = await world.cohort(cse, 9, route=AdmissionRoute.NRI)
    result = await assign_seats(session, [e.id for e in regular + nri], actor_id=None)
    assert len(result.seated) == 106
    assert set(result.unseated) == {e.id for e in nri[6:]}

    await refresh_seat_flags(session, sorted(result.touched_pools, key=str))
    [flag] = await _flags(session)
    assert flag.type is FlagType.QUOTA_BREACH
    assert flag.dedupe_key == f"QUOTA_BREACH:{cse.id}:2026-27:NRI"
    assert flag.severity is Severity.HIGH  # NRI more than 2 over
    assert flag.evidence["summary"] == "9 NRI admissions against 6 NRI seats in CSE (2026-27)."
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Admitted via route"] == "9 (NRI)"
    assert facts["Rule percentage"] == "5% of approved intake 120"
    assert facts["Unseated"] == "3"


async def test_small_nri_overflow_is_medium(world, session) -> None:
    inst = await world.institution()
    cse = await world.programme(inst, "CSE")
    nri = await world.cohort(cse, 8, route=AdmissionRoute.NRI)
    result = await assign_seats(session, [e.id for e in nri], actor_id=None)
    await refresh_seat_flags(session, sorted(result.touched_pools, key=str))
    [flag] = await _flags(session)
    assert flag.severity is Severity.MEDIUM


async def test_withdrawal_releases_and_refill_after_cutoff_is_late(world, session) -> None:
    inst = await world.institution()
    it = await world.programme(inst, "IT", intakes={"2026-27": 20})  # REGULAR 19, NRI 1
    initial = await world.batch(inst, "1-T_2026-27.csv")
    full = await world.cohort(it, 19, batch=initial)
    await assign_seats(session, [e.id for e in full], actor_id=None)

    update = await world.batch(inst, "1-T_2026-27_update1.csv")
    leaving = full[:2]
    for enrolment, row_no in zip(leaving, (2, 3), strict=True):
        enrolment.status = EnrolmentStatus.WITHDRAWN
        enrolment.status_date = date(2026, 9, 20)
        enrolment.upload_batch_id, enrolment.source_row_no = update.id, row_no
    held = [e.seat_id for e in leaving]
    refills = [
        await world.enrol(
            await world.student(f"Refill {i}", apaar=f"55550000000{i}"),
            it,
            route=AdmissionRoute.MANAGEMENT,
            admission_date=date(2026, 10, 5),
            batch=update,
            row_no=4 + i,
        )
        for i in range(2)
    ]
    await session.flush()

    result = await assign_seats(session, [e.id for e in leaving + refills], actor_id=None)
    assert result.released == [e.id for e in leaving]
    assert sorted(result.seated, key=str) == sorted((e.id for e in refills), key=str)
    assert sorted(result.late_refills, key=str) == sorted((e.id for e in refills), key=str)
    assert result.flags.created == 2
    assert {e.seat_id for e in refills} == set(held)
    releases = (
        (await session.execute(select(SeatEvent).where(SeatEvent.kind == SeatEventKind.RELEASE)))
        .scalars()
        .all()
    )
    assert {(r.reason, r.effective_date) for r in releases} == {("withdrawal", date(2026, 9, 20))}

    flags = await _flags(session, FlagType.LATE_REFILL)
    assert len(flags) == 2
    flag = next(f for f in flags if f.enrolment_id == refills[0].id)
    seat = await session.get(Seat, refills[0].seat_id)
    assert flag.severity is Severity.MEDIUM
    assert flag.dedupe_key == f"LATE_REFILL:{seat.id}:{refills[0].id}"
    assert flag.evidence["summary"] == (
        f"Seat {seat.seat_code} assigned on 5 Oct 2026, after the last admission date 15 Sep 2026."
    )
    facts = {f["label"]: (f["value"], f["source"]) for f in flag.evidence["facts"]}
    assert facts["Released on"] == ("20 Sep 2026", "Seat ledger")
    assert facts["Assigned on"] == (
        "5 Oct 2026",
        "College upload 1-T_2026-27_update1.csv, row 4",
    )
    assert flag.evidence["rule_source"] == (
        "Last admission date for 2026-27 (AICTE admission schedule)"
    )

    # Re-running the same delta changes nothing.
    again = await assign_seats(session, [e.id for e in leaving + refills], actor_id=None)
    assert again.seated == again.released == again.late_refills == []
    assert again.flags.created == 0


async def test_backlog_admitted_before_cutoff_takes_a_freed_seat_without_late_refill(
    world, session
) -> None:
    inst = await world.institution()
    it = await world.programme(inst, "IT", intakes={"2026-27": 20})
    full = await world.cohort(it, 19)
    backlog = await world.cohort(it, 1, admission_date=date(2026, 8, 20))
    first = await assign_seats(session, [e.id for e in full + backlog], actor_id=None)
    assert first.unseated == [backlog[0].id]

    late = await world.cohort(it, 1, admission_date=date(2026, 10, 1), route=AdmissionRoute.SPOT)
    leaving = full[0]
    leaving.status = EnrolmentStatus.WITHDRAWN
    leaving.status_date = date(2026, 9, 25)
    await session.flush()
    result = await assign_seats(session, [leaving.id, late[0].id], actor_id=None)
    # the backlog row, admitted first, gets the freed seat; the later admission waits
    assert result.seated == [backlog[0].id]
    assert result.late_refills == []
    assert result.unseated == [late[0].id]
    assert await _flags(session, FlagType.LATE_REFILL) == []


async def test_withdrawal_alone_seats_the_backlog(world, session) -> None:
    inst = await world.institution()
    it = await world.programme(inst, "IT", intakes={"2026-27": 20})
    full = await world.cohort(it, 19)
    backlog = await world.cohort(it, 2)
    first = await assign_seats(session, [e.id for e in full + backlog], actor_id=None)
    assert len(first.unseated) == 2
    await refresh_seat_flags(session, list(first.touched_pools))

    leaving = full[0]
    leaving.status = EnrolmentStatus.TRANSFERRED
    await session.flush()
    result = await assign_seats(session, [leaving.id], actor_id=None)
    assert result.released == [leaving.id]
    assert result.seated == [backlog[0].id]
    seat = await session.get(Seat, backlog[0].seat_id)
    assert seat.status is SeatStatus.ASSIGNED and seat.enrolment_id == backlog[0].id

    await refresh_seat_flags(session, list(result.touched_pools))
    [flag] = await _flags(session, FlagType.EXCESS_ADMISSION)
    assert flag.evidence["summary"] == (
        "20 admitted against 20 approved seats in IT (2026-27); 1 without a seat."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Most unseated at once"] == "2"
    assert flag.related_enrolment_ids == [backlog[1].id]


async def test_route_change_moves_the_seat(world, session) -> None:
    inst = await world.institution()
    cse = await world.programme(inst, "CSE")
    [enrolment] = await world.cohort(cse, 1)
    await assign_seats(session, [enrolment.id], actor_id=None)
    regular_seat = enrolment.seat_id

    enrolment.admission_route = AdmissionRoute.NRI
    await session.flush()
    result = await assign_seats(session, [enrolment.id], actor_id=None)
    assert result.released == [enrolment.id] and result.seated == [enrolment.id]
    seat = await session.get(Seat, enrolment.seat_id)
    assert seat.seat_code.startswith("CSE-N-")
    old = await session.get(Seat, regular_seat)
    assert old.status is SeatStatus.FREE and old.enrolment_id is None
    reasons = (
        (
            await session.execute(
                select(SeatEvent.reason).where(SeatEvent.kind == SeatEventKind.RELEASE)
            )
        )
        .scalars()
        .all()
    )
    assert reasons == ["route or year changed"]


async def test_ciwg_students_take_reserved_international_seats(world, session) -> None:
    inst = await world.institution()
    cse = await world.programme(inst, "CSE", intakes={"2026-27": 20})  # 3 international, 1 CIWG
    foreign = [
        await world.enrol(
            await world.student(f"Foreign {i}", nationality="BD", passport=f"N100000{i}"),
            cse,
            route=AdmissionRoute.INTERNATIONAL,
            row_no=2 + i,
        )
        for i in range(3)
    ]
    ciwg = await world.enrol(
        await world.student("Gulf Child", passport="Z9000001"),
        cse,
        route=AdmissionRoute.INTERNATIONAL,
        row_no=10,
    )
    result = await assign_seats(session, [e.id for e in foreign + [ciwg]], actor_id=None)
    assert result.unseated == [foreign[2].id]
    reserved = (await session.execute(select(Seat).where(Seat.reserved_for == "CIWG"))).scalar_one()
    assert reserved.enrolment_id == ciwg.id
    await refresh_seat_flags(session, list(result.touched_pools))
    [flag] = await _flags(session)
    assert flag.type is FlagType.QUOTA_BREACH
    assert flag.evidence["summary"] == (
        "4 International admissions against 3 International seats in CSE (2026-27)."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Rule percentage"] == "15% of approved intake 20"
