"""A programme-level case is decided record by record and closes only when no record it
names is outstanding; UPHOLD needs the approval version that covers its admissions
(D43; API_CONTRACT §A4.10, §A4.11)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, update

from app.db.session import session_factory
from app.engine.ledger import assign_seats
from app.models.enums import FlagStatus, SeatStatus
from app.models.institution import Approval, ApprovalVersion
from app.models.seat import Seat
from app.models.verification import CaseAction
from tests.decisions.conftest import cohort, decide, excess_case, flag, regular_pool


async def test_withdrawing_some_excess_records_keeps_the_case_open(dw) -> None:
    ids = await cohort(dw, 31)  # 19 Regular seats: 12 admissions beyond the intake
    seated, excess = ids[:19], ids[19:]
    case = await excess_case(dw)
    admin = await dw.login("admin@aicte.demo")
    url = f"/flags/{case}/actions"

    detail = (await admin.get(f"/flags/{case}")).json()
    assert (detail["scope"], detail["covers"]) == ("MULTI_RECORD", "SEAT")
    assert detail["outstanding_enrolment_ids"] == [str(i) for i in excess]
    assert detail["approval"] == {
        "id": str(dw.approval),
        "current_version": 1,
        "approved_intake": 20,
        "covers": False,
    }

    # a multi-record withdrawal names its records, and only records the case names
    none = await admin.post(url, json=decide("WITHDRAW", "BEYOND_APPROVED_INTAKE"))
    assert none.status_code == 422 and none.json()["error"]["code"] == "WITHDRAW_NONE_SELECTED"
    stranger = await admin.post(
        url,
        json=decide(
            "WITHDRAW",
            "BEYOND_APPROVED_INTAKE",
            withdrawn_enrolment_ids=[str(excess[0]), str(seated[0])],
        ),
    )
    assert stranger.status_code == 409
    assert stranger.json()["error"]["details"]["n"] == 1

    two = await admin.post(
        url,
        json=decide(
            "WITHDRAW",
            "BEYOND_APPROVED_INTAKE",
            withdrawn_enrolment_ids=[str(excess[0]), str(excess[1])],
        ),
    )
    assert two.status_code == 200, two.text
    body = two.json()
    assert body["status"] == "OPEN" and body["effects"]["case_status"] == "OPEN"
    assert body["decision"] is None
    assert len(body["outstanding_enrolment_ids"]) == 10
    assert body["history"][-1]["withdrawn_enrolment_ids"] == [str(excess[0]), str(excess[1])]
    assert (body["history"][-1]["from_status"], body["history"][-1]["to_status"]) == (
        "OPEN",
        "OPEN",
    )
    assert body["effects"]["seats_released"] == []  # they held none

    # one more record corrected into the free NRI seat is no longer outstanding
    corrected = await admin.post(
        url,
        json=decide(
            "CORRECT",
            "WRONG_SEAT_CATEGORY",
            correction={
                "enrolment_id": str(excess[2]),
                "fields": {"admission_route": "NRI", "nri_sponsored": True},
            },
        ),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "OPEN"
    assert len(corrected.json()["outstanding_enrolment_ids"]) == 9

    # without a covering approval version the claim cannot be upheld
    no_version = await admin.post(url, json=decide("UPHOLD", "APPROVAL_VERSION_COVERS"))
    assert no_version.status_code == 422
    assert no_version.json()["error"]["details"]["fields"][0]["field"] == "approval_version"
    refused = await admin.post(
        url, json=decide("UPHOLD", "APPROVAL_VERSION_COVERS", approval_version=1)
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "UPHOLD_NEEDS_VERSION"
    assert refused.json()["error"]["details"] == {"current_version": 1, "covers": False}

    rest = [str(i) for i in excess[3:]]
    closed = await admin.post(
        url, json=decide("WITHDRAW", "BEYOND_APPROVED_INTAKE", withdrawn_enrolment_ids=rest)
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "WITHDRAWN"
    assert closed.json()["outstanding_enrolment_ids"] == []
    assert (await flag(case)).resolved_at is not None
    async with session_factory()() as session:
        rows = (
            (await session.execute(select(CaseAction).where(CaseAction.flag_id == case)))
            .scalars()
            .all()
        )
    assert [(r.action.value, r.to_status) for r in rows] == [
        ("WITHDRAW", FlagStatus.OPEN),
        ("CORRECT", FlagStatus.OPEN),
        ("WITHDRAW", FlagStatus.WITHDRAWN),
    ]


async def test_uphold_under_the_version_that_covers_the_admissions(dw) -> None:
    ids = await cohort(dw, 22)  # 3 beyond the 19 Regular seats
    case = await excess_case(dw)
    # what a new approval version does (ENGINES §17.5): more seats, the backlog seated
    pool = await regular_pool(dw)
    async with session_factory()() as session:
        session.add(
            ApprovalVersion(
                approval_id=dw.approval,
                version=2,
                approved_intake=24,
                effective_from=date(2026, 10, 1),
                source="AICTE EoA 2026-27, revised",
            )
        )
        await session.execute(
            update(Approval)
            .where(Approval.id == dw.approval)
            .values(current_version=2, approved_intake=24)
        )
        for n in range(3):
            session.add(
                Seat(pool_id=pool.id, seat_code=f"CSE-R-{90 + n:03d}", status=SeatStatus.FREE)
            )
        await session.flush()
        await assign_seats(session, ids[19:], actor_id=None)
        await session.commit()
    admin = await dw.login("admin@aicte.demo")
    detail = (await admin.get(f"/flags/{case}")).json()
    assert detail["approval"]["covers"] is True and detail["approval"]["current_version"] == 2
    old = await admin.post(
        f"/flags/{case}/actions",
        json=decide("UPHOLD", "APPROVAL_VERSION_COVERS", approval_version=1),
    )
    assert old.status_code == 409
    upheld = await admin.post(
        f"/flags/{case}/actions",
        json=decide("UPHOLD", "APPROVAL_VERSION_COVERS", approval_version=2),
    )
    assert upheld.status_code == 200, upheld.text
    body = upheld.json()
    assert body["status"] == "UPHELD"
    assert body["effects"]["approval"] == {
        "version": 2,
        "approved_intake": 24,
        "cohort_year": "2026-27",
        "programme_code": "CSE",
    }
    assert body["history"][-1]["approval_version"] == 2
