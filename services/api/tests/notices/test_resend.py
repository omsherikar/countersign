"""Resends: POST /enrolments/{id}/notices/resend (API_CONTRACT §A3.5, §A3.26)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app import worker
from app.core.config import get_settings
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    ConsentPurpose,
    ConsentState,
    EnrolmentStatus,
    NoticeChannel,
    NoticeDelivery,
)
from app.models.student import Enrolment
from app.models.verification import Notification
from app.notices.student_check import fmt_day, wire_time
from app.privacy.service import record_consent
from tests.notices.conftest import delivered, notices_of, signed_in_owner

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER


@pytest.fixture
def inline(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_inline", True)


async def expire(enrolment_id) -> None:
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment_id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()


def resend_url(enrolment) -> str:
    return f"/enrolments/{enrolment.id}/notices/resend"


def error(response) -> tuple[int, str, str, dict]:
    body = response.json()["error"]
    return response.status_code, body["code"], body["message"], body["details"]


async def test_a_live_notice_blocks_a_resend(world, mailer, clients):
    enrolment, _ = await delivered(world, mailer)
    email, _ = await notices_of(enrolment.id)
    response = await clients["abc"].post(resend_url(enrolment), json={})
    assert error(response) == (
        409,
        "NOTICE_LIVE",
        f"A notice sent on {fmt_day(email.sent_at)} is open until {fmt_day(email.expires_at)}.",
        {"reason": "LIVE", "expires_at": wire_time(email.expires_at)},
    )


async def test_an_answered_notice_blocks_a_resend(world, mailer, clients, public):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    async with await signed_in_owner(tokens[EMAIL]) as student:
        await student.post(f"/notices/{tokens[EMAIL]}/respond", json={"response": "YES"})
    await expire(enrolment.id)
    response = await clients["admin"].post(resend_url(enrolment), json={})
    assert error(response) == (
        409,
        "NOTICE_LIVE",
        "The student has already replied.",
        {"reason": "ANSWERED"},
    )


async def test_a_resend_after_expiry_sends_new_notices(world, mailer, clients, inline):
    enrolment, _ = await delivered(world, mailer)
    await expire(enrolment.id)
    response = await clients["abc"].post(resend_url(enrolment))
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["enrolment_id"] == str(enrolment.id)
    assert [
        (n["channel"], n["state"], n["delivery_status"], n["resent"]) for n in body["notices"]
    ] == [
        ("EMAIL", "QUEUED", "QUEUED", True),
        ("DIGILOCKER", "QUEUED", "QUEUED", True),
    ]
    assert body["resend"] == {"allowed": False, "blocked_by": "LIVE", "resends_left": 2}
    # delivered after the response (inline here, by the worker otherwise)
    rows = await notices_of(enrolment.id)
    fresh = [n for n in rows if n.resent_by_id is not None]
    assert {n.delivery_status for n in fresh} == {NoticeDelivery.SENT}
    assert {n.resent_by_id for n in fresh} == {world.users["abc"].id}
    assert len(mailer.sent) == 2
    async with session_factory()() as s:
        creates = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "notification",
                        AuditLog.action == AuditAction.CREATE,
                        AuditLog.actor_id == world.users["abc"].id,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert sorted(a.after["channel"] for a in creates) == ["DIGILOCKER", "EMAIL"]
    assert all(a.after["resent"] is True for a in creates)


async def test_without_inline_the_worker_delivers(world, mailer, clients, monkeypatch):
    queued: list[list[str]] = []
    monkeypatch.setattr(worker.deliver_notices_task, "delay", lambda ids: queued.append(ids))
    enrolment, _ = await delivered(world, mailer, apaar=None)
    await expire(enrolment.id)
    response = await clients["ro_west"].post(resend_url(enrolment))
    assert response.status_code == 202
    [new] = response.json()["notices"]
    assert queued == [[new["id"]]]
    async with session_factory()() as s:
        row = await s.get(Notification, new["id"])
    assert row.delivery_status is NoticeDelivery.QUEUED  # committed before it was queued


async def test_three_resends_then_the_limit(world, mailer, clients, inline):
    enrolment, _ = await delivered(world, mailer, apaar=None)
    for left in (2, 1, 0):
        await expire(enrolment.id)
        response = await clients["admin"].post(resend_url(enrolment))
        assert response.status_code == 202
        assert response.json()["resend"]["resends_left"] == left
    await expire(enrolment.id)
    response = await clients["admin"].post(resend_url(enrolment))
    assert error(response) == (
        429,
        "RESEND_LIMIT",
        "This notice has been resent 3 times this academic year.",
        {"limit": 3},
    )
    detail = (await clients["admin"].get(f"/enrolments/{enrolment.id}")).json()
    assert detail["resend"] == {"allowed": False, "blocked_by": "LIMIT", "resends_left": 0}


async def test_who_may_resend(world, mailer, clients, inline):
    abc_enrolment, _ = await delivered(world, mailer, apaar=None)
    await expire(abc_enrolment.id)
    url = resend_url(abc_enrolment)
    assert (await clients["xyz"].post(url)).status_code == 404
    assert error(await clients["xyz"].post(url))[2] == "Enrolment not found."
    assert (await clients["ro_south"].post(url)).status_code == 404
    assert (await clients["university"].post(url)).status_code == 403
    student = await world.student_login(abc_enrolment)
    assert (await student.post(url)).status_code == 403
    await student.aclose()
    assert (await clients["abc"].post(url)).status_code == 202


async def test_conditions_that_block_a_resend(world, mailer, clients):
    inactive = await world.enrolment(status=EnrolmentStatus.WITHDRAWN)
    assert error(await clients["admin"].post(resend_url(inactive))) == (
        409,
        "CONFLICT",
        "Notices go only to active enrolments.",
        {"reason": "NOT_ACTIVE"},
    )
    unreachable = await world.enrolment(email=None, apaar=None)
    assert error(await clients["admin"].post(resend_url(unreachable))) == (
        409,
        "CONFLICT",
        "The student has no email address or linked APAAR to send a notice to.",
        {"reason": "NO_CHANNEL"},
    )
    quiet = await world.enrolment()
    async with session_factory()() as s:
        await record_consent(
            s,
            student_id=quiet.student_id,
            purpose=ConsentPurpose.NOTICE,
            status=ConsentState.WITHDRAWN,
            channel="PORTAL",
            notice_text="Stop new notices?",
        )
        await s.commit()
    assert error(await clients["admin"].post(resend_url(quiet))) == (
        409,
        "CONFLICT",
        "The student has asked not to receive notices.",
        {"reason": "CONSENT_WITHDRAWN"},
    )
    async with session_factory()() as s:
        assert (await s.execute(select(Notification))).scalars().all() == []
        # nothing was sent, so the enrolment shows why the button is off
        assert (await s.get(Enrolment, quiet.id)) is not None
    detail = (await clients["admin"].get(f"/enrolments/{quiet.id}")).json()
    assert detail["resend"]["blocked_by"] == "CONSENT_WITHDRAWN"
