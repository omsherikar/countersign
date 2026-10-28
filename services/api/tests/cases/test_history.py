"""Case history: what the college may read of it, what CONFIRM leaves alone, what CLEAR
asks for, and the system note an engine refresh adds to a decided flag."""

from __future__ import annotations

import uuid

from sqlalchemy import select

import app.credentials as credentials
from app.db.session import session_factory
from app.models.credential import Credential
from app.models.enums import EnrolmentStatus
from app.models.seat import Seat
from app.models.student import Enrolment
from app.models.verification import Check
from tests.cases.conftest import add_credential, new_flag

PDF = b"%PDF-1.4\n%%EOF\n"


async def test_the_college_never_sees_assignments_or_internal_notes(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    west = await logins("ro.west@aicte.demo")
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw)
    url = f"/flags/{flag_id}/actions"
    senior = cw.users["senior@aicte.demo"]
    steps = [
        (west, {"action": "ASSIGN", "assignee_id": str(cw.users["ro.west@aicte.demo"])}),
        (west, {"action": "NOTE", "note": "Looks like a typing slip."}),
        (west, {"action": "REQUEST_DOCS", "note": "Send the admission form."}),
    ]
    for client, payload in steps:
        assert (await client.post(url, json=payload)).status_code == 200
    response = await registrar.post(
        f"/flags/{flag_id}/response",
        data={"note": "Form attached."},
        files=[("files", ("form.pdf", PDF, "application/pdf"))],
    )
    assert response.status_code == 201
    escalate = {"action": "ESCALATE", "note": "Same name twice.", "assignee_id": str(senior)}
    later = [
        (west, escalate),
        (admin, {"action": "CLEAR", "note": "The form settles it."}),
        (admin, {"action": "REOPEN", "note": "New information from the region."}),
    ]
    for client, payload in later:
        assert (await client.post(url, json=payload)).status_code == 200

    officer = (await west.get(f"/flags/{flag_id}")).json()["history"]
    assert [h["action"] for h in officer] == [
        "ASSIGN",
        "NOTE",
        "REQUEST_DOCS",
        "COLLEGE_RESPONSE",
        "ESCALATE",
        "CLEAR",
        "REOPEN",
    ]
    assert officer[0]["assignee"]["id"] == str(cw.users["ro.west@aicte.demo"])
    assert officer[0]["note"] is None
    assert officer[4]["assignee"] == {"id": str(senior), "name": "Senior AICTE Officer"}
    assert officer[1]["note"] == "Looks like a typing slip."
    assert officer[1]["actor"] == {
        "id": str(cw.users["ro.west@aicte.demo"]),
        "name": "Regional Officer, Western",
        "role": "RO_OFFICER",
    }

    college = (await registrar.get(f"/flags/{flag_id}")).json()["history"]
    assert [h["action"] for h in college] == [
        "NOTE",
        "REQUEST_DOCS",
        "COLLEGE_RESPONSE",
        "ESCALATE",
        "CLEAR",
        "REOPEN",
    ]
    notes = {h["action"]: h["note"] for h in college}
    assert notes == {
        "NOTE": None,
        "REQUEST_DOCS": "Send the admission form.",
        "COLLEGE_RESPONSE": "Form attached.",
        "ESCALATE": None,
        "CLEAR": "The form settles it.",
        "REOPEN": None,
    }
    assert all(h["assignee"] is None for h in college)
    assert "Senior AICTE Officer" not in str(college)
    assert college[2]["attachments"][0]["filename"] == "form.pdf"
    # status changes stay visible even where the words are kept back
    assert (college[3]["from_status"], college[3]["to_status"]) == ("DOCS_REQUESTED", "ESCALATED")


async def test_confirm_revokes_the_proof_and_touches_nothing_else(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw)
    credential_id = await add_credential(cw.ravi_student, cw.ravi)

    async def snapshot():
        async with session_factory()() as session:
            enrolment = await session.get(Enrolment, cw.ravi)
            seat = await session.get(Seat, enrolment.seat_id) if enrolment.seat_id else None
            checks = (
                await session.execute(
                    select(Check.type, Check.status).where(Check.enrolment_id == cw.ravi)
                )
            ).all()
            return (
                enrolment.status,
                enrolment.status_date,
                enrolment.seat_id,
                seat.status if seat else None,
                sorted(checks),
            )

    before = await snapshot()
    assert before[0] is EnrolmentStatus.ACTIVE and before[2] is not None
    response = await admin.post(
        f"/flags/{flag_id}/actions",
        json={"action": "CONFIRM", "note": "Confirmed with the registry."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONFIRMED"
    assert await snapshot() == before
    async with session_factory()() as session:
        credential = await session.get(Credential, credential_id)
    assert credential.revoked is True and credential.revoked_reason == "FLAG_CONFIRMED"
    assert credential.revoked_by_id == cw.users["admin@aicte.demo"]

    # a flag that names no enrolment confirms without touching any proof
    seat_flag = await new_flag(cw, institution="xyz")
    other = await add_credential(cw.xyz_student, await _xyz_enrolment(cw))
    confirmed = await admin.post(
        f"/flags/{seat_flag}/actions", json={"action": "CONFIRM", "note": "Excess confirmed."}
    )
    assert confirmed.status_code == 200
    async with session_factory()() as session:
        assert (await session.get(Credential, other)).revoked is False


async def _xyz_enrolment(cw) -> uuid.UUID:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(Enrolment.id).where(Enrolment.student_id == cw.xyz_student)
            )
        ).scalar_one()


async def test_clear_asks_for_a_proof_for_every_named_enrolment(cw, logins, monkeypatch) -> None:
    asked: list[uuid.UUID] = []

    async def spy(session, enrolment_id):
        asked.append(enrolment_id)
        return None

    monkeypatch.setattr(credentials, "issue_if_eligible", spy)
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw, related=[cw.ravi, cw.asha])
    response = await admin.post(
        f"/flags/{flag_id}/actions", json={"action": "CLEAR", "note": "Both genuine."}
    )
    assert response.status_code == 200
    assert asked == [cw.ravi, cw.asha]
