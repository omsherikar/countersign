"""The seed: notices for every seeded batch, then datagen's simulated replies (D31, §A3.28)."""

from __future__ import annotations

import shutil

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    UploadSource,
)
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.verification import Check, Flag, Notification
from app.notices import mailer as mail
from app.notices.mailer import MemoryMailer, SmtpMailer
from app.seed import cli, replies
from app.seed.importer import import_directory
from tests.conftest import FIXTURE_DIR


async def enrolment_at(filename: str, row_no: int) -> Enrolment:
    async with session_factory()() as s:
        return (
            await s.execute(
                select(Enrolment)
                .join(UploadBatch, UploadBatch.id == Enrolment.upload_batch_id)
                .where(
                    UploadBatch.filename == filename,
                    UploadBatch.source == UploadSource.SEED,
                    Enrolment.source_row_no == row_no,
                )
            )
        ).scalar_one()


async def student_check(enrolment: Enrolment) -> Check:
    async with session_factory()() as s:
        return (
            await s.execute(
                select(Check).where(
                    Check.enrolment_id == enrolment.id, Check.type == CheckType.STUDENT
                )
            )
        ).scalar_one()


async def test_the_seed_sends_notices_then_applies_the_replies(db, monkeypatch):
    box = MemoryMailer()
    monkeypatch.setattr(cli, "build_mailer", lambda *a, **k: box)
    factory = session_factory()
    summary = await import_directory(factory, FIXTURE_DIR)
    created = await cli.send_seed_notices(factory, summary, FIXTURE_DIR)

    async with session_factory()() as s:
        reachable = (
            await s.execute(
                select(func.count())
                .select_from(Enrolment)
                .join(Student, Student.id == Enrolment.student_id)
                .where(
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                    Enrolment.upload_batch_id.is_not(None),
                    Student.email.is_not(None),
                )
            )
        ).scalar_one()
        by_status = dict(
            (
                await s.execute(
                    select(Notification.delivery_status, func.count()).group_by(
                        Notification.delivery_status
                    )
                )
            ).all()
        )
    # every reachable active enrolment of a seeded batch has its email notice out
    assert len(box.sent) == reachable > 0
    assert created == sum(by_status.values()) and NoticeDelivery.QUEUED not in by_status
    assert await cli.send_seed_notices(factory, summary, FIXTURE_DIR) == 0

    counts = await replies.apply_replies(factory, FIXTURE_DIR / replies.REPLIES_FILE)
    assert (counts.lines, counts.yes, counts.no, counts.no_reply) == (7, 3, 2, 1)
    assert (counts.not_found, counts.refused) == (1, 0)
    assert counts.problems == ["1-ABC-0001_2026-27.csv row 999: no seeded enrolment"]

    ravi = await enrolment_at("1-ABC-0001_2026-27.csv", 2)
    assert (await student_check(ravi)).detail["notice_state"] == "SENT"  # left for the demo
    priya = await enrolment_at("1-ABC-0001_2026-27.csv", 3)
    assert (await student_check(priya)).status is CheckStatus.CONFIRMED
    sneha = await enrolment_at("1-ABC-0001_2026-27.csv", 5)
    denied = await student_check(sneha)
    assert denied.status is CheckStatus.CONTRADICTED and denied.detail["channel"] == "DIGILOCKER"
    async with session_factory()() as s:
        flag = (
            await s.execute(select(Flag).where(Flag.dedupe_key == f"STUDENT_DENIED:{sneha.id}"))
        ).scalar_one()
        seeded = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "notification",
                        AuditLog.action == AuditAction.UPDATE,
                        AuditLog.after["via"].astext == "demo-seed",
                    )
                )
            )
            .scalars()
            .all()
        )
        denied_flags = (
            await s.execute(
                select(func.count()).select_from(Flag).where(Flag.type == FlagType.STUDENT_DENIED)
            )
        ).scalar_one()
    assert flag.type is FlagType.STUDENT_DENIED
    assert {"label": "Comment from the student", "value": "I never applied to this college.",
            "source": "Student reply", "audience": "OFFICER"} in flag.evidence["facts"]  # fmt: skip
    assert len(seeded) == 5 and all(a.actor_id is None for a in seeded)
    assert denied_flags == 2

    # the replies answered the channel each line names
    async with session_factory()() as s:
        answered = (
            (
                await s.execute(
                    select(Notification.channel).where(
                        Notification.enrolment_id == sneha.id, Notification.response.is_not(None)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert answered == [NoticeChannel.DIGILOCKER]

    # running the replies again changes nothing
    again = await replies.apply_replies(factory, FIXTURE_DIR / replies.REPLIES_FILE)
    assert (again.yes, again.no, again.refused) == (3, 2, 0)
    async with session_factory()() as s:
        after = (
            await s.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.after["via"].astext == "demo-seed")
            )
        ).scalar_one()
    assert after == 5


def test_the_replies_command_without_a_file(tmp_path, capsys):
    assert replies.main(["--from", str(tmp_path)]) == 0
    assert "no notice_replies.jsonl" in capsys.readouterr().out
    shutil.copy(FIXTURE_DIR / "manifest.json", tmp_path / replies.REPLIES_FILE)
    assert replies.main(["--from", str(tmp_path)]) == 2  # not one JSON object per line


async def test_the_seed_sends_no_notices_while_the_mail_server_is_down(db, monkeypatch):
    def unreachable(*args, **kwargs):
        raise ConnectionRefusedError(61, "refused")

    monkeypatch.setattr(mail.smtplib, "SMTP", unreachable)
    settings = get_settings().model_copy(update={"smtp_host": "localhost", "smtp_port": 1025})
    monkeypatch.setattr(cli, "build_mailer", lambda *a, **k: SmtpMailer(settings))
    output = await cli._run(FIXTURE_DIR, reset=True)
    assert "seeded 4 upload files" in output
    assert output.endswith(
        'no student notices sent: localhost:1025 says "Mail server did not respond." '
        "Start the mail server and run this again; it sends only what is missing."
    )
    async with session_factory()() as s:
        assert (await s.execute(select(func.count()).select_from(Notification))).scalar_one() == 0
        # the seed's last step gives every ACTIVE record its status
        unset = select(func.count()).where(
            Enrolment.status == EnrolmentStatus.ACTIVE, Enrolment.record_status_at.is_(None)
        )
        assert (await s.execute(unset)).scalar_one() == 0
    assert "record statuses updated on " in output
