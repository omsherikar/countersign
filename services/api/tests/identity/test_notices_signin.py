"""Notices behind sign-in (D37, API_CONTRACT §A4.13): the page shows the claim to whoever
holds the link, but only the record's own student, signed in through DigiLocker, can
answer; anyone else is told the notice is for someone else and nothing is recorded. A
student can also answer on their own enrolments page."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    CaseActionKind,
    ConsentStatus,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    NoticeResponse,
    Severity,
)
from app.models.verification import CaseAction, Flag, Notification
from app.notices.dispatch import send_notices_for_batch
from tests.identity.conftest import (
    add_account,
    as_user,
    client,
    pending_client,
    sign_in,
    student_of,
)
from tests.notices.conftest import delivered, notices_of, student_user

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER
DOB = date(2007, 1, 1)


async def answers_recorded(enrolment_id) -> list:
    return [n.response for n in await notices_of(enrolment_id) if n.response is not None]


async def reply_audits() -> list[AuditLog]:
    async with session_factory()() as s:
        return list(
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "notification",
                        AuditLog.action == AuditAction.UPDATE,
                        AuditLog.after.has_key("response"),
                    )
                )
            ).scalars()
        )


async def test_a_notice_link_cannot_record_an_answer_without_sign_in(world, mailer, public):
    enrolment, tokens = await delivered(world, mailer)
    token = tokens[EMAIL]
    page = (await public.get(f"/notices/{token}")).json()
    assert page["viewer"] == {"signed_in": False, "name": None, "match": None}
    assert page["can_answer"] is False and page["claim_url"] is None
    assert page["sign_in_url"] == f"/api/auth/digilocker/start?next=/student/notices/{token}"
    response = await public.post(f"/notices/{token}/respond", json={"response": "NO"})
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "SIGNIN_REQUIRED",
        "message": "Sign in with DigiLocker to answer this notice.",
        "details": {},
    }
    assert await answers_recorded(enrolment.id) == [] and await reply_audits() == []


async def test_another_student_or_an_officer_is_someone_else(world, mailer, clients):
    enrolment, tokens = await delivered(world, mailer)
    other_enrolment = await world.enrolment("Kedar Sawant")
    other = await student_user(other_enrolment.student_id)
    token = tokens[EMAIL]
    async with as_user(other) as c:
        page = (await c.get(f"/notices/{token}")).json()
        assert page["viewer"] == {"signed_in": True, "name": other.name, "match": "SOMEONE_ELSE"}
        assert page["can_answer"] is False
        refused = await c.post(f"/notices/{token}/respond", json={"response": "NO"})
    assert refused.status_code == 403
    assert refused.json()["error"] == {
        "code": "NOTICE_IDENTITY_MISMATCH",
        "message": "This notice is for someone else. Nothing was recorded.",
        "details": {},
    }
    for officer in ("admin", "abc"):
        page = (await clients[officer].get(f"/notices/{token}")).json()
        assert page["viewer"] == {"signed_in": True, "name": None, "match": "SOMEONE_ELSE"}
        answer = await clients[officer].post(f"/notices/{token}/respond", json={"response": "YES"})
        assert answer.status_code == 403
    assert await answers_recorded(enrolment.id) == [] and await reply_audits() == []
    async with session_factory()() as s:
        reads = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "notification", AuditLog.action == AuditAction.READ
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {r.after["match"] for r in reads} == {"SOMEONE_ELSE"}
    assert all(r.actor_id is None for r in reads)


async def test_the_records_own_student_answers_after_sign_in(world, mailer):
    enrolment, tokens = await delivered(world, mailer, name="Ravi Kumar Sharma")
    student = await student_user(enrolment.student_id)
    token = tokens[DIGILOCKER]
    async with as_user(student) as c:
        page = (await c.get(f"/notices/{token}")).json()
        assert page["viewer"] == {"signed_in": True, "name": student.name, "match": "MATCH"}
        assert page["can_answer"] is True
        answer = await c.post(f"/notices/{token}/respond", json={"response": "YES"})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["response"] == "YES" and body["viewer"]["match"] == "MATCH"
    assert body["can_answer"] is True  # one change is allowed within 7 days
    [entry] = await reply_audits()
    assert entry.actor_id == student.id
    assert entry.after == {
        "response": "YES",
        "previous_response": None,
        "via": "digilocker-sign-in",
    }
    async with session_factory()() as s:
        consent_channel = (
            await s.execute(select(Notification.channel).where(Notification.response.is_not(None)))
        ).scalar_one()
    assert consent_channel is DIGILOCKER


async def test_the_token_rules_come_before_sign_in(world, mailer, public):
    enrolment, tokens = await delivered(world, mailer)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()
    anonymous = await public.post(f"/notices/{tokens[EMAIL]}/respond", json={"response": "YES"})
    assert anonymous.status_code == 410
    unknown = await public.post(f"/notices/{'A' * 43}/respond", json={"response": "YES"})
    assert unknown.status_code == 404


async def test_a_pending_claim_sees_claim_needed_only_on_a_record_without_apaar(world, mailer):
    provisional, tokens = await delivered(
        world, mailer, name="Asha Patil", apaar=None, consent=ConsentStatus.REFUSED
    )
    linked, linked_tokens = await delivered(world, mailer, name="Asha Patil")
    token = tokens[EMAIL]
    async with pending_client("Asha Patil", DOB) as c:
        page = (await c.get(f"/notices/{token}")).json()
        assert page["viewer"] == {"signed_in": True, "name": "Asha Patil", "match": "CLAIM_NEEDED"}
        assert page["claim_url"] == f"/student/claim?next=/student/notices/{token}"
        assert page["can_answer"] is False
        refused = await c.post(f"/notices/{token}/respond", json={"response": "YES"})
        assert refused.status_code == 401  # a pending claim is not a sign-in to Countersign
        other = (await c.get(f"/notices/{linked_tokens[EMAIL]}")).json()
        assert other["viewer"]["match"] == "SOMEONE_ELSE" and other["claim_url"] is None


async def test_from_the_link_through_sign_in_and_claim_to_the_answer(world, mailer, gov):
    enrolment, tokens = await delivered(
        world, mailer, name="Asha Patil", apaar=None, consent=ConsentStatus.REFUSED
    )
    provisional_id = (await student_of(enrolment)).provisional_id
    add_account(gov, "DL-ASHA-0001", "Asha Patil", DOB)
    page = f"/student/notices/{tokens[EMAIL]}"
    async with client() as c:
        signed = await sign_in(c, gov, "DL-ASHA-0001", page)
        assert signed.headers["location"] == page  # back to the notice, CLAIM_NEEDED there
        claimed = await c.post("/auth/digilocker/claim", json={"provisional_id": provisional_id})
        assert claimed.json()["next"] == page
        view = (await c.get(f"/notices/{tokens[EMAIL]}")).json()
        assert view["viewer"]["match"] == "MATCH" and view["can_answer"] is True
        answer = await c.post(f"/notices/{tokens[EMAIL]}/respond", json={"response": "NO"})
    assert answer.status_code == 200
    assert await answers_recorded(enrolment.id) == [NoticeResponse.NO]


async def test_a_student_answers_on_their_own_enrolments_page(world, mailer):
    enrolment, _tokens = await delivered(world, mailer)
    student = await student_user(enrolment.student_id)
    elsewhere = await world.enrolment("Someone Else")
    async with as_user(student) as c:
        answer = await c.post(
            f"/students/me/enrolments/{enrolment.id}/respond",
            json={"response": "NO", "comment": "I never joined."},
        )
        assert answer.status_code == 200, answer.text
        record = answer.json()
        assert record["id"] == str(enrolment.id) and record["response"] == "NO"
        assert record["record_status"] == "DISPUTED"
        not_mine = await c.post(
            f"/students/me/enrolments/{elsewhere.id}/respond", json={"response": "YES"}
        )
        assert not_mine.status_code == 404
        assert not_mine.json()["error"]["message"] == "Enrolment not found."
    # the latest delivered notice took the answer
    email, digi = await notices_of(enrolment.id)
    assert [n.response for n in (email, digi)].count(NoticeResponse.NO) == 1
    [entry] = await reply_audits()
    assert (entry.actor_id, entry.after["via"]) == (student.id, "digilocker-sign-in")


async def test_an_answer_without_a_notice_gets_one_and_an_expired_one_still_counts(world, mailer):
    quiet = await world.enrolment("No Notice Yet")  # never sent anything
    student = await student_user(quiet.student_id)
    async with as_user(student) as c:
        answer = await c.post(
            f"/students/me/enrolments/{quiet.id}/respond", json={"response": "YES"}
        )
    assert answer.status_code == 200, answer.text
    [notice] = await notices_of(quiet.id)
    assert (notice.channel, notice.delivery_status, notice.response) == (
        DIGILOCKER,
        NoticeDelivery.SENT,
        NoticeResponse.YES,
    )
    assert notice.message == "Answered after DigiLocker sign-in." and notice.sent_at

    expired, _tokens = await delivered(world, mailer)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == expired.id)
            .values(expires_at=datetime.now(UTC) - timedelta(days=1))
        )
        await s.commit()
    owner = await student_user(expired.student_id)
    async with as_user(owner) as c:
        late = await c.post(
            f"/students/me/enrolments/{expired.id}/respond", json={"response": "YES"}
        )
    assert late.status_code == 200


async def test_only_an_active_enrolment_and_only_a_student(world, mailer, clients):
    enrolment = await world.enrolment("Left College", status=EnrolmentStatus.WITHDRAWN)
    student = await student_user(enrolment.student_id)
    async with as_user(student) as c:
        refused = await c.post(
            f"/students/me/enrolments/{enrolment.id}/respond", json={"response": "NO"}
        )
    assert refused.status_code == 409
    assert refused.json()["error"]["details"] == {"reason": "NOT_ACTIVE"}
    officer = await clients["admin"].post(
        f"/students/me/enrolments/{enrolment.id}/respond", json={"response": "NO"}
    )
    assert officer.status_code == 403


async def test_the_student_sees_the_decision_on_their_dispute(world, mailer):
    enrolment, _tokens = await delivered(world, mailer)
    student = await student_user(enrolment.student_id)
    async with as_user(student) as c:
        await c.post(f"/students/me/enrolments/{enrolment.id}/respond", json={"response": "NO"})
    async with session_factory()() as s:
        flag = (
            await s.execute(select(Flag).where(Flag.dedupe_key == f"STUDENT_DENIED:{enrolment.id}"))
        ).scalar_one()
        assert (flag.type, flag.severity) == (FlagType.STUDENT_DENIED, Severity.HIGH)
        at = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
        s.add(
            CaseAction(
                flag_id=flag.id,
                actor_id=world.users["admin"].id,
                action=CaseActionKind.NOTE,
                note="Looking into it.",
                at=at - timedelta(hours=1),
            )
        )
        s.add(
            CaseAction(
                flag_id=flag.id,
                actor_id=world.users["admin"].id,
                action=CaseActionKind.UPHOLD,
                note="The admission documents check out.",
                reason_code="DOCUMENTS_CONFIRM",
                from_status=FlagStatus.OPEN,
                to_status=FlagStatus.UPHELD,
                at=at,
            )
        )
        await s.commit()
    async with as_user(student) as c:
        me = (await c.get("/students/me")).json()
    [record] = me["enrolments"]
    assert record["decision"] == {
        "outcome": "UPHELD",
        "reason_code": "DOCUMENTS_CONFIRM",
        "at": "2026-10-30T09:00:00Z",
    }
    assert "admission documents" not in str(me)  # never the officer's note


async def test_the_email_points_to_sign_in_and_carries_a_provisional_id(world, mailer):
    batch = await world.batch()
    refused = await world.enrolment(
        "Asha Patil", batch=batch, apaar=None, consent=ConsentStatus.REFUSED
    )
    linked = await world.enrolment("Ravi Kumar Sharma", batch=batch)
    await send_notices_for_batch(batch.id)
    provisional_id = (await student_of(refused)).provisional_id
    by_to = {m.to: m.body for m in mailer.sent}
    refused_mail = by_to[(await student_of(refused)).email]
    linked_mail = by_to[(await student_of(linked)).email]
    line = (
        "Your college recorded you without an APAAR. Your provisional ID is "
        f"{provisional_id}; you need it to claim the record after signing in."
    )
    assert line in refused_mail and "sign in with DigiLocker" in refused_mail
    assert "provisional ID" not in linked_mail
