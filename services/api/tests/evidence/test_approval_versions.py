"""Approval versions in the Seat Ledger (D41; API_CONTRACT §A4.17; ENGINES §17.5).

Raising the intake adds seats, seats the backlog and makes the Seat rows cite the new
version; lowering it below the seats already assigned is refused and changes nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy import func, select

from app.approvals import service
from app.core.errors import ApiError
from app.db.session import session_factory
from app.engine import status
from app.engine.checks import run_checks
from app.engine.flags import refresh_seat_flags
from app.engine.ledger import assign_seats
from app.models.enums import CheckStatus, CheckType, FlagType, RecordStatus, SeatStatus, SeatType
from app.models.institution import Approval, ApprovalVersion, Institution, Programme
from app.models.seat import Seat, SeatPool
from app.models.student import Enrolment
from app.models.verification import Check, Flag
from tests.conftest import truncate_all


async def _cse(world, session, intake: int = 90, admitted: int = 100):
    inst = await world.institution(aicte_id="1-ABC-0001")
    cse = await world.programme(inst, intakes={"2026-27": intake})
    approval = (
        await session.execute(select(Approval).where(Approval.programme_id == cse.id))
    ).scalar_one()
    session.add(
        ApprovalVersion(
            approval_id=approval.id,
            version=1,
            approved_intake=intake,
            effective_from=date(2026, 3, 15),
            source="AICTE EoA 2026-27",
        )
    )
    cohort = await world.cohort(cse, admitted)
    ids = [e.id for e in cohort]
    ledger = await assign_seats(session, ids, actor_id=None)
    return approval, cohort, ledger


async def _capacity(session, approval, seat_type=SeatType.REGULAR) -> tuple[int, int]:
    pool = (
        await session.execute(
            select(SeatPool).where(
                SeatPool.approval_id == approval.id, SeatPool.seat_type == seat_type
            )
        )
    ).scalar_one()
    live = await session.scalar(
        select(func.count())
        .select_from(Seat)
        .where(Seat.pool_id == pool.id, Seat.status != SeatStatus.RELEASED)
    )
    return pool.capacity, live


async def test_raising_the_intake_seats_the_backlog_and_the_rows_cite_the_new_version(
    world, session, gov
) -> None:
    approval, cohort, ledger = await _cse(world, session)
    assert len(ledger.unseated) == 15  # 85 Regular seats inside an intake of 90
    await run_checks(session, [e.id for e in cohort], gov)
    await refresh_seat_flags(session, list(ledger.touched_pools))
    await status.settle(session, issue=False)
    unseated = cohort[-1]
    assert (await session.get(Enrolment, unseated.id)).record_status is RecordStatus.UNDER_REVIEW

    admin = await world.user()
    body = await service.add_version(
        session,
        admin,
        approval.id,
        approved_intake=120,
        effective_from=date(2026, 5, 20),
        source="AICTE EoA 2026-27, revised",
    )
    assert (body["current_version"], [v["version"] for v in body["items"]]) == (2, [2, 1])
    assert body["effects"]["seats_added"] >= 29  # Regular 85 to 114, NRI 5 to 6, ...
    assert body["effects"]["seated"] == 15
    assert await _capacity(session, approval) == (114, 114)
    seats = await session.scalar(
        select(func.count())
        .select_from(Enrolment)
        .where(Enrolment.id.in_([e.id for e in cohort]), Enrolment.seat_id.is_not(None))
    )
    assert seats == 100
    row = (
        await session.execute(
            select(Check)
            .where(Check.enrolment_id == unseated.id, Check.type == CheckType.SEAT)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.status is CheckStatus.CONFIRMED
    assert row.supplied_by == "AICTE approval v2, 2026-27 (Seat Ledger, derived)"
    assert row.detail["approval_version"] == 2
    # the excess case names nobody now, so the record is no longer under review
    excess = (
        await session.execute(select(Flag).where(Flag.type == FlagType.EXCESS_ADMISSION))
    ).scalar_one()
    assert excess.related_enrolment_ids == []
    record = await session.get(Enrolment, unseated.id)
    await session.refresh(record)
    assert record.record_status is not RecordStatus.UNDER_REVIEW
    assert body["effects"]["records_changed"] >= 15
    assert service.covers(approval, SeatType.REGULAR, 0)


async def test_lowering_below_the_assigned_seats_is_refused_and_changes_nothing(
    world, session
) -> None:
    approval, _cohort, _ = await _cse(world, session, intake=120, admitted=100)
    admin = await world.user()
    before = await _capacity(session, approval)
    with pytest.raises(ApiError) as refused:
        await service.add_version(
            session,
            admin,
            approval.id,
            approved_intake=60,
            effective_from=date(2026, 11, 1),
            source="AICTE EoA 2026-27, second revision",
        )
    assert (refused.value.status_code, refused.value.code) == (409, "APPROVAL_BELOW_ASSIGNED")
    details = refused.value.details
    assert (details["intake"], details["assigned"]) == (60, 100)
    assert {p["seat_type"]: (p["assigned"], p["new_capacity"]) for p in details["pools"]} == {
        "REGULAR": (100, 57)
    }
    assert (approval.current_version, approval.approved_intake) == (1, 120)
    assert await _capacity(session, approval) == before
    assert await session.scalar(select(func.count()).select_from(ApprovalVersion)) == 1


async def test_lowering_removes_free_seats_highest_first(world, session) -> None:
    approval, _cohort, _ = await _cse(world, session, intake=120, admitted=50)
    admin = await world.user()
    body = await service.add_version(
        session,
        admin,
        approval.id,
        approved_intake=100,
        effective_from=date(2026, 6, 1),
        source="AICTE EoA 2026-27, revised",
    )
    assert body["effects"]["seats_removed"] > 0
    assert await _capacity(session, approval) == (95, 95)
    codes = sorted(
        (
            await session.execute(
                select(Seat.seat_code)
                .join(SeatPool, SeatPool.id == Seat.pool_id)
                .where(SeatPool.approval_id == approval.id, SeatPool.seat_type == SeatType.REGULAR)
            )
        ).scalars()
    )
    assert codes[-1] == "CSE-R-095"


async def test_a_version_cannot_take_effect_before_the_current_one(world, session) -> None:
    approval, _cohort, _ = await _cse(world, session, admitted=1)
    with pytest.raises(ApiError) as refused:
        await service.add_version(
            session,
            await world.user(),
            approval.id,
            approved_intake=120,
            effective_from=date(2026, 1, 1),
            source="AICTE EoA 2026-27, revised",
        )
    assert refused.value.status_code == 422


# ----------------------------------------------------------------------- the api


@pytest.fixture
async def fresh() -> AsyncIterator[None]:
    await truncate_all()
    yield
    await truncate_all()


async def _abc_cse_approval() -> str:
    async with session_factory()() as session:
        return str(
            (
                await session.execute(
                    select(Approval.id)
                    .join(Programme, Programme.id == Approval.programme_id)
                    .join(Institution, Institution.id == Programme.institution_id)
                    .where(
                        Institution.aicte_permanent_id == "1-ABC-0001",
                        Programme.code == "CSE",
                        Approval.academic_year == "2026-27",
                    )
                )
            ).scalar_one()
        )


async def test_the_api_reads_and_adds_versions_within_scope(
    fresh, admin, ro_west, ro_south, registrar_abc, registrar_xyz, student
) -> None:
    approval_id = await _abc_cse_approval()
    url = f"/approvals/{approval_id}/versions"
    read = await registrar_abc.get(url)
    assert read.status_code == 200, read.text
    assert (read.json()["current_version"], read.json()["programme"]["code"]) == (1, "CSE")
    assert (await ro_west.get(url)).status_code == 200
    assert (await registrar_xyz.get(url)).status_code == 404
    assert (await ro_south.get(url)).json()["error"]["message"] == "Approval not found."
    assert (await student.get(url)).status_code == 403

    payload = {
        "approved_intake": 132,
        "effective_from": "2026-11-01",
        "source": "AICTE EoA 2026-27, second revision",
    }
    assert (await ro_west.post(url, json=payload)).status_code == 403
    assert (await registrar_abc.post(url, json=payload)).status_code == 403
    bad = await admin.post(url, json={**payload, "approved_intake": 0})
    assert bad.status_code == 422
    created = await admin.post(url, json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["current_version"] == 2
    assert body["items"][0] == {
        "version": 2,
        "approved_intake": 132,
        "effective_from": "2026-11-01",
        "source": "AICTE EoA 2026-27, second revision",
        "created_at": body["items"][0]["created_at"],
    }
    assert set(body["effects"]) == {
        "seats_added",
        "seats_removed",
        "seated",
        "flags_refreshed",
        "records_changed",
    }
