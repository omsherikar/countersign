"""Attestations follow the record (D44, R6, ENGINES §17.13): issued when it is
COUNTERSIGNED, with or without a reply; revoked when it becomes DISPUTED and issued again
once the dispute is upheld; an officer's withdrawal holds."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app import credentials
from app.credentials import status_list
from app.db.session import session_factory
from app.engine import status
from app.models.credential import Credential
from app.models.enums import CredentialKind, FlagStatus, RecordStatus
from app.models.student import Enrolment
from app.models.verification import Flag
from app.notices.dispatch import send_notices_for_batch
from tests.identity.conftest import COUNTERSIGNED_ROWS, as_user, write_rows
from tests.notices.conftest import student_user


async def attestations(enrolment_id) -> list[tuple[CredentialKind, bool, str | None]]:
    async with session_factory()() as s:
        rows = (
            await s.execute(
                select(Credential)
                .where(Credential.enrolment_id == enrolment_id)
                .order_by(Credential.issued_at)
            )
        ).scalars()
        return [(c.kind, c.revoked, c.revoked_reason) for c in rows]


async def record_status_of(enrolment_id) -> RecordStatus:
    async with session_factory()() as s:
        return (await s.get(Enrolment, enrolment_id)).record_status


async def countersigned_batch(world, name: str):
    """A record whose identity, seat and joining record are confirmed, uploaded in a batch
    whose notices then go out."""
    status_list.invalidate()
    batch = await world.batch()
    enrolment = await world.enrolment(name, batch=batch)
    await write_rows(enrolment.id, COUNTERSIGNED_ROWS)
    assert await record_status_of(enrolment.id) is RecordStatus.COUNTERSIGNED
    # the upload itself signs nothing; the batch's notices task issues afterwards
    assert await attestations(enrolment.id) == []
    await send_notices_for_batch(batch.id)
    return enrolment


async def test_a_countersigned_record_gets_one_without_any_reply(world, mailer):
    enrolment = await countersigned_batch(world, "Priya Deshmukh")
    assert await attestations(enrolment.id) == [(CredentialKind.ENROLMENT, False, None)]
    waiting = await world.enrolment("Waiting Student")
    async with session_factory()() as s:
        assert await credentials.issue_if_eligible(s, waiting.id) is None  # awaiting evidence


async def test_a_dispute_revokes_it_and_an_upheld_dispute_brings_it_back(world, mailer):
    enrolment = await countersigned_batch(world, "Sneha Patil")
    student = await student_user(enrolment.student_id)
    async with as_user(student) as c:
        answer = await c.post(
            f"/students/me/enrolments/{enrolment.id}/respond",
            json={"response": "NO", "comment": "I never joined."},
        )
    assert answer.json()["record_status"] == "DISPUTED"
    assert await attestations(enrolment.id) == [(CredentialKind.ENROLMENT, True, "STUDENT_DISPUTE")]

    # an officer upholds the claim: the Student row stays contradicted but is resolved
    async with session_factory()() as s:
        flag = (
            await s.execute(select(Flag).where(Flag.dedupe_key == f"STUDENT_DENIED:{enrolment.id}"))
        ).scalar_one()
        flag.status = FlagStatus.UPHELD
        await status.mark_resolved(
            s,
            flag,
            FlagStatus.UPHELD,
            actor_id=world.users["admin"].id,
            at=datetime.now(UTC),
            case_action_seq=1,
            reason_code="DOCUMENTS_CONFIRM",
        )
        await status.refresh(s, [enrolment.id])
        await s.commit()
    assert await record_status_of(enrolment.id) is RecordStatus.COUNTERSIGNED
    assert await attestations(enrolment.id) == [
        (CredentialKind.ENROLMENT, True, "STUDENT_DISPUTE"),
        (CredentialKind.ENROLMENT, False, None),
    ]


async def test_an_officers_withdrawal_holds(world, mailer):
    enrolment = await countersigned_batch(world, "Arjun Mehta")
    async with session_factory()() as s:
        revoked = await credentials.revoke_for_enrolment(
            s, enrolment.id, "CLAIM_WITHDRAWN", world.users["admin"].id
        )
        await s.commit()
    assert revoked == 1
    async with session_factory()() as s:
        await status.refresh(s, [enrolment.id])  # still COUNTERSIGNED by its rows
        await s.commit()
    assert await record_status_of(enrolment.id) is RecordStatus.COUNTERSIGNED
    assert await attestations(enrolment.id) == [(CredentialKind.ENROLMENT, True, "CLAIM_WITHDRAWN")]
