"""The demo seed keeps every record's status in step with its rows and cases (D35), and
reproduces the deck's sample card (ENGINES §17.18).

The fixture is ABC College of Engineering's B.Tech CSE first years from datagen's small
data (seed 42), with their registry, joining record and notice replies: the excess
admission, the sample card (row 41), a refused-consent student, a provisional record and
the demo students. The seed runs as `make seed` runs it, without the final status sweep
of the seed command, so a writer that forgot to queue its records would show here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.session import session_factory
from app.engine import status
from app.engine import status_text as text
from app.models.enums import CheckType, EnrolmentStatus, FlagStatus, FlagType, RecordStatus
from app.models.student import Enrolment
from app.models.upload import UploadBatch
from app.models.verification import Check, Flag
from app.notices.mailer import MemoryMailer
from app.seed import cli, replies
from app.seed.importer import import_directory
from tests.conftest import truncate_all

FIXTURE = Path(__file__).parent / "fixtures" / "abc_cse"
FILE = "1-ABC-0001_2026-27.csv"
SAMPLE_ROW = 41


@pytest.fixture(scope="module")
async def seeded() -> AsyncIterator[None]:
    await truncate_all()
    factory = session_factory()
    summary = await import_directory(factory, FIXTURE)
    await cli.send_seed_notices(factory, summary, FIXTURE, mailer=MemoryMailer())
    await replies.apply_replies(factory, FIXTURE / replies.REPLIES_FILE)
    yield
    await truncate_all()


async def _record(row_no: int) -> tuple[Enrolment, dict[CheckType, Check]]:
    async with session_factory()() as session:
        enrolment = (
            await session.execute(
                select(Enrolment)
                .join(UploadBatch, UploadBatch.id == Enrolment.upload_batch_id)
                .where(UploadBatch.filename == FILE, Enrolment.source_row_no == row_no)
            )
        ).scalar_one()
        checks = (
            await session.execute(select(Check).where(Check.enrolment_id == enrolment.id))
        ).scalars()
        return enrolment, {c.type: c for c in checks}


async def test_every_stored_status_is_what_the_rule_says_of_its_rows_and_cases(seeded) -> None:
    async with session_factory()() as session:
        stored = {
            e.id: (e.record_status, e.status_reason, e.next_step)
            for e in (
                await session.execute(
                    select(Enrolment).where(Enrolment.status == EnrolmentStatus.ACTIVE)
                )
            ).scalars()
        }
        assert len(stored) > 100
        tally = await status.refresh(session, list(stored), issue=False)
        recomputed = {
            e.id: (e.record_status, e.status_reason, e.next_step)
            for e in (
                await session.execute(
                    select(Enrolment)
                    .where(Enrolment.id.in_(list(stored)))
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        }
        await session.rollback()
    assert tally.changed == 0
    assert recomputed == stored
    # the seed reaches every status the deck names but a pure dispute-free record
    statuses = {s for s, *_ in stored.values()}
    assert {RecordStatus.COUNTERSIGNED, RecordStatus.UNDER_REVIEW, RecordStatus.DISPUTED} <= (
        statuses
    )
    assert RecordStatus.AWAITING_EVIDENCE in statuses


async def test_the_deck_sample_card(seeded) -> None:
    enrolment, rows = await _record(SAMPLE_ROW)
    today = text.ist_date(datetime.now(UTC))
    identity = rows[CheckType.IDENTITY]
    assert (identity.status.value, identity.detail["finding"]) == ("CONFIRMED", None)
    assert identity.detail["source_line"].startswith("APAAR verification · ")

    seat = rows[CheckType.SEAT]
    assert seat.status.value == "CONFIRMED"
    assert seat.detail["finding"] == "fits approved intake"
    assert seat.supplied_by == "AICTE approval v2, 2026-27 (Seat Ledger, derived)"
    assert seat.detail["source_line"] == "AICTE approval v2, 2026-27 (Seat Ledger, derived)"

    joining = rows[CheckType.ADMISSION]
    assert (joining.status.value, joining.detail["finding"]) == ("CONTRADICTED", "not found")
    assert joining.detail["source_line"] == (
        f"State admission authority · {text.day(joining.observed_at, today)}"
    )
    assert joining.independent is True

    credits = rows[CheckType.STUDYING]
    assert credits.status.value == "NOT_YET_DUE"
    assert credits.detail["source_line"] == "First semester not complete"

    student = rows[CheckType.STUDENT]
    assert (student.status.value, student.detail["finding"]) == (
        "CONTRADICTED",
        '"I never joined"',
    )
    assert student.detail["source_line"] == (
        f"Student sign-in via DigiLocker · {text.day(student.observed_at, today)}"
    )
    assert student.supplied_by == "Student via DigiLocker sign-in" and student.independent

    assert enrolment.record_status is RecordStatus.DISPUTED
    assert enrolment.status_reason == (
        "The student said they never joined, after signing in with DigiLocker on "
        f"{text.day(student.observed_at, today)}."
    )
    assert enrolment.next_step == "Waiting for an officer to review the student's dispute."
    async with session_factory()() as session:
        cases = {
            f.type: f.status
            for f in (
                await session.execute(select(Flag).where(Flag.enrolment_id == enrolment.id))
            ).scalars()
        }
    assert cases == {
        FlagType.STUDENT_DENIED: FlagStatus.OPEN,
        FlagType.NOT_IN_JOINING_RECORD: FlagStatus.OPEN,
    }


async def test_a_clean_record_with_its_joining_record_is_countersigned_without_a_reply(
    seeded,
) -> None:
    clean = []
    async with session_factory()() as session:
        for enrolment in (
            await session.execute(
                select(Enrolment).where(Enrolment.record_status == RecordStatus.COUNTERSIGNED)
            )
        ).scalars():
            rows = {
                c.type: c
                for c in (
                    await session.execute(select(Check).where(Check.enrolment_id == enrolment.id))
                ).scalars()
            }
            if rows[CheckType.STUDENT].status.value == "PENDING":
                clean.append((enrolment, rows))
    assert clean, "a record countersigned by its joining record alone"
    enrolment, rows = clean[0]
    assert rows[CheckType.ADMISSION].status.value == "CONFIRMED"
    assert enrolment.status_reason == (
        "Identity, seat and the joining record confirm the record, and nothing is unresolved."
    )
    assert enrolment.next_step == "None. The evidence is complete."


async def test_a_refused_consent_record_waits_for_the_claim(seeded) -> None:
    enrolment, rows = await _record(37)  # the provisional record the demo claims
    assert rows[CheckType.IDENTITY].status.value == "NOT_APPLICABLE"
    assert rows[CheckType.IDENTITY].detail["source_line"] == (
        "APAAR not linked; alternative route not used yet"
    )
    assert enrolment.record_status is RecordStatus.AWAITING_EVIDENCE
    assert enrolment.next_step == (
        "Waiting for the student to sign in with DigiLocker and claim this record with its "
        "provisional ID."
    )
