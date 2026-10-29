"""Completeness against the state admission authority and the reporting deadline (D40;
API_CONTRACT §A4.18; ENGINES §17.10): a college that left students out shows them by name
and roll number with a score below 100 and one MISSING_FROM_UPLOAD case; each college reads
on time, late or overdue."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.db.session import session_factory
from app.engine import completeness, status
from app.main import app
from app.models.audit import AuditLog
from app.models.enums import FlagStatus, FlagType, UploadKind, UploadSource, UploadStatus
from app.models.geo import Region, State
from app.models.institution import Programme
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.verification import CaseAction, Flag
from tests.decisions.conftest import (
    FakeAuthority,
    FakeJoining,
    authority_adapters,
    cohort,
    decide,
)
from tests.engines.conftest import World

YEAR = "2026-27"


def _uploaded(n: int, name: str, dob: date, code: str = "CSE") -> completeness.UploadedFact:
    return completeness.UploadedFact(
        enrolment_id=uuid.UUID(int=n), programme_code=code, dob=dob, name_normalised=name
    )


def test_match_and_deadline_states_are_pure() -> None:
    dob = date(2007, 3, 21)
    joinings = [
        FakeJoining("R1", "Ravi Kumar Sharma", dob, "CSE", date(2026, 8, 2)),
        FakeJoining("R2", "Ravi K Sharma", dob, "CSE", date(2026, 8, 2)),
        FakeJoining("R3", "Asha Patil", date(2007, 11, 2), "CSE", date(2026, 8, 3)),
        FakeJoining("R4", "Meena Iyer", date(2007, 6, 1), "ECE", date(2026, 8, 3)),
    ]
    uploaded = [
        _uploaded(1, "ravi kumar sharma", dob),
        _uploaded(2, "asha patil", date(2007, 11, 3)),  # another date of birth
        _uploaded(3, "meena iyer", date(2007, 6, 1), "CSE"),  # another programme
    ]
    pairs = completeness.match(joinings, uploaded)
    # one to one, best score first: the exact name takes the record
    assert [p[1] for p in pairs] == [uuid.UUID(int=1), None, None, None]

    deadline = date(2026, 9, 30)
    state = completeness.deadline_state
    on_time = datetime(2026, 9, 30, 18, 0, tzinfo=UTC)  # 23:30 IST on the day
    late = datetime(2026, 9, 30, 19, 0, tzinfo=UTC)  # 00:30 IST the day after
    assert state(deadline, on_time, date(2026, 10, 29)).value == "ON_TIME"
    assert state(deadline, late, date(2026, 10, 29)).value == "LATE"
    assert state(deadline, None, date(2026, 10, 29)).value == "OVERDUE"
    assert state(deadline, None, date(2026, 9, 30)).value == "NOT_DUE"
    assert completeness.pct(5, 7) == 71.4 and completeness.pct(0, 0) is None
    assert completeness.pct_words(100.0) == "100" and completeness.pct_words(71.4) == "71.4"


async def _students(ids: list[uuid.UUID]) -> list[tuple[str, date]]:
    async with session_factory()() as session:
        rows = await session.execute(
            select(Enrolment.id, Student.name, Student.dob)
            .join(Student, Student.id == Enrolment.student_id)
            .where(Enrolment.id.in_(ids))
        )
        found = {r.id: (r.name, r.dob) for r in rows.all()}
    return [found[i] for i in ids]


async def _batch(institution_id: uuid.UUID, at: datetime) -> None:
    async with session_factory()() as session:
        world = World(session)
        session.add(
            UploadBatch(
                institution_id=institution_id,
                academic_year=YEAR,
                filename="file.csv",
                kind=UploadKind.INITIAL,
                status=UploadStatus.DONE,
                source=UploadSource.SEED,
                uploaded_by=(await world.user()).id,
                created_at=at,
            )
        )
        await session.commit()


async def _reconcile(adapters, institution_id) -> completeness.Reconciliation:
    async with session_factory()() as session:
        result = await completeness.reconcile(session, adapters, institution_id, YEAR)
        await status.commit(session)
    return result


async def test_a_college_that_left_students_out(dw) -> None:
    ids = await cohort(dw, 5, rows=False)
    authority = FakeAuthority()
    joined = [
        FakeJoining(f"MHCET-2026-00{n}", name, dob, "CSE", date(2026, 8, 2))
        for n, (name, dob) in enumerate(await _students(ids), start=1)
    ]
    sneha = FakeJoining(
        "MHCET-2026-007731", "Sneha Kulkarni", date(2007, 5, 9), "CSE", date(2026, 8, 4),
        round=2, apaar_last4="8812",
    )  # fmt: skip
    omkar = FakeJoining(
        None, "Omkar Jadhav", date(2007, 1, 14), "CSE", date(2026, 8, 20),
        round=None, route="MANAGEMENT",
    )  # fmt: skip
    authority.publish("1-ABC-0001", YEAR, [*joined, sneha, omkar])
    adapters = authority_adapters(authority)

    result = await _reconcile(adapters, dw.abc)
    assert (result.joined, result.uploaded_and_joined, result.missing) == (7, 5, 2)
    assert result.completeness_pct == 71.4 and result.case_raised
    assert [s["name"] for s in result.missing_students] == ["Sneha Kulkarni", "Omkar Jadhav"]
    assert result.missing_students[0] == {
        "name": "Sneha Kulkarni",
        "roll_no": "MHCET-2026-007731",
        "programme_code": "CSE",
        "joined_on": "2026-08-04",
        "round": 2,
        "route": "COUNSELLING",
        "apaar_masked": "XXXX XXXX 8812",
    }

    async with session_factory()() as session:
        case = (
            await session.execute(select(Flag).where(Flag.type == FlagType.MISSING_FROM_UPLOAD))
        ).scalar_one()
    assert case.severity.value == "MEDIUM" and case.enrolment_id is None
    assert case.dedupe_key == f"MISSING_FROM_UPLOAD:{dw.abc}:{YEAR}"
    assert case.evidence["summary"] == (
        "2 students the Maharashtra admission authority lists as joined at ABC College of "
        "Engineering in 2026-27 are not in the college's uploads."
    )
    facts = {f["label"]: f["value"] for f in case.evidence["facts"]}
    assert facts["Joined (authority)"] == "7" and facts["Completeness"] == "71.4%"
    assert facts["Reporting deadline"] == "30 Sep 2026"
    # the case lists the students by masked id only
    assert facts["Missing students"] == "XXXX XXXX 8812, No id"
    assert "Sneha" not in str(case.evidence)

    # reconciling again changes nothing and raises nothing new
    again = await _reconcile(adapters, dw.abc)
    assert not again.case_raised and not again.case_updated

    registrar = await dw.login("registrar@abc.edu.demo")
    body = (await registrar.get(f"/institutions/{dw.abc}/completeness")).json()
    assert (body["joined"], body["uploaded_and_joined"], body["missing"]) == (7, 5, 2)
    assert body["completeness_pct"] == 71.4 and body["published"] is True
    assert body["deadline"] == "2026-09-30" and body["deadline_state"] == "OVERDUE"
    assert body["case"] == {"id": str(case.id), "status": "OPEN"}
    assert [s["roll_no"] for s in body["missing_students"]] == ["MHCET-2026-007731", None]
    assert body["institution"]["aicte_permanent_id"] == "1-ABC-0001"
    csv_text = (await registrar.get(f"/institutions/{dw.abc}/completeness.csv")).text
    assert "name,roll_no,programme_code,joined_on,round,route,apaar_masked" in csv_text
    assert "Sneha Kulkarni,MHCET-2026-007731,CSE,2026-08-04,2,COUNSELLING" in csv_text
    university = await dw.login("coe@univ.demo")
    counts = (await university.get(f"/institutions/{dw.abc}/completeness")).json()
    assert counts["missing"] == 2 and counts["missing_students"] == []
    assert (await university.get(f"/institutions/{dw.abc}/completeness.csv")).status_code == 403
    south = await dw.login("ro.south@aicte.demo")
    assert (await south.get(f"/institutions/{dw.abc}/completeness")).status_code == 404
    async with session_factory()() as session:
        reads = (
            (
                await session.execute(
                    select(AuditLog.after).where(
                        AuditLog.entity_type == "institution_score", AuditLog.action == "READ"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert reads == [{"via": "completeness", "missing": 2}] * 2

    # the case names its students to the officer and takes only an Uphold
    admin = await dw.login("admin@aicte.demo")
    detail = (await admin.get(f"/flags/{case.id}")).json()
    assert [s["name"] for s in detail["missing_students"]] == ["Sneha Kulkarni", "Omkar Jadhav"]
    assert "WITHDRAW" not in detail["allowed_actions"]
    upheld = await admin.post(
        f"/flags/{case.id}/actions", json=decide("UPHOLD", "MISSING_NOW_UPLOADED")
    )
    assert upheld.status_code == 200

    # the college uploads one of them: the evidence moves, the decision stays
    async with session_factory()() as session:
        world = World(session)
        programme = await session.get(Programme, dw.cse)
        student = await world.student("Sneha Kulkarni", date(2007, 5, 9))
        await world.enrol(student, programme)
        await session.commit()
    moved = await _reconcile(adapters, dw.abc)
    assert (moved.missing, moved.completeness_pct, moved.case_updated) == (1, 85.7, True)
    async with session_factory()() as session:
        case = await session.get(Flag, case.id)
        notes = (
            (
                await session.execute(
                    select(CaseAction.note).where(
                        CaseAction.flag_id == case.id, CaseAction.action == "SYSTEM_NOTE"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert case.status is FlagStatus.UPHELD
    today = completeness.today_ist()
    assert notes == [
        f"The college uploaded 1 of the missing students on {today.day} "
        f"{today.strftime('%b')} {today.year}; 1 still missing."
    ]

    # the authority down keeps the last result and says so
    authority.down = True
    down = await _reconcile(adapters, dw.abc)
    assert down.source_unavailable and down.missing == 1
    body = (await registrar.get(f"/institutions/{dw.abc}/completeness")).json()
    assert body["source_unavailable"] is True and body["missing"] == 1


async def test_deadline_states_and_the_officer_list(dw, monkeypatch) -> None:
    async with session_factory()() as session:
        world = World(session)
        world.regions["WEST"] = (
            await session.execute(select(Region).where(Region.code == "WEST"))
        ).scalar_one()
        world.states["MH"] = (
            await session.execute(select(State).where(State.code == "MH"))
        ).scalar_one()
        late = await world.institution("LMN Institute of Engineering", "1-LMN-0004")
        await world.programme(late, "CSE")
        await session.commit()
        late_id = late.id
    await _batch(dw.abc, datetime(2026, 9, 20, 6, 30, tzinfo=UTC))
    await _batch(late_id, datetime(2026, 10, 5, 6, 30, tzinfo=UTC))
    # XYZ has sent nothing and the deadline has passed
    authority = FakeAuthority()
    missing = FakeJoining("R9", "Not Uploaded", date(2007, 2, 2), "CSE", date(2026, 8, 1))
    authority.publish("1-ABC-0001", YEAR, [missing])
    monkeypatch.setattr(app.state, "adapters", authority_adapters(authority), raising=False)

    admin = await dw.login("admin@aicte.demo")
    refreshed = await admin.post("/completeness/refresh", json={"academic_year": YEAR})
    assert refreshed.status_code == 200, refreshed.text
    totals = refreshed.json()
    assert (totals["institutions"], totals["missing"], totals["cases_raised"]) == (3, 1, 1)
    assert (await (await dw.login("ro.west@aicte.demo")).post(
        "/completeness/refresh", json={"academic_year": YEAR}
    )).status_code == 403  # fmt: skip

    page = (await admin.get("/completeness", params={"academic_year": YEAR})).json()
    states = {i["institution"]["aicte_permanent_id"]: i["deadline_state"] for i in page["items"]}
    assert states == {"1-ABC-0001": "ON_TIME", "1-LMN-0004": "LATE", "1-XYZ-0002": "OVERDUE"}
    assert page["totals"]["deadline_states"] == {
        "NOT_DUE": 0,
        "ON_TIME": 1,
        "LATE": 1,
        "OVERDUE": 1,
    }
    assert page["deadline"] == "2026-09-30" and page["total"] == 3
    abc = next(i for i in page["items"] if i["institution"]["aicte_permanent_id"] == "1-ABC-0001")
    assert (abc["missing"], abc["completeness_pct"], abc["case_status"]) == (1, 0.0, "OPEN")
    # completeness ascending puts the lowest first, colleges with nothing joined last
    assert page["items"][0]["institution"]["aicte_permanent_id"] == "1-ABC-0001"
    late_only = (await admin.get("/completeness", params={"deadline_state": "LATE"})).json()
    assert [i["institution"]["name"] for i in late_only["items"]] == [
        "LMN Institute of Engineering"
    ]
    west = (await (await dw.login("ro.west@aicte.demo")).get("/completeness")).json()
    assert {i["institution"]["aicte_permanent_id"] for i in west["items"]} == {
        "1-ABC-0001",
        "1-LMN-0004",
    }
    registrar = await dw.login("registrar@abc.edu.demo")
    assert (await registrar.get("/completeness")).status_code == 403
