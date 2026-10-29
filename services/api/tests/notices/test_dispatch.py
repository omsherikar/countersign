"""Sending a batch's notices: who gets one, delivery, tokens and the worker (D23, §A3.2)."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text, update

from app import worker
from app.core.config import get_settings
from app.db.session import session_factory
from app.engine.checks import refresh_student
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    ConsentPurpose,
    ConsentState,
    ConsentStatus,
    EnrolmentStatus,
    NoticeChannel,
    NoticeDelivery,
    UploadStatus,
)
from app.models.verification import Check, Notification
from app.notices import dispatch
from app.notices.dispatch import (
    DIGILOCKER_TRIP,
    deliver_notices,
    programme_short,
    send_notices_for_batch,
)
from app.notices.mailer import MailResult, MemoryMailer
from app.notices.student_check import fmt_day
from app.privacy.service import record_consent
from tests.notices.conftest import notices_of, token_of

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER


async def student_check(enrolment_id) -> Check | None:
    async with session_factory()() as s:
        return (
            await s.execute(
                select(Check).where(
                    Check.enrolment_id == enrolment_id, Check.type == CheckType.STUDENT
                )
            )
        ).scalar_one_or_none()


def test_programme_short():
    assert programme_short("B.Tech Computer Science and Engineering", "CSE") == "B.Tech CSE"
    assert programme_short("Diploma in Mechanical Engineering", "DME") == (
        "Diploma in Mechanical Engineering"
    )


async def test_a_done_batch_gets_one_notice_per_channel_per_active_enrolment(world, mailer, gov):
    batch = await world.batch()
    both = await world.enrolment(batch=batch)
    email_only = await world.enrolment(batch=batch, apaar=None)
    digilocker_only = await world.enrolment(batch=batch, email=None)
    unreachable = await world.enrolment(batch=batch, email=None, apaar=None)
    withdrawn = await world.enrolment(batch=batch, status=EnrolmentStatus.WITHDRAWN)
    no_notices = await world.enrolment(batch=batch)
    elsewhere = await world.enrolment(batch=await world.batch(filename="other.csv"))
    async with session_factory()() as s:
        # whatever its Identity result: a failed Identity still gets its notice
        s.add(
            Check(
                enrolment_id=both.id,
                type=CheckType.IDENTITY,
                status=CheckStatus.CONTRADICTED,
                source="APAAR",
                detail={"summary": "APAAR ending 0001 is not in the APAAR registry."},
            )
        )
        await record_consent(
            s,
            student_id=no_notices.student_id,
            purpose=ConsentPurpose.NOTICE,
            status=ConsentState.WITHDRAWN,
            channel="PORTAL",
            notice_text="Stop new notices?",
        )
        await s.commit()

    assert await send_notices_for_batch(batch.id) == 4
    channels = {
        e.id: sorted(n.channel.value for n in await notices_of(e.id))
        for e in (both, email_only, digilocker_only, unreachable, withdrawn, no_notices, elsewhere)
    }
    assert channels == {
        both.id: ["DIGILOCKER", "EMAIL"],
        email_only.id: ["EMAIL"],
        digilocker_only.id: ["DIGILOCKER"],
        unreachable.id: [],
        withdrawn.id: [],
        no_notices.id: [],
        elsewhere.id: [],
    }
    for enrolment in (both, email_only, digilocker_only):
        assert {n.delivery_status for n in await notices_of(enrolment.id)} == {NoticeDelivery.SENT}
    assert len(mailer.sent) == 2 and len(gov.digilocker.inbox) == 2

    # the STUDENT check now says what happened
    sent = await student_check(both.id)
    assert sent.status is CheckStatus.PENDING and sent.detail["notice_state"] == "SENT"
    assert (await student_check(unreachable.id)).detail["notice_state"] == "UNREACHABLE"
    quiet = (await student_check(no_notices.id)).detail
    assert quiet["notice_state"] == "NOT_SENT" and quiet["consent_withdrawn"] is True
    assert await student_check(withdrawn.id) is None

    # a second run creates nothing and sends nothing
    assert await send_notices_for_batch(batch.id) == 0
    assert len(mailer.sent) == 2 and len(gov.digilocker.inbox) == 2
    async with session_factory()() as s:
        creates = (
            await s.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.entity_type == "notification", AuditLog.action == AuditAction.CREATE
                )
            )
        ).scalar_one()
    assert creates == 4


async def test_only_a_done_batch_sends(world, mailer):
    for status in (UploadStatus.QUEUED, UploadStatus.PROCESSING, UploadStatus.FAILED):
        batch = await world.batch(status=status)
        await world.enrolment(batch=batch)
        assert await send_notices_for_batch(batch.id) == 0
    assert await send_notices_for_batch(uuid.uuid4()) == 0
    assert mailer.sent == []


async def test_the_email_and_the_digilocker_message(world, mailer, gov):
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch)
    await send_notices_for_batch(batch.id)
    [message] = mailer.sent
    email, digi = await notices_of(enrolment.id)
    assert (email.channel, digi.channel) == (EMAIL, DIGILOCKER)
    # the notice only points to DigiLocker sign-in (D37), in English with Hindi under it
    assert message.subject == "ABC College of Engineering has reported an enrolment in your name"
    token = token_of(message)
    link = f"{get_settings().web_origin}/student/notices/{token}"
    english, hindi = message.body.split("\n\n")
    assert english == (
        "ABC College of Engineering has told AICTE that you joined B.Tech Computer Science and "
        f"Engineering in 2026-27. To see what they reported and to answer, open {link} and sign "
        "in with DigiLocker. Your answer is recorded only after you sign in with DigiLocker; "
        f"nothing in this email can record it. The link works until {fmt_day(email.expires_at)}. "
        "Never share your DigiLocker OTP with anyone, including AICTE or your college."
    )
    assert link in hindi and "DigiLocker से साइन इन करें" in hindi
    assert message.headers == {"X-Countersign-Notice": str(email.id)}
    [inbox] = gov.digilocker.inbox
    assert inbox["message"] == (
        "ABC College of Engineering has reported that you joined B.Tech CSE (2026-27). "
        "Sign in to Countersign with DigiLocker to answer."
    )
    assert inbox["callback_url"].startswith(f"{get_settings().web_origin}/student/notices/")
    # the notice lasts notices.expiry_days from its creation
    assert abs((email.expires_at - email.created_at) - timedelta(days=30)) < timedelta(minutes=1)


async def test_only_the_hash_of_a_token_is_stored(world, mailer, gov):
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch)
    await send_notices_for_batch(batch.id)
    email, digi = await notices_of(enrolment.id)
    email_token = token_of(mailer.sent[0])
    digi_token = gov.digilocker.inbox[0]["callback_url"].rsplit("/", 1)[1]
    assert email.token_hash == hashlib.sha256(email_token.encode()).hexdigest()
    assert digi.token_hash == hashlib.sha256(digi_token.encode()).hexdigest()
    assert "{link}" in email.message and email_token not in email.message
    async with session_factory()() as s:
        for token in (email_token, digi_token):
            hits = (
                await s.execute(
                    text(
                        "SELECT count(*) FROM notifications n "
                        "WHERE n::text LIKE :t OR EXISTS ("
                        "  SELECT 1 FROM audit_log a WHERE a.after::text LIKE :t)"
                    ),
                    {"t": f"%{token}%"},
                )
            ).scalar_one()
            assert hits == 0


async def test_digilocker_404_fails_that_channel_and_never_delays_email(world, mailer, gov):
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, digilocker=False)
    events: list[str] = []
    real_send, real_notify = mailer.send_many, gov.digilocker.notify

    def send(messages):
        events.append("email")
        return real_send(messages)

    async def notify(*args):
        events.append("digilocker")
        return await real_notify(*args)

    mailer.send_many = send
    gov.digilocker.notify = notify
    await send_notices_for_batch(batch.id)
    email, digi = await notices_of(enrolment.id)
    assert (email.delivery_status, email.attempts) == (NoticeDelivery.SENT, 1)
    assert (digi.delivery_status, digi.attempts, digi.last_error) == (
        NoticeDelivery.FAILED,
        1,
        "No DigiLocker account.",
    )
    assert digi.sent_at is None and events == ["email", "digilocker"]
    assert (await student_check(enrolment.id)).detail["notice_state"] == "SENT"


async def test_a_digilocker_outage_is_tried_three_times_and_trips_each_pass(world, mailer, gov):
    batch = await world.batch()
    enrolments = [await world.enrolment(batch=batch) for _ in range(DIGILOCKER_TRIP + 4)]
    gov.digilocker.down = True
    calls = 0
    real_notify = gov.digilocker.notify

    async def notify(*args):
        nonlocal calls
        calls += 1
        return await real_notify(*args)

    gov.digilocker.notify = notify
    await send_notices_for_batch(batch.id)
    for enrolment in enrolments:
        email, digi = await notices_of(enrolment.id)
        assert email.delivery_status is NoticeDelivery.SENT and email.attempts == 1
        assert (digi.delivery_status, digi.attempts, digi.last_error) == (
            NoticeDelivery.FAILED,
            3,
            "DigiLocker did not respond.",
        )
    # every pass stops calling after DIGILOCKER_TRIP unavailable answers in a row
    assert calls == 3 * DIGILOCKER_TRIP


class FlakyMailer(MemoryMailer):
    """Fails the first `failures` calls as an outage, after the message went out."""

    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def send_many(self, messages):
        self.calls += 1
        self.sent.extend(messages)
        if self.calls <= self.failures:
            failed = MailResult(ok=False, error="Mail server did not respond.", transient=True)
            return [failed] * len(messages)
        return [MailResult(ok=True) for _ in messages]


async def test_a_mail_outage_is_retried_with_a_fresh_token(world, monkeypatch):
    flaky = FlakyMailer(failures=1)
    monkeypatch.setattr(dispatch, "build_mailer", lambda *a, **k: flaky)
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, apaar=None)
    await send_notices_for_batch(batch.id)
    [notice] = await notices_of(enrolment.id)
    assert (notice.delivery_status, notice.attempts, notice.last_error) == (
        NoticeDelivery.SENT,
        2,
        None,
    )
    first, second = (token_of(m) for m in flaky.sent)
    assert first != second
    assert notice.token_hash == hashlib.sha256(second.encode()).hexdigest()


async def test_three_failed_tries_fail_the_email(world, monkeypatch):
    flaky = FlakyMailer(failures=3)
    monkeypatch.setattr(dispatch, "build_mailer", lambda *a, **k: flaky)
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, apaar=None)
    await send_notices_for_batch(batch.id)
    [notice] = await notices_of(enrolment.id)
    assert (notice.delivery_status, notice.attempts, notice.last_error) == (
        NoticeDelivery.FAILED,
        3,
        "Mail server did not respond.",
    )
    hashes = {hashlib.sha256(token_of(m).encode()).hexdigest() for m in flaky.sent}
    assert len(hashes) == 3 and notice.token_hash not in hashes
    detail = (await student_check(enrolment.id)).detail
    assert detail == {
        "summary": "Notice not sent yet.",
        "notice_state": "NOT_SENT",
        "delivery_failed": True,
    }


async def test_a_refused_address_fails_at_once(world, monkeypatch):
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, apaar=None, email="bounce@example.demo")
    monkeypatch.setattr(
        dispatch, "build_mailer", lambda *a, **k: MemoryMailer(refuse={"bounce@example.demo"})
    )
    await send_notices_for_batch(batch.id)
    [notice] = await notices_of(enrolment.id)
    assert (notice.delivery_status, notice.attempts, notice.last_error) == (
        NoticeDelivery.FAILED,
        1,
        "Email address was refused.",
    )


async def test_a_large_batch_is_created_and_delivered_in_chunks(world, mailer, gov):
    batch = await world.batch()
    ids = await world.bulk(1_100, batch)
    started = time.perf_counter()
    assert await send_notices_for_batch(batch.id) == 2_200
    elapsed = time.perf_counter() - started
    assert len(mailer.sent) == 1_100 and len(gov.digilocker.inbox) == 1_100
    assert mailer.calls == 3  # one send_many, so one connection, per 500 notices
    async with session_factory()() as s:
        counts = dict(
            (
                await s.execute(
                    select(Notification.delivery_status, func.count()).group_by(
                        Notification.delivery_status
                    )
                )
            ).all()
        )
        states = (
            await s.execute(
                select(func.count())
                .select_from(Check)
                .where(
                    Check.enrolment_id.in_(ids),
                    Check.type == CheckType.STUDENT,
                    Check.detail["notice_state"].astext == "SENT",
                )
            )
        ).scalar_one()
    assert counts == {NoticeDelivery.SENT: 2_200} and states == 1_100
    assert elapsed < 60, f"2,200 notices took {elapsed:.1f} s"


async def test_refresh_after_expiry_reads_expired(world, mailer):
    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, apaar=None)
    await send_notices_for_batch(batch.id)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await refresh_student(s, [enrolment.id])
        await s.commit()
    check = await student_check(enrolment.id)
    assert check.status is CheckStatus.PENDING and check.detail["notice_state"] == "EXPIRED"


async def test_deliver_notices_sends_queued_rows_and_refreshes_the_check(world, mailer, gov):
    enrolment = await world.enrolment(consent=ConsentStatus.LINKED)
    async with session_factory()() as s:
        rows = await dispatch.create_notices(s, [enrolment.id], resent_by_id=None, actor_id=None)
        await s.commit()
    assert {n.delivery_status for n in rows} == {NoticeDelivery.QUEUED}
    assert await deliver_notices([n.id for n in rows], adapters=gov) == 2
    assert (await student_check(enrolment.id)).detail["notice_state"] == "SENT"
    # delivering again does nothing: only QUEUED rows with tries left are sent
    assert await deliver_notices([n.id for n in rows], adapters=gov) == 0


def test_the_delivery_task_is_registered():
    task = worker.celery_app.tasks["countersign.deliver_notices"]
    assert task.acks_late is True


async def test_the_worker_requeues_old_queued_notices_on_start(world, monkeypatch):
    fresh, old, tried, sent = [await world.enrolment(apaar=None) for _ in range(4)]
    ids = {}
    async with session_factory()() as s:
        for key, enrolment in (("fresh", fresh), ("old", old), ("tried", tried), ("sent", sent)):
            [row] = await dispatch.create_notices(
                s, [enrolment.id], resent_by_id=None, actor_id=None
            )
            ids[key] = row.id
        await s.flush()
        an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        await s.execute(
            update(Notification)
            .where(Notification.id.in_([ids["old"], ids["tried"], ids["sent"]]))
            .values(created_at=an_hour_ago)
        )
        await s.execute(
            update(Notification).where(Notification.id == ids["tried"]).values(attempts=3)
        )
        await s.execute(
            update(Notification)
            .where(Notification.id == ids["sent"])
            .values(delivery_status=NoticeDelivery.SENT)
        )
        await s.commit()
    queued: list[list[str]] = []
    monkeypatch.setattr(worker.deliver_notices_task, "delay", lambda ids_: queued.append(ids_))
    monkeypatch.setattr(worker, "enqueue_batch", lambda batch_id: None)
    # the worker calls it outside any event loop
    assert await asyncio.to_thread(worker.requeue_unfinished) == []
    assert queued == [[str(ids["old"])]]


def test_a_delivery_that_cannot_be_queued_is_logged(monkeypatch):
    def broker_down(ids):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(worker.deliver_notices_task, "delay", broker_down)
    assert worker.enqueue_delivery([uuid.uuid4()]) is False
    assert worker.enqueue_delivery([]) is True


async def test_an_inline_upload_sends_its_notices(world, mailer, clients, tmp_path, monkeypatch):
    from tests.pipeline.conftest import ROW, csv_bytes

    monkeypatch.setattr(get_settings(), "upload_inline", True)
    monkeypatch.setattr(get_settings(), "upload_spool_dir", str(tmp_path / "spool"))
    response = await clients["abc"].post(
        "/uploads",
        data={"academic_year": "2026-27", "declaration": "true"},
        files={"file": ("1-ABC-0001_2026-27.csv", csv_bytes([ROW]), "text/csv")},
    )
    assert response.status_code == 202, response.text
    async with session_factory()() as s:
        rows = (
            (await s.execute(select(Notification).order_by(Notification.channel))).scalars().all()
        )
        identity = (
            await s.execute(select(Check.status).where(Check.type == CheckType.IDENTITY))
        ).scalar_one()
    # the in-memory registry is empty, so Identity fails; the notice goes out regardless
    assert identity is CheckStatus.CONTRADICTED
    assert [(n.channel, n.delivery_status, n.last_error) for n in rows] == [
        (EMAIL, NoticeDelivery.SENT, None),
        (DIGILOCKER, NoticeDelivery.FAILED, "No DigiLocker account."),
    ]
    assert [m.to for m in mailer.sent] == [ROW["email"]]
