"""The public notice page: GET /notices/{token} (API_CONTRACT §A3.3, §A3.1, §A4.13, D32)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.ratelimit import limiter
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import AuditAction, NoticeChannel
from app.models.verification import Notification
from app.notices import dispatch
from app.notices.dispatch import send_notices_for_batch
from app.notices.student_check import wire_time
from tests.notices.conftest import delivered, notices_of, token_of
from tests.notices.test_dispatch import FlakyMailer

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER
NOT_FOUND = {
    "error": {"code": "NOTICE_NOT_FOUND", "message": "This link is not valid.", "details": {}}
}


async def test_the_page_shows_the_claim_and_masks_the_id(world, mailer, public):
    enrolment, tokens = await delivered(world, mailer, name="Ravi Kumar Sharma")
    email, _ = await notices_of(enrolment.id)
    response = await public.get(f"/notices/{tokens[EMAIL]}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "channel": "EMAIL",
        "institution_name": "ABC College of Engineering",
        "programme_code": "CSE",
        "programme_name": "B.Tech Computer Science and Engineering",
        "academic_year": "2026-27",
        "year_of_study": 1,
        "id_kind": "APAAR",
        "id_masked": body["id_masked"],
        "uploaded_at": body["uploaded_at"],
        "sent_at": wire_time(email.sent_at),
        "expires_at": wire_time(email.expires_at),
        "response": None,
        "responded_at": None,
        "previous_response": None,
        "changed_at": None,
        "can_change_until": None,
        "consent_text": (
            "By replying, you let AICTE record your answer with today's date against this "
            "enrolment. Your answer is shown to AICTE officers and to ABC College of Engineering "
            'as "Confirmed" or "Denied", with no other personal detail. If you add a comment, '
            "only AICTE officers see it."
        ),
        "notice_version": "v1",
        # nobody signed in: the claim shows, the answer needs DigiLocker sign-in (D37)
        "viewer": {"signed_in": False, "name": None, "match": None},
        "can_answer": False,
        "sign_in_url": f"/api/auth/digilocker/start?next=/student/notices/{tokens[EMAIL]}",
        "claim_url": None,
    }
    assert body["id_masked"].startswith("XXXX XXXX ") and len(body["id_masked"]) == 14
    assert "Ravi" not in response.text and "@" not in response.text
    digilocker = await public.get(f"/notices/{tokens[DIGILOCKER]}")
    assert digilocker.json()["channel"] == "DIGILOCKER"


async def test_a_provisional_id_is_masked_too(world, mailer, public):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    body = (await public.get(f"/notices/{tokens[EMAIL]}")).json()
    assert body["id_kind"] == "PROVISIONAL"
    assert body["id_masked"].startswith("PRV-XXXX") and len(body["id_masked"]) == 12


async def test_each_view_is_audited_and_the_first_sets_opened_at(world, mailer, public, clients):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    await public.get(f"/notices/{tokens[EMAIL]}")
    [notice] = await notices_of(enrolment.id)
    first_open = notice.opened_at
    assert first_open is not None
    # a signed-in officer opening the link is still an anonymous read; the cookie only says
    # that the person looking is not the record's student
    officer = (await clients["admin"].get(f"/notices/{tokens[EMAIL]}")).json()
    assert officer["viewer"] == {"signed_in": True, "name": None, "match": "SOMEONE_ELSE"}
    [notice] = await notices_of(enrolment.id)
    assert notice.opened_at == first_open
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
    assert [(r.entity_id, r.actor_id, r.after) for r in reads] == [
        (notice.id, None, {"via": "notice-link", "match": None}),
        (notice.id, None, {"via": "notice-link", "match": "SOMEONE_ELSE"}),
    ]


async def test_an_unanswered_notice_past_its_expiry_is_gone(world, mailer, public):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()
    response = await public.get(f"/notices/{tokens[EMAIL]}")
    assert response.status_code == 410
    assert response.json()["error"] == {
        "code": "NOTICE_EXPIRED",
        "message": "This link has expired. Ask your college to resend the notice.",
        "details": {},
    }


async def test_malformed_unknown_and_failed_try_tokens_get_the_same_404(world, monkeypatch, public):
    flaky = FlakyMailer(failures=1)
    monkeypatch.setattr(dispatch, "build_mailer", lambda *a, **k: flaky)
    batch = await world.batch()
    await world.enrolment(batch=batch, apaar=None)
    await send_notices_for_batch(batch.id)
    failed_try, delivered_try = (token_of(m) for m in flaky.sent)
    assert (await public.get(f"/notices/{delivered_try}")).status_code == 200
    for token in (failed_try, "A" * 43, "not-a-token", "A" * 44, "A" * 42 + "!"):
        response = await public.get(f"/notices/{token}")
        assert (response.status_code, response.json()) == (404, NOT_FOUND), token
        reply = await public.post(f"/notices/{token}/respond", json={"response": "YES"})
        assert (reply.status_code, reply.json()) == (404, NOT_FOUND), token


async def test_three_failed_tries_leave_no_working_link(world, monkeypatch, public):
    flaky = FlakyMailer(failures=3)
    monkeypatch.setattr(dispatch, "build_mailer", lambda *a, **k: flaky)
    batch = await world.batch()
    await world.enrolment(batch=batch, apaar=None)
    await send_notices_for_batch(batch.id)
    assert len(flaky.sent) == 3
    for message in flaky.sent:
        response = await public.get(f"/notices/{token_of(message)}")
        assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_the_public_routes_allow_30_a_minute_per_address(world, mailer, public):
    _, tokens = await delivered(world, mailer, apaar=None)
    limiter.reset()
    limiter.enabled = True
    try:
        # guessing tokens counts against the one allowance of the address
        for i in range(29):
            assert (await public.get(f"/notices/{str(i).zfill(43)}")).status_code == 404
        reply = await public.post(f"/notices/{'B' * 43}/respond", json={"response": "YES"})
        assert reply.status_code == 404
        limited = await public.get(f"/notices/{tokens[EMAIL]}")
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        reply = await public.post(f"/notices/{tokens[EMAIL]}/respond", json={"response": "YES"})
        assert reply.status_code == 429
    finally:
        limiter.enabled = False
        limiter.reset()
