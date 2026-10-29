"""Week 2 read endpoints over engine output: flags, enrolment detail, rechecks, counts.

One world for the module: ABC (Maharashtra, West, affiliated to MSTU) and XYZ (Tamil
Nadu, South). ABC CSE has 21 Regular-route admissions against an intake of 20
(19 Regular seats, so 2 without one), an R. K. Sharma copy of Ravi Kumar Sharma, and a
student whose APAAR check met an outage. One APAAR is ACTIVE at both colleges in
physical programmes; at ABC it was admitted first, so it holds CSE-R-001.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import session_factory
from app.engine.status import refresh
from app.engine.suite import DefaultEngines
from app.main import app
from app.models.audit import AuditLog
from app.models.enums import AdmissionRoute, FlagType, UserRole
from app.models.geo import University
from app.models.user import User
from app.models.verification import Flag
from tests.conftest import PASSWORD, login_as, truncate_all
from tests.engines.conftest import World, adapters

DOB = date(2007, 3, 21)
RAVI_APAAR = "123456784417"
ASHA_APAAR = "987654320011"
TWIN_APAAR = "555566667777"


@dataclass
class Ids:
    abc: uuid.UUID
    xyz: uuid.UUID
    cse: uuid.UUID
    ravi: uuid.UUID
    rk: uuid.UUID
    asha: uuid.UUID
    twin_abc: uuid.UUID
    twin_xyz: uuid.UUID
    unseated: list[uuid.UUID]


@pytest.fixture(scope="module")
async def ids() -> AsyncIterator[Ids]:
    await truncate_all()
    gov = adapters()
    async with session_factory()() as session:
        world = World(session)
        mh = await world.state("MH", "Maharashtra", "WEST")
        mstu = University(
            code="MSTU", name="Maharashtra State Technical University", state_id=mh.id
        )
        session.add(mstu)
        await session.flush()
        abc = await world.institution("ABC College of Engineering", "1-ABC-0001", university=mstu)
        xyz = await world.institution(
            "XYZ Institute of Technology", "1-XYZ-0002", "TN", "Tamil Nadu", "SOUTH"
        )
        cse = await world.programme(abc, "CSE", intakes={"2026-27": 20})
        it = await world.programme(xyz, "IT", name="B.Tech Information Technology")
        batch = await world.batch(abc, "1-ABC-0001_2026-27.csv")
        ravi_student = await world.student(
            "Ravi Kumar Sharma", DOB, apaar=RAVI_APAAR, mobile="9876504521"
        )
        ravi = await world.enrol(ravi_student, cse, batch=batch, row_no=2)
        asha = await world.enrol(
            await world.student("Asha Patil", date(2007, 11, 2), apaar=ASHA_APAAR),
            cse,
            batch=batch,
            row_no=3,
        )
        world.next_row = 4
        others = await world.cohort(cse, 17, batch=batch)
        rk = await world.enrol(
            await world.student("R. K. Sharma", DOB, mobile="9876504521"),
            cse,
            batch=batch,
            row_no=40,
        )
        twin = await world.student("Kiran Rao", date(2006, 5, 5), apaar=TWIN_APAAR)
        twin_abc = await world.enrol(
            twin,
            cse,
            route=AdmissionRoute.MANAGEMENT,
            batch=batch,
            row_no=41,
            admission_date=date(2026, 7, 15),
        )
        twin_xyz = await world.enrol(twin, it)
        users = [
            ("admin@aicte.demo", UserRole.AICTE_ADMIN, {}),
            ("ro.west@aicte.demo", UserRole.RO_OFFICER, {"region_id": world.regions["WEST"].id}),
            ("ro.south@aicte.demo", UserRole.RO_OFFICER, {"region_id": world.regions["SOUTH"].id}),
            ("registrar@abc.edu.demo", UserRole.INSTITUTION, {"institution_id": abc.id}),
            ("registrar@xyz.edu.demo", UserRole.INSTITUTION, {"institution_id": xyz.id}),
            ("coe@univ.demo", UserRole.UNIVERSITY, {"university_id": mstu.id}),
            ("student@demo", UserRole.STUDENT, {"student_id": ravi_student.id}),
        ]
        hashed = hash_password(PASSWORD)
        for email, role, scope in users:
            session.add(User(email=email, password_hash=hashed, name=email, role=role, **scope))

        abc_ids = [ravi.id, asha.id, *(e.id for e in others), rk.id, twin_abc.id]
        suite = DefaultEngines()
        ledger = await suite.assign_seats(session, abc_ids + [twin_xyz.id], actor_id=None)
        gov.apaar.registry[RAVI_APAAR] = {"name": "Ravi Kumar Sharma", "dob": DOB}
        gov.apaar.registry[TWIN_APAAR] = {"name": "Kiran Rao", "dob": date(2006, 5, 5)}
        await suite.run_checks(session, [i for i in abc_ids if i != asha.id] + [twin_xyz.id], gov)
        gov.apaar.down = True
        await suite.run_checks(session, [asha.id], gov)
        await suite.detect_duplicates(session, abc.id, "2026-27", abc_ids)
        await suite.refresh_seat_flags(session, list(ledger.touched_pools))
        # as at the end of an upload batch, after the duplicate and seat flags
        await refresh(session, [*abc_ids, twin_xyz.id], issue=False)
        await session.commit()
        result = Ids(
            abc=abc.id,
            xyz=xyz.id,
            cse=cse.id,
            ravi=ravi.id,
            rk=rk.id,
            asha=asha.id,
            twin_abc=twin_abc.id,
            twin_xyz=twin_xyz.id,
            unseated=list(ledger.unseated),
        )
    yield result
    await truncate_all()


@pytest.fixture
async def as_role(ids):
    clients = []

    async def _login(email: str):
        client = await login_as(email)
        clients.append(client)
        return client

    yield _login
    for client in clients:
        await client.aclose()


async def _flag(flag_type: FlagType, institution_id: uuid.UUID) -> Flag:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(Flag).where(Flag.type == flag_type, Flag.institution_id == institution_id)
            )
        ).scalar_one()


# ----------------------------------------------------------------------- GET /flags


async def test_flag_list_for_officers(ids, as_role) -> None:
    admin = await as_role("admin@aicte.demo")
    body = (await admin.get("/flags")).json()
    types = sorted(i["type"] for i in body["items"])
    assert types == [
        "DUPLICATE_CROSS_INSTITUTION",
        "DUPLICATE_CROSS_INSTITUTION",
        "DUPLICATE_WITHIN_UPLOAD",
        "EXCESS_ADMISSION",
    ]
    assert (body["total"], body["institutions"]) == (4, 2)
    severities = [i["severity"] for i in body["items"]]
    assert severities == sorted(severities, key=["HIGH", "MEDIUM", "LOW"].index)
    excess = next(i for i in body["items"] if i["type"] == "EXCESS_ADMISSION")
    assert excess["summary"] == (
        "21 admitted against 20 approved seats in CSE (2026-27); 2 without a seat."
    )
    assert excess["related_count"] == 2 and excess["enrolment_id"] is None
    assert excess["programme"]["code"] == "CSE" and excess["assignee"] is None
    assert excess["institution"]["state_name"] == "Maharashtra"

    unresolved = (await admin.get("/flags", params={"status": "UNRESOLVED"})).json()
    assert unresolved["total"] == 4
    assert (await admin.get("/flags", params={"status": "OPEN,UPHELD"})).json()["total"] == 4
    assert (await admin.get("/flags", params={"status": "UPHELD"})).json()["total"] == 0
    bad = await admin.get("/flags", params={"status": "SHUT"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (await admin.get("/flags", params={"type": "EXCESS_ADMISSION"})).json()["total"] == 1
    assert (await admin.get("/flags", params={"severity": "MEDIUM"})).json()["total"] == 1
    assert (await admin.get("/flags", params={"state": "tn"})).json()["total"] == 1
    assert (await admin.get("/flags", params={"q": "without a seat"})).json()["total"] == 1
    assert (await admin.get("/flags", params={"q": "1-xyz"})).json()["total"] == 1
    newest = (await admin.get("/flags", params={"sort": "created_desc"})).json()["items"]
    assert [i["created_at"] for i in newest] == sorted(
        (i["created_at"] for i in newest), reverse=True
    )

    west = (await (await as_role("ro.west@aicte.demo")).get("/flags")).json()
    assert {i["institution"]["aicte_permanent_id"] for i in west["items"]} == {"1-ABC-0001"}
    south = (await (await as_role("ro.south@aicte.demo")).get("/flags")).json()
    assert [i["type"] for i in south["items"]] == ["DUPLICATE_CROSS_INSTITUTION"]


async def test_flag_list_scoping_and_redaction_for_a_college(ids, as_role) -> None:
    registrar = await as_role("registrar@abc.edu.demo")
    body = (await registrar.get("/flags")).json()
    assert body["total"] == 3 and body["institutions"] == 1
    cross = next(i for i in body["items"] if i["type"] == "DUPLICATE_CROSS_INSTITUTION")
    assert cross["summary"] == (
        "The same student appears as active here and at another institution in Tamil Nadu "
        "(2026-27)."
    )
    assert cross["related_count"] == 1  # the XYZ side is not counted for ABC
    assert (await registrar.get("/flags", params={"q": "XYZ"})).json()["total"] == 0
    for email in ("coe@univ.demo", "student@demo"):
        assert (await (await as_role(email)).get("/flags")).status_code == 403


# ------------------------------------------------------------------- GET /flags/{id}


async def test_cross_flag_detail_officer_and_college(ids, as_role) -> None:
    flag = await _flag(FlagType.DUPLICATE_CROSS_INSTITUTION, ids.abc)
    west = await as_role("ro.west@aicte.demo")
    officer = (await west.get(f"/flags/{flag.id}")).json()
    assert officer["summary"] == (
        "The same student appears as active at ABC College of Engineering and "
        "XYZ Institute of Technology (2026-27)."
    )
    assert officer["related_hidden"] == 0 and officer["related_count"] == 2
    # officers see both sides whatever the other side's region
    assert {r["institution"]["name"] for r in officer["related_enrolments"]} == {
        "ABC College of Engineering",
        "XYZ Institute of Technology",
    }
    labels = [f["value"] for f in officer["evidence"]["facts"]]
    assert "XYZ Institute of Technology: B.Tech Information Technology" in labels
    assert officer["enrolment"]["id"] == str(ids.twin_abc)
    assert officer["history"] == [] and officer["assignee"] is None

    registrar = await as_role("registrar@abc.edu.demo")
    college = (await registrar.get(f"/flags/{flag.id}")).json()
    assert college["summary"] == college["evidence"]["summary"]
    assert "XYZ" not in str(college)
    assert college["related_hidden"] == 1 and college["related_count"] == 1
    assert college["evidence"]["related_enrolment_ids"] == [str(ids.twin_abc)]
    assert [r["id"] for r in college["related_enrolments"]] == [str(ids.twin_abc)]
    assert "Another institution in Tamil Nadu: B.Tech Information Technology" in [
        f["value"] for f in college["evidence"]["facts"]
    ]
    for wire in (officer, college):
        text = str(wire)
        assert "audience" not in text and "summary_for_institution" not in text
        assert "'data'" not in text and "peak_unseated" not in text

    assert (await (await as_role("registrar@xyz.edu.demo")).get(f"/flags/{flag.id}")).json()[
        "error"
    ]["message"] == "Flag not found."
    assert (
        await (await as_role("ro.south@aicte.demo")).get(f"/flags/{flag.id}")
    ).status_code == 404
    assert (await registrar.get(f"/flags/{uuid.uuid4()}")).status_code == 404


async def test_excess_flag_detail_lists_the_unseated(ids, as_role) -> None:
    flag = await _flag(FlagType.EXCESS_ADMISSION, ids.abc)
    admin = await as_role("admin@aicte.demo")
    before = await _read_audits()
    body = (await admin.get(f"/flags/{flag.id}")).json()
    assert body["enrolment"] is None
    assert [r["id"] for r in body["related_enrolments"]] == [str(i) for i in ids.unseated]
    assert all(r["seat_code"] is None for r in body["related_enrolments"])
    assert body["evidence"]["facts"][0] == {
        "label": "Approved intake",
        "value": "20",
        "source": "AICTE approval 2026-27",
    }
    assert await _read_audits() == before + len(ids.unseated)


async def _read_audits() -> int:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == "READ")
            )
        ).scalar_one()


# -------------------------------------------------------------- GET /enrolments/{id}


async def test_enrolment_detail(ids, as_role) -> None:
    registrar = await as_role("registrar@abc.edu.demo")
    before = await _read_audits()
    body = (await registrar.get(f"/enrolments/{ids.ravi}")).json()
    assert await _read_audits() == before + 1
    assert body["institution"]["aicte_permanent_id"] == "1-ABC-0001"
    assert body["student"]["apaar_masked"] == "XXXX XXXX 4417"
    assert body["student"]["mobile_masked"] == "XXXXXX4521" and body["student"]["gender"] == "U"
    assert body["programme"]["mode"] == "PHYSICAL"
    assert body["cohort_year"] == "2026-27" and body["admission_date"] == "2026-08-01"
    assert body["upload"] == {
        "batch_id": body["upload"]["batch_id"],
        "filename": "1-ABC-0001_2026-27.csv",
        "row_no": 2,
    }
    assert body["seat"]["seat_code"] == "CSE-R-002" and body["seat"]["seat_type"] == "REGULAR"
    assert body["seat"]["assigned_at"].endswith("Z")
    assert [c["type"] for c in body["checks"]] == [
        "IDENTITY",
        "ADMISSION",
        "SEAT",
        "STUDYING",
        "STUDENT",
    ]
    identity = body["checks"][0]
    assert identity["status"] == "CONFIRMED" and identity["source"] == "APAAR"
    assert identity["attempts"] == 0 and identity["checked_at"].endswith("Z")
    assert (identity["supplied_by"], identity["independent"], identity["resolved"]) == (
        "APAAR registry",
        True,
        None,
    )
    assert identity["observed_at"].endswith("Z")
    studying = body["checks"][3]
    assert (studying["status"], studying["supplied_by"], studying["observed_at"]) == (
        "NOT_YET_DUE",
        "",
        None,
    )
    # one contradiction outranks the confirmations (D35)
    assert body["record_status"] == "UNDER_REVIEW"
    assert body["status_reason"] == "Joining record is contradicted."
    # no case covers the joining record yet, so the record's open case gives the next step
    assert body["next_step"] == (
        "Waiting for an officer to review the Duplicate within institution case."
    )
    assert body["record_status_at"].endswith("Z")
    assert "123456784417" not in str(body)
    assert body["countersign"]["score"] == {"passes": 2, "applicable": 4}  # counselling not found
    assert [f["type"] for f in body["flags"]] == ["DUPLICATE_WITHIN_UPLOAD"]
    assert body["flags"][0]["summary"] == (
        "Rows 2 and 40 of 1-ABC-0001_2026-27.csv describe the same student."
    )

    assert (await (await as_role("registrar@xyz.edu.demo")).get(f"/enrolments/{ids.ravi}")).json()[
        "error"
    ]["message"] == "Enrolment not found."
    assert (
        await (await as_role("ro.south@aicte.demo")).get(f"/enrolments/{ids.ravi}")
    ).status_code == 404
    assert (await (await as_role("student@demo")).get(f"/enrolments/{ids.ravi}")).status_code == 403


async def test_university_reads_affiliates_with_redaction(ids, as_role) -> None:
    university = await as_role("coe@univ.demo")
    body = (await university.get(f"/enrolments/{ids.twin_abc}")).json()
    [cross] = [f for f in body["flags"] if f["type"] == "DUPLICATE_CROSS_INSTITUTION"]
    assert cross["summary"] == (
        "The same student appears as active here and at another institution in Tamil Nadu "
        "(2026-27)."
    )
    assert (await university.get(f"/enrolments/{ids.twin_xyz}")).status_code == 404
    officer = (await (await as_role("admin@aicte.demo")).get(f"/enrolments/{ids.twin_abc}")).json()
    [cross] = [f for f in officer["flags"] if f["type"] == "DUPLICATE_CROSS_INSTITUTION"]
    assert "XYZ Institute of Technology" in cross["summary"]


# ---------------------------------------------------------------- enrolment list


async def test_enrolment_list_rows_and_filters(ids, as_role) -> None:
    admin = await as_role("admin@aicte.demo")
    url = f"/institutions/{ids.abc}/enrolments"
    body = (await admin.get(url, params={"page_size": 50})).json()
    assert body["total"] == 21
    rows = {r["id"]: r for r in body["items"]}
    ravi = rows[str(ids.ravi)]
    assert ravi["seat_code"] == "CSE-R-002"
    assert ravi["cohort_year"] == "2026-27" and ravi["status_date"] == "2026-08-01"
    assert [c["type"] for c in ravi["countersign"]["checks"]][0] == "IDENTITY"
    assert set(ravi["countersign"]["checks"][0]) == {"type", "status"}
    assert [f["type"] for f in ravi["flags"]] == ["DUPLICATE_WITHIN_UPLOAD"]
    rk = rows[str(ids.rk)]
    assert [f["type"] for f in rk["flags"]] == ["EXCESS_ADMISSION", "DUPLICATE_WITHIN_UPLOAD"]

    unseated = (await admin.get(url, params={"seated": "false"})).json()
    assert {r["id"] for r in unseated["items"]} == {str(i) for i in ids.unseated}
    seat_fail = (
        await admin.get(url, params={"check_status": "CONTRADICTED", "check_type": "SEAT"})
    ).json()
    assert seat_fail["total"] == len(ids.unseated)
    assert {r["record_status"] for r in seat_fail["items"]} == {"UNDER_REVIEW"}
    assert (await admin.get(url, params={"check_type": "SEAT"})).json()["total"] == 21
    pending = await admin.get(
        url, params={"check_status": "SOURCE_UNAVAILABLE", "check_type": "IDENTITY"}
    )
    assert [r["id"] for r in pending.json()["items"]] == [str(ids.asha)]
    flagged = (await admin.get(url, params={"flagged": "true", "page_size": 50})).json()
    assert flagged["total"] == 4  # the 2 unseated (one is R. K.), Ravi and the twin
    assert (await admin.get(url, params={"flagged": "false"})).json()["total"] == 17


# --------------------------------------------------------------- institutions + dashboard


async def test_institution_counts(ids, as_role) -> None:
    admin = await as_role("admin@aicte.demo")
    body = (await admin.get("/institutions")).json()
    assert [(i["aicte_permanent_id"], i["flags_open"]) for i in body["items"]] == [
        ("1-ABC-0001", 3),
        ("1-XYZ-0002", 1),
    ]
    abc = body["items"][0]
    assert (abc["approved_seats"], abc["admitted"], abc["enrolments"]) == (20, 21, 21)

    detail = (await admin.get(f"/institutions/{ids.abc}")).json()
    assert detail["flags_open"] == 3 and detail["admitted"] == 21
    [cse] = detail["programmes"]
    assert cse["mode"] == "PHYSICAL"
    assert (cse["enrolments"], cse["seated"], cse["unseated"]) == (21, 19, 2)
    assert cse["seated"] == sum(p["assigned"] for p in cse["pools"])
    assert detail["last_upload"]["status"] == "DONE"


async def test_dashboard_kpis(ids, as_role) -> None:
    admin = await as_role("admin@aicte.demo")
    body = (await admin.get("/dashboard/summary")).json()
    kpis = body["kpis"]
    assert (kpis["flags_open"], kpis["admitted"], kpis["enrolments"]) == (4, 22, 22)
    assert kpis["countersigned_pct"] == 0.0  # STUDENT is pending for everyone
    assert "clear_pct" not in kpis and sum(kpis["records"].values()) == kpis["enrolments"]
    by_type = {f["type"]: f["open"] for f in body["flags_by_type"]}
    assert list(by_type)[:3] == ["EXCESS_ADMISSION", "QUOTA_BREACH", "LATE_REFILL"]
    assert by_type["DUPLICATE_CROSS_INSTITUTION"] == 2 and by_type["EXCESS_ADMISSION"] == 1
    assert len(by_type) == len(FlagType)
    mh = next(s for s in body["by_state"] if s["state_code"] == "MH")
    assert (mh["flags_open"], mh["admitted"]) == (3, 21)
    south = next(r for r in body["by_region"] if r["region"] == "SOUTH")
    assert south["flags_open"] == 1

    college = (await (await as_role("registrar@abc.edu.demo")).get("/dashboard/summary")).json()
    assert college["kpis"]["flags_open"] == 3
    assert sum(f["open"] for f in college["flags_by_type"]) == 3


async def test_student_sees_real_countersign(ids, as_role) -> None:
    body = (await (await as_role("student@demo")).get("/students/me")).json()
    [enrolment] = body["enrolments"]
    assert enrolment["countersign"]["score"] == {"passes": 2, "applicable": 4}
    assert len(enrolment["countersign"]["checks"]) == 5


# ---------------------------------------------------------------------- rechecks


async def test_enrolment_recheck_after_the_source_is_back(ids, as_role) -> None:
    gov = adapters()
    gov.apaar.registry[ASHA_APAAR] = {"name": "Asha Patil", "dob": date(2007, 11, 2)}
    previous = getattr(app.state, "adapters", None)
    app.state.adapters = gov
    try:
        for email in ("coe@univ.demo", "student@demo"):
            response = await (await as_role(email)).post(f"/enrolments/{ids.asha}/recheck", json={})
            assert response.status_code == 403
        other = await as_role("registrar@xyz.edu.demo")
        assert (await other.post(f"/enrolments/{ids.asha}/recheck", json={})).status_code == 404

        registrar = await as_role("registrar@abc.edu.demo")
        gov.apaar.down = True
        still = (await registrar.post(f"/enrolments/{ids.asha}/recheck", json={})).json()
        assert still["results"] == [
            {"type": "IDENTITY", "before": "SOURCE_UNAVAILABLE", "after": "SOURCE_UNAVAILABLE"}
        ]

        gov.apaar.down = False
        body = (await registrar.post(f"/enrolments/{ids.asha}/recheck", json={})).json()
        assert body["enrolment_id"] == str(ids.asha)
        assert body["rechecked"] == 1
        assert body["results"] == [
            {"type": "IDENTITY", "before": "SOURCE_UNAVAILABLE", "after": "CONFIRMED"}
        ]
        assert body["flags_raised"] == 0
        assert body["countersign"]["checks"][0] == {"type": "IDENTITY", "status": "CONFIRMED"}
        detail = (await registrar.get(f"/enrolments/{ids.asha}")).json()
        assert detail["checks"][0]["attempts"] == 2

        nothing = (await registrar.post(f"/enrolments/{ids.asha}/recheck", json={})).json()
        assert (nothing["rechecked"], nothing["results"]) == (0, [])
    finally:
        app.state.adapters = previous


async def test_institution_recheck(ids, as_role) -> None:
    previous = getattr(app.state, "adapters", None)
    gov = adapters()
    gov.apaar.down = True  # whatever is still pending stays pending
    app.state.adapters = gov
    try:
        url = f"/institutions/{ids.abc}/recheck"
        assert (
            await (await as_role("registrar@abc.edu.demo")).post(url, json={})
        ).status_code == 403
        assert (await (await as_role("ro.south@aicte.demo")).post(url, json={})).status_code == 404
        west = await as_role("ro.west@aicte.demo")
        body = (await west.post(url, json={"academic_year": "2026-27"})).json()
        assert body["institution_id"] == str(ids.abc) and body["academic_year"] == "2026-27"
        assert body["enrolments"] == body["rechecked"] == body["still_pending"]
        assert body["now_pass"] == body["now_fail"] == body["now_na"] == 0
        assert body["flags_raised"] == 0 and body["duration_ms"] >= 0
        assert (await west.post(url)).status_code == 200  # the body is optional
    finally:
        app.state.adapters = previous


async def test_institution_recheck_is_rate_limited_per_user(ids, as_role) -> None:
    from app.core.ratelimit import limiter

    previous = getattr(app.state, "adapters", None)
    app.state.adapters = adapters()
    limiter.reset()
    limiter.enabled = True
    try:
        url = f"/institutions/{ids.abc}/recheck"
        west = await as_role("ro.west@aicte.demo")
        statuses = [(await west.post(url, json={})).status_code for _ in range(7)]
        assert statuses == [200] * 6 + [429]
        limited = await west.post(url, json={})
        assert limited.json()["error"]["details"]["retry_after"] == 60
        admin = await as_role("admin@aicte.demo")  # another user has their own allowance
        assert (await admin.post(url, json={})).status_code == 200
    finally:
        limiter.enabled = False
        limiter.reset()
        app.state.adapters = previous
