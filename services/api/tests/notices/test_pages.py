"""Notices and proofs on GET /students/me and GET /enrolments/{id}; proofs after rechecks
(API_CONTRACT §A3.6, §A3.7, ENGINES §16.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app import credentials
from app.credentials import holder
from app.db.session import session_factory
from app.models.enums import NoticeChannel
from app.models.verification import Notification
from app.notices.student_check import wire_time
from tests.notices.conftest import confirm_rows, delivered, notices_of, signed_in_owner

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER
NOTICE_KEYS = {
    "id", "channel", "state", "delivery_status", "attempts", "last_error", "sent_at",
    "expires_at", "response", "responded_at", "previous_response", "changed_at", "resent",
}  # fmt: skip


@pytest.fixture
def issued(monkeypatch) -> list:
    calls: list = []

    async def issue_if_eligible(session, enrolment_id):
        calls.append(enrolment_id)
        return None

    monkeypatch.setattr(credentials, "issue_if_eligible", issue_if_eligible)
    return calls


async def answer(token: str, response: str = "YES") -> None:
    """The notice's own student answers, signed in through DigiLocker (D37)."""
    async with await signed_in_owner(token) as student:
        reply = await student.post(f"/notices/{token}/respond", json={"response": response})
    assert reply.status_code == 200, reply.text


async def test_the_student_sees_their_notices_and_proofs(world, mailer, public, monkeypatch):
    enrolment, tokens = await delivered(world, mailer, digilocker=False)
    await answer(tokens[EMAIL])
    proof = {
        "id": "c1c1c1c1-3333-4444-8555-666677778888",
        "kind": "ENROLMENT",
        "status": "ACTIVE",
        "enrolment_id": str(enrolment.id),
        "institution_name": "ABC College of Engineering",
        "issued_at": "2026-10-29T06:10:00Z",
    }

    async def wallet_summary(session, student_id):
        assert student_id == enrolment.student_id
        return [proof]

    monkeypatch.setattr(holder, "wallet_summary", wallet_summary)
    student = await world.student_login(enrolment)
    body = (await student.get("/students/me")).json()
    await student.aclose()
    email, digi = await notices_of(enrolment.id)
    by_channel = {n["channel"]: n for n in body["notices"]}
    assert by_channel["EMAIL"] == {
        "id": str(email.id),
        "enrolment_id": str(enrolment.id),
        "channel": "EMAIL",
        "institution_name": "ABC College of Engineering",
        "programme_name": "B.Tech Computer Science and Engineering",
        "academic_year": "2026-27",
        "state": "ANSWERED",
        "delivery_status": "SENT",
        "sent_at": wire_time(email.sent_at),
        "expires_at": wire_time(email.expires_at),
        "response": "YES",
        "responded_at": wire_time(email.responded_at),
        "changed_at": None,
        "can_change_until": wire_time(email.responded_at + timedelta(days=7)),
    }
    assert (by_channel["DIGILOCKER"]["state"], by_channel["DIGILOCKER"]["delivery_status"]) == (
        "FAILED",
        "FAILED",
    )
    assert body["credentials"] == [proof]
    assert body["signed_in_with"] == "DIGILOCKER"
    [record] = body["enrolments"]
    [student_row] = [c for c in record["checks"] if c["type"] == "STUDENT"]
    assert (student_row["state"], student_row["independent"]) == ("CONFIRMED", True)
    assert (record["response"], record["can_respond"], record["decision"]) == ("YES", True, None)


async def test_notice_states_newest_first(world, mailer):
    enrolment, _ = await delivered(world, mailer, apaar=None)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()
    student = await world.student_login(enrolment)
    [notice] = (await student.get("/students/me")).json()["notices"]
    await student.aclose()
    assert notice["state"] == "EXPIRED"


async def test_enrolment_detail_lists_notices_resend_and_proofs(
    world, mailer, clients, monkeypatch
):
    enrolment, _ = await delivered(world, mailer, digilocker=False)
    ref = {
        "id": "c1c1c1c1-3333-4444-8555-666677778888",
        "kind": "ENROLMENT",
        "status": "ACTIVE",
        "short_id": "7Q2MK4PX",
        "issued_at": "2026-10-29T06:10:00Z",
        "revoked_at": None,
        "revoked_reason_code": None,
        "revoked_reason": None,
    }

    async def credential_refs(session, enrolment_id):
        assert enrolment_id == enrolment.id
        return [ref]

    monkeypatch.setattr(holder, "credential_refs", credential_refs)
    body = (await clients["abc"].get(f"/enrolments/{enrolment.id}")).json()
    email, digi = await notices_of(enrolment.id)
    assert [n["channel"] for n in body["notices"]] == ["EMAIL", "DIGILOCKER"]
    assert all(set(n) == NOTICE_KEYS for n in body["notices"])
    assert body["notices"][0] == {
        "id": str(email.id),
        "channel": "EMAIL",
        "state": "AWAITING",
        "delivery_status": "SENT",
        "attempts": 1,
        "last_error": None,
        "sent_at": wire_time(email.sent_at),
        "expires_at": wire_time(email.expires_at),
        "response": None,
        "responded_at": None,
        "previous_response": None,
        "changed_at": None,
        "resent": False,
    }
    assert body["notices"][1]["last_error"] == "No DigiLocker account."
    assert body["resend"] == {"allowed": False, "blocked_by": "LIVE", "resends_left": 3}
    assert body["credentials"] == [ref]
    [student_check] = [c for c in body["checks"] if c["type"] == "STUDENT"]
    assert student_check["status"] == "PENDING"
    assert student_check["source"] == "STUDENT_NOTICE"
    assert student_check["detail"]["notice_state"] == "SENT"
    # the university may read the enrolment but never resend
    university = (await clients["university"].get(f"/enrolments/{enrolment.id}")).json()
    assert university["resend"] == {"allowed": False, "blocked_by": "ROLE", "resends_left": 3}


async def test_an_enrolment_with_no_notice(world, clients):
    enrolment = await world.enrolment()
    body = (await clients["admin"].get(f"/enrolments/{enrolment.id}")).json()
    assert body["notices"] == [] and body["credentials"] == []
    assert body["resend"] == {"allowed": True, "blocked_by": None, "resends_left": 3}


async def test_both_rechecks_ask_for_the_proof(world, mailer, clients, public, issued):
    confirmed, tokens = await delivered(world, mailer, apaar=None)
    waiting, _ = await delivered(world, mailer, apaar=None)
    await confirm_rows(confirmed.id)
    await confirm_rows(waiting.id)
    await answer(tokens[EMAIL])
    issued.clear()
    response = await clients["admin"].post(f"/enrolments/{confirmed.id}/recheck")
    assert response.status_code == 200, response.text
    assert issued == [confirmed.id]
    issued.clear()
    response = await clients["admin"].post(f"/institutions/{world.abc.id}/recheck", json={})
    assert response.status_code == 200, response.text
    # only a COUNTERSIGNED record can be eligible (D44): the other waits for evidence
    assert issued == [confirmed.id] and waiting.id not in issued
