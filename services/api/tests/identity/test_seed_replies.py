"""The seed's planned replies stand for answers given after DigiLocker sign-in (D37), with
the provisional claims they need (D36)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    ConsentStatus,
    UploadSource,
)
from app.models.verification import Check
from app.notices.dispatch import send_notices_for_batch
from app.seed import replies
from tests.identity.conftest import user_of
from tests.notices.conftest import notices_of

FILE = "1-ABC-0001_2026-27.csv"


def write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


async def row_of(enrolment_id, check_type: CheckType) -> Check | None:
    async with session_factory()() as s:
        return (
            await s.execute(
                select(Check).where(Check.enrolment_id == enrolment_id, Check.type == check_type)
            )
        ).scalar_one_or_none()


async def test_seeded_replies_sign_in_and_claim_first_when_there_is_no_apaar(
    world, mailer, tmp_path
):
    batch = await world.batch(source=UploadSource.SEED, filename=FILE)
    linked = await world.enrolment("Priya Deshmukh", batch=batch, row_no=2)
    refused = await world.enrolment(
        "Suresh Pawar", batch=batch, row_no=3, apaar=None, consent=ConsentStatus.REFUSED
    )
    pending = await world.enrolment(
        "Meera Chavan", batch=batch, row_no=4, apaar=None, consent=ConsentStatus.PENDING
    )
    await world.enrolment("Nobody Answered", batch=batch, row_no=5)
    await send_notices_for_batch(batch.id)
    write_jsonl(
        tmp_path / replies.REPLIES_FILE,
        [
            {
                "file": f"uploads/{FILE}",
                "row_no": n,
                "reply": reply,
                "channel": "EMAIL",
                "comment": None,
                "reply_after_days": 0,
            }
            for n, reply in ((2, "YES"), (3, "YES"), (4, "YES"), (5, "NONE"))
        ],  # fmt: skip
    )
    write_jsonl(
        tmp_path / replies.ACCOUNTS_FILE,
        [
            # the refused-consent student's account: no APAAR, same birth date and name
            {
                "digilocker_id": "DL-SURE-0001",
                "name": "Suresh Pawar",
                "dob": "2007-01-01",
                "gender": "M",
                "apaar_id": None,
            },
            # someone else born the same day: never used for Meera
            {
                "digilocker_id": "DL-OTHR-0001",
                "name": "Kavya Nair",
                "dob": "2007-01-01",
                "gender": "F",
                "apaar_id": None,
            },
        ],  # fmt: skip
    )
    counts = await replies.apply_replies(session_factory(), tmp_path / replies.REPLIES_FILE)
    assert (counts.lines, counts.yes, counts.no, counts.no_reply) == (4, 2, 0, 1)
    assert (counts.claimed, counts.no_signin, counts.refused) == (1, 1, 0)
    assert counts.problems == [f"{FILE} row 4: the student cannot sign in through DigiLocker"]

    # the linked student answered by APAAR sign-in; the refused one after claiming
    assert (await row_of(linked.id, CheckType.STUDENT)).status is CheckStatus.CONFIRMED
    assert (await row_of(refused.id, CheckType.STUDENT)).status is CheckStatus.CONFIRMED
    identity = await row_of(refused.id, CheckType.IDENTITY)
    assert identity.status is CheckStatus.CONFIRMED
    assert identity.supplied_by == "Student via DigiLocker sign-in"
    bound = await user_of(refused.student_id)
    assert bound.digilocker_sub == "DL-SURE-0001"
    assert bound.email == "dl-sure-0001@digilocker.invalid"
    # the student who could not sign in has no answer and no account
    assert [n.response for n in await notices_of(pending.id)] == [None]
    assert await user_of(pending.student_id) is None
    async with session_factory()() as s:
        [claim] = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "student", AuditLog.action == AuditAction.UPDATE
                    )
                )
            )
            .scalars()
            .all()
        )
    assert claim.entity_id == refused.student_id and claim.actor_id is None
    assert claim.after == {"claimed_via": "digilocker", "enrolments": 1, "via": "demo-seed"}

    # running it again claims nothing more and records nothing new
    again = await replies.apply_replies(session_factory(), tmp_path / replies.REPLIES_FILE)
    assert (again.yes, again.claimed, again.no_signin) == (2, 0, 1)


async def test_without_an_accounts_file_only_linked_students_answer(world, mailer, tmp_path):
    batch = await world.batch(source=UploadSource.SEED, filename=FILE)
    await world.enrolment("Priya Deshmukh", batch=batch, row_no=2)
    await world.enrolment("Suresh Pawar", batch=batch, row_no=3, apaar=None)
    await send_notices_for_batch(batch.id)
    write_jsonl(
        tmp_path / replies.REPLIES_FILE,
        [
            {
                "file": FILE,
                "row_no": n,
                "reply": "YES",
                "channel": "EMAIL",
                "comment": None,
                "reply_after_days": 0,
            }
            for n in (2, 3)
        ],  # fmt: skip
    )
    counts = await replies.apply_replies(session_factory(), tmp_path / replies.REPLIES_FILE)
    assert (counts.yes, counts.claimed, counts.no_signin) == (1, 0, 1)
