"""The student's privacy rights over HTTP (D30, API_CONTRACT §A3.22): the public notice,
consents and their withdrawal, the access log, the export and data requests."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core import audit
from app.core.audit import AuditEntry
from app.credentials import holder
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.credential import Consent, Credential, CredentialPresentation, DataRequest
from app.models.enums import (
    AuditAction,
    ConsentPurpose,
    ConsentState,
    NoticeChannel,
)
from app.models.verification import Notification
from app.privacy import service as privacy
from app.privacy.notice import WITHDRAW_TEXTS
from tests.cases.conftest import RAVI_APAAR, add_credential, new_flag


async def give(student_id: uuid.UUID, purpose: ConsentPurpose) -> None:
    async with session_factory()() as session:
        await privacy.record_consent(
            session,
            student_id=student_id,
            purpose=purpose,
            status=ConsentState.GIVEN,
            channel="PORTAL",
            notice_text=f"{purpose.value} text",
        )
        await session.commit()


async def clear_consents(student_id: uuid.UUID) -> None:
    async with session_factory()() as session:
        rows = (
            await session.execute(select(Consent).where(Consent.student_id == student_id))
        ).scalars()
        for row in rows:
            await session.delete(row)
        await session.commit()


async def read_entry(entity_type: str, entity_id, actor_id=None, after=None) -> None:
    async with session_factory()() as session:
        await audit.record_many(
            session,
            [
                AuditEntry(
                    action=AuditAction.READ,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    actor_id=actor_id,
                    after=after,
                )
            ],
        )
        await session.commit()


async def notification(cw) -> uuid.UUID:
    async with session_factory()() as session:
        row = Notification(
            student_id=cw.ravi_student,
            enrolment_id=cw.ravi,
            channel=NoticeChannel.EMAIL,
            token_hash=uuid.uuid4().hex,
            message="notice",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(row)
        await session.commit()
        return row.id


async def test_the_privacy_notice_is_public(client) -> None:
    body = (await client.get("/privacy/notice")).json()
    assert body["version"] == "v1" and body["effective_from"] == "2026-10-28"
    assert body["title"] == "How Countersign uses your data"
    assert body["sections"][0]["id"] == "what_we_hold"
    assert all(set(s) == {"id", "heading", "body"} for s in body["sections"])
    assert set(body["consent_texts"]) == {"APAAR_LINK", "NOTICE", "CREDENTIAL_SHARE"}
    assert "{institution_name}" in body["consent_texts"]["APAAR_LINK"]
    assert "\u2014" not in json.dumps(body, ensure_ascii=False)  # no dashes in the notice


async def test_consents_list_and_notice_withdrawal(cw, logins) -> None:
    await clear_consents(cw.ravi_student)
    student = await logins("student@demo")
    empty = (await student.get("/students/me/consents")).json()
    assert empty == {
        "current": [
            {"purpose": "APAAR_LINK", "status": "NONE", "since": None, "can_withdraw": False},
            {"purpose": "NOTICE", "status": "NONE", "since": None, "can_withdraw": True},
            {
                "purpose": "CREDENTIAL_SHARE",
                "status": "NONE",
                "since": None,
                "can_withdraw": False,
            },
        ],
        "items": [],
    }

    # nothing given yet: the choice is kept as one WITHDRAWN row
    first = await student.post("/students/me/consents/NOTICE/withdraw", json={})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["presentations_expired"] == 0
    assert body["current"][1]["status"] == "WITHDRAWN" and body["current"][1]["since"]
    assert body["current"][1]["can_withdraw"] is False
    [row] = body["items"]
    assert (row["purpose"], row["status"], row["channel"]) == ("NOTICE", "WITHDRAWN", "PORTAL")
    assert row["notice_text"] == WITHDRAW_TEXTS[ConsentPurpose.NOTICE]
    async with session_factory()() as session:
        assert await privacy.notice_consent_withdrawn(session, [cw.ravi_student]) == {
            cw.ravi_student
        }
    again = (await student.post("/students/me/consents/NOTICE/withdraw")).json()
    assert len(again["items"]) == 1

    # a later Yes gives it again; withdrawing turns that row, and only it, to WITHDRAWN
    await give(cw.ravi_student, ConsentPurpose.NOTICE)
    given = (await student.get("/students/me/consents")).json()
    assert given["current"][1]["status"] == "GIVEN" and given["current"][1]["can_withdraw"]
    after = (await student.post("/students/me/consents/NOTICE/withdraw", json={})).json()
    assert len(after["items"]) == 2
    assert after["items"][0]["status"] == "WITHDRAWN" and after["items"][0]["withdrawn_at"]
    async with session_factory()() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type == "consent", AuditLog.action == "UPDATE")
                    .order_by(AuditLog.seq.desc())
                    .limit(1)
                )
            )
            .scalars()
            .all()
        )
    assert entries[0].after == {"purpose": "NOTICE", "status": "WITHDRAWN"}
    assert entries[0].actor_id == cw.users["student@demo"]


async def test_apaar_and_unknown_purposes_cannot_be_withdrawn(cw, logins) -> None:
    student = await logins("student@demo")
    apaar = await student.post("/students/me/consents/APAAR_LINK/withdraw", json={})
    assert apaar.status_code == 422
    assert apaar.json()["error"]["details"]["fields"] == [
        {
            "field": "purpose",
            "message": "To unlink your APAAR, send a correction request. Your college must "
            "upload your record again; your admission is not affected.",
        }
    ]
    assert (await student.post("/students/me/consents/EVERYTHING/withdraw")).status_code == 422
    for email in ("admin@aicte.demo", "registrar@abc.edu.demo", "coe@univ.demo"):
        client = await logins(email)
        assert (await client.get("/students/me/consents")).status_code == 403
        assert (await client.post("/students/me/consents/NOTICE/withdraw")).status_code == 403


async def test_withdrawing_share_consent_expires_live_proofs(cw, logins, monkeypatch) -> None:
    await clear_consents(cw.ravi_student)
    credential_id = await add_credential(cw.ravi_student, cw.asha)
    now = datetime.now(UTC)
    async with session_factory()() as session:
        live = CredentialPresentation(
            credential_id=credential_id,
            code_hash=uuid.uuid4().hex * 2,
            presentation="x~y~z",
            disclosed=["institution", "programme"],
            expires_at=now + timedelta(minutes=10),
        )
        session.add(live)
        await session.commit()
    await give(cw.ravi_student, ConsentPurpose.CREDENTIAL_SHARE)
    await give(cw.ravi_student, ConsentPurpose.CREDENTIAL_SHARE)

    calls = []

    async def expire(session, student_id, *, now):
        # stands in for the wallet's own expiry of every live share of the student
        calls.append(student_id)
        result = await session.execute(
            update(CredentialPresentation)
            .where(
                CredentialPresentation.credential_id.in_(
                    select(Credential.id).where(Credential.student_id == student_id)
                ),
                CredentialPresentation.expires_at > now,
            )
            .values(expires_at=now)
        )
        return result.rowcount

    monkeypatch.setattr(holder, "expire_live_presentations", expire)
    student = await logins("student@demo")
    before = (await student.get("/students/me/consents")).json()["current"][2]
    assert before["status"] == "GIVEN" and before["can_withdraw"] is True

    body = (await student.post("/students/me/consents/CREDENTIAL_SHARE/withdraw", json={})).json()
    assert body["presentations_expired"] == 1 and calls == [cw.ravi_student]
    assert body["current"][2]["status"] == "WITHDRAWN"
    assert body["current"][2]["can_withdraw"] is False
    assert [i["status"] for i in body["items"] if i["purpose"] == "CREDENTIAL_SHARE"] == [
        "WITHDRAWN",
        "WITHDRAWN",
    ]
    async with session_factory()() as session:
        expired = await session.get(CredentialPresentation, live.id)
        assert expired.expires_at <= datetime.now(UTC)

    again = (await student.post("/students/me/consents/CREDENTIAL_SHARE/withdraw")).json()
    assert again["presentations_expired"] == 0


async def test_the_access_log_shows_roles_only_never_own_reads(cw, logins) -> None:
    student = await logins("student@demo")
    admin = await logins("admin@aicte.demo")
    west = await logins("ro.west@aicte.demo")
    registrar = await logins("registrar@abc.edu.demo")
    await student.get("/students/me")  # the student's own read
    assert (await admin.get(f"/enrolments/{cw.ravi}")).status_code == 200
    flag_id = await new_flag(cw)
    assert (await west.get(f"/flags/{flag_id}")).status_code == 200
    assert (await registrar.get(f"/enrolments/{cw.ravi}")).status_code == 200
    notice = await notification(cw)
    await read_entry("notification", notice, after={"via": "notice-link"})
    credential = await add_credential(cw.ravi_student, cw.ravi)
    await read_entry("credential", credential, after={"via": "degree-qr", "ip_hash": "ab12"})
    await read_entry("student", cw.ravi_student, cw.users["coe@univ.demo"], {"via": "degree-print"})
    await read_entry("student", cw.xyz_student, cw.users["admin@aicte.demo"])  # someone else

    response = await student.get("/students/me/access-log", params={"page_size": 200})
    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    assert all(set(i) == {"at", "role", "what"} for i in items)
    assert [(i["role"], i["what"]) for i in items[:6]] == [
        ("UNIVERSITY", "DEGREE"),
        ("VERIFIER", "CREDENTIAL"),
        ("NOTICE_LINK", "NOTICE"),
        ("INSTITUTION", "RECORD"),
        ("RO_OFFICER", "RECORD"),
        ("AICTE_ADMIN", "RECORD"),
    ]
    assert "STUDENT" not in {i["role"] for i in items}
    assert body["total"] == len(items)
    text = json.dumps(body)
    for leak in ("Regional Officer", "admin@", "@aicte", str(cw.users["admin@aicte.demo"])):
        assert leak not in text
    assert [i["at"] for i in items] == sorted((i["at"] for i in items), reverse=True)
    for email in ("admin@aicte.demo", "registrar@abc.edu.demo"):
        assert (await (await logins(email)).get("/students/me/access-log")).status_code == 403


ON = "2026-10-29"


def disclosure(key: str, value) -> str:
    raw = json.dumps(["c2FsdA", key, value]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def test_the_export_holds_everything_with_the_apaar_masked(cw, logins) -> None:
    student = await logins("student@demo")
    await new_flag(cw)
    credential_id = await add_credential(cw.ravi_student, cw.ravi)
    sd_jwt = "~".join(
        [
            "eyJhbGciOiJFUzI1NiJ9.e30.c2ln",
            disclosure("name", "Ravi Kumar Sharma"),
            disclosure("dob", "2007-03-21"),
            disclosure("institution", {"name": "ABC College of Engineering", "aicte_id": "1-A"}),
            disclosure("countersigned", {"checks": ["IDENTITY", "SEAT", "STUDENT"], "on": ON}),
            "",
        ]
    )  # fmt: skip
    async with session_factory()() as session:
        await session.execute(
            update(Credential).where(Credential.id == credential_id).values(sd_jwt=sd_jwt)
        )
        await session.commit()
    created = await student.post(
        "/students/me/data-requests",
        json={"kind": "CORRECTION", "details": "My date of birth is recorded wrongly."},
    )
    assert created.status_code == 201

    response = await student.get("/students/me/export.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        'attachment; filename="countersign-my-data.json"'
    )
    body = response.json()
    assert RAVI_APAAR not in response.text and "9876504521" not in response.text
    assert body["student"]["apaar_masked"] == "XXXX XXXX 4417"
    assert body["student"]["mobile_masked"] == "XXXXXX4521"
    assert body["privacy_notice_version"] == "v1"
    assert {e["institution_name"] for e in body["enrolments"]} == {"ABC College of Engineering"}
    flags = body["enrolments"][0]["flags"]
    assert flags and all("The name you uploaded differs" in f["summary"] for f in flags)
    assert "Meena" not in response.text and "Asha" not in response.text
    claims = next(c for c in body["credentials"] if c["id"] == str(credential_id))["claims"]
    assert claims == [
        {"key": "name", "label": "Name", "value": "Ravi Kumar Sharma"},
        {"key": "dob", "label": "Date of birth", "value": "21 Mar 2007"},
        {
            "key": "institution",
            "label": "Institution",
            "value": "ABC College of Engineering (1-A)",
        },
        {
            "key": "countersigned",
            "label": "Countersigned by",
            "value": "Identity, Seat and Student, as of 29 Oct 2026",
        },
    ]
    assert body["data_requests"][0]["kind"] == "CORRECTION"
    assert set(body) == {
        "generated_at",
        "privacy_notice_version",
        "student",
        "enrolments",
        "notices",
        "consents",
        "credentials",
        "presentations",
        "data_requests",
        "access_log",
    }
    async with session_factory()() as session:
        entry = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "student", AuditLog.action == "READ")
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
        ).scalar_one()
    assert entry.after == {"via": "export"} and entry.actor_id == cw.users["student@demo"]
    # the student's own export is not in their access log
    log = (await student.get("/students/me/access-log", params={"page_size": 200})).json()
    assert "EXPORT" not in {i["what"] for i in log["items"]}


async def test_data_requests_from_the_student_to_aicte(cw, logins) -> None:
    async with session_factory()() as session:
        await session.execute(DataRequest.__table__.delete())
        await session.commit()
    student = await logins("student@demo")
    admin = await logins("admin@aicte.demo")

    access = await student.post("/students/me/data-requests", json={"kind": "ACCESS"})
    assert access.status_code == 201
    body = access.json()
    assert (body["status"], body["response"]) == ("DONE", "Your data is ready to download.")
    assert body["export_path"] == "/students/me/export.json" and body["resolved_at"]

    missing = await student.post("/students/me/data-requests", json={"kind": "ERASURE"})
    assert missing.status_code == 422
    assert missing.json()["error"]["details"]["fields"][0] == {
        "field": "details",
        "message": "Write a few words so an officer knows what to do.",
    }
    someone_else = str(uuid.uuid4())
    other = await student.post(
        "/students/me/data-requests",
        json={"kind": "CORRECTION", "details": "Wrong programme.", "enrolment_id": someone_else},
    )
    assert other.status_code == 422
    assert other.json()["error"]["details"]["fields"][0]["field"] == "enrolment_id"
    correction = await student.post(
        "/students/me/data-requests",
        json={
            "kind": "CORRECTION",
            "details": "My date of birth is recorded wrongly.",
            "enrolment_id": str(cw.ravi),
        },
    )
    assert correction.status_code == 201
    row = correction.json()
    assert row["status"] == "OPEN" and row["export_path"] is None
    assert row["enrolment"] == {
        "id": str(cw.ravi),
        "institution_name": "ABC College of Engineering",
        "programme_name": "B.Tech Computer Science and Engineering",
        "academic_year": "2026-27",
    }
    erasure = await student.post(
        "/students/me/data-requests",
        json={"kind": "ERASURE", "details": "Please remove my mobile number."},
    )
    assert erasure.status_code == 201

    mine = (await student.get("/students/me/data-requests")).json()
    assert [i["kind"] for i in mine["items"]] == ["ERASURE", "CORRECTION", "ACCESS"]

    queue = (await admin.get("/data-requests")).json()
    assert [i["kind"] for i in queue["items"]] == ["CORRECTION", "ERASURE"]
    assert queue["items"][0]["student"] == {
        "id": str(cw.ravi_student),
        "name": "Ravi Kumar Sharma",
        "apaar_masked": "XXXX XXXX 4417",
        "provisional_id": None,
    }
    assert RAVI_APAAR not in str(queue)
    assert (await admin.get("/data-requests", params={"kind": "ACCESS"})).json()["total"] == 1

    url = f"/data-requests/{row['id']}/resolve"
    short = await admin.post(url, json={"status": "DONE", "response": "ok"})
    assert short.status_code == 422
    assert short.json()["error"]["details"]["fields"][0]["field"] == "response"
    done = await admin.post(
        url, json={"status": "DONE", "response": "Your college will upload the row again."}
    )
    assert done.status_code == 200, done.text
    resolved = done.json()
    assert resolved["status"] == "DONE" and resolved["resolved_at"]
    assert resolved["resolved_by"] == {
        "id": str(cw.users["admin@aicte.demo"]),
        "name": "AICTE Administrator",
    }
    twice = await admin.post(url, json={"status": "REJECTED", "response": "Changed my mind."})
    assert twice.status_code == 409
    assert twice.json()["error"]["details"] == {"reason": "ALREADY_RESOLVED"}
    assert twice.json()["error"]["message"] == "This request is already resolved."
    unknown = await admin.post(
        f"/data-requests/{uuid.uuid4()}/resolve",
        json={"status": "DONE", "response": "Nothing to do here."},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == "Data request not found."

    queue = (await admin.get("/data-requests")).json()
    assert [(i["kind"], i["status"]) for i in queue["items"]] == [
        ("ERASURE", "OPEN"),
        ("CORRECTION", "DONE"),
    ]
    reply = next(
        i for i in (await student.get("/students/me/data-requests")).json()["items"]
        if i["kind"] == "CORRECTION"
    )  # fmt: skip
    assert reply["response"] == "Your college will upload the row again."

    for email in ("ro.west@aicte.demo", "registrar@abc.edu.demo", "student@demo"):
        client = await logins(email)
        assert (await client.get("/data-requests")).status_code == 403
    async with session_factory()() as session:
        reads = (
            await session.execute(
                select(AuditLog.actor_id).where(
                    AuditLog.entity_type == "student",
                    AuditLog.entity_id == cw.ravi_student,
                    AuditLog.action == "READ",
                    AuditLog.actor_id == cw.users["admin@aicte.demo"],
                )
            )
        ).all()
    assert len(reads) >= 3  # one per list of the queue


@pytest.mark.parametrize("path", ["/students/me/export.json", "/students/me/data-requests"])
async def test_only_the_student_reaches_their_own_data(cw, logins, path) -> None:
    for email in ("admin@aicte.demo", "registrar@abc.edu.demo", "coe@univ.demo"):
        assert (await (await logins(email)).get(path)).status_code == 403
