"""refresh_record_status against the database: the checks, the student loop and officer
decisions keep `enrolments.record_status` current (D35, R2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.cases.service import apply_action, college_response, today_ist
from app.core.security import hash_password
from app.engine.checks import refresh_student, run_checks
from app.engine.evidence import fmt_date
from app.engine.ledger import assign_seats
from app.engine.status import DISPUTE_NEXT, DISPUTED_REASON, refresh_record_status
from app.models.enums import (
    CaseActionKind,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    NoticeResponse,
    RecordStatus,
    Severity,
    UserRole,
)
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import Flag, Notification
from tests.conftest import PASSWORD
from tests.engines.test_checks import _checks, _ravi

COUNTERSIGNED_BY_COUNSELLING = (
    "Identity and seat are confirmed, and Counselling list confirms the enrolment."
)


async def _record(session, enrolment_id: uuid.UUID) -> Enrolment:
    return (
        await session.execute(
            select(Enrolment)
            .where(Enrolment.id == enrolment_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def _checked(world, session, gov) -> Enrolment:
    _, _, enrolment = await _ravi(world, gov)
    await assign_seats(session, [enrolment.id], actor_id=None)
    await run_checks(session, [enrolment.id], gov)
    return enrolment


async def _student_says(session, enrolment: Enrolment, response: NoticeResponse) -> None:
    now = datetime.now(UTC)
    session.add(
        Notification(
            student_id=enrolment.student_id,
            enrolment_id=enrolment.id,
            channel=NoticeChannel.EMAIL,
            token_hash=uuid.uuid4().hex,
            message="Did you join?",
            delivery_status=NoticeDelivery.SENT,
            sent_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=29),
            response=response,
            responded_at=now,
        )
    )
    await session.flush()
    await refresh_student(session, [enrolment.id])


async def _dispute(session, enrolment: Enrolment) -> Flag:
    return (
        await session.execute(
            select(Flag).where(
                Flag.type == FlagType.STUDENT_DENIED, Flag.enrolment_id == enrolment.id
            )
        )
    ).scalar_one()


async def test_the_checks_write_the_record_status(world, session, gov) -> None:
    enrolment = await _checked(world, session, gov)
    record = await _record(session, enrolment.id)
    assert record.record_status is RecordStatus.COUNTERSIGNED
    assert record.status_reason == COUNTERSIGNED_BY_COUNSELLING
    assert record.next_step is None
    assert record.record_status_at is not None
    # nothing changed, so nothing is written again
    assert await refresh_record_status(session, [enrolment.id]) == 0


async def test_an_unseated_record_is_under_review(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov)
    await run_checks(session, [enrolment.id], gov)
    record = await _record(session, enrolment.id)
    assert record.record_status is RecordStatus.UNDER_REVIEW
    assert record.status_reason == "The seat row contradicts the claim."
    assert record.next_step == "An officer reviews the contradiction."


async def test_a_source_outage_waits_and_never_contradicts(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov)
    await assign_seats(session, [enrolment.id], actor_id=None)
    gov.apaar.down = True
    await run_checks(session, [enrolment.id], gov)
    record = await _record(session, enrolment.id)
    assert record.record_status is RecordStatus.AWAITING_EVIDENCE
    assert record.status_reason == "Identity is not confirmed yet."
    assert record.next_step == "Waiting for APAAR registry to respond; a recheck asks again."


async def test_a_student_no_disputes_the_record_until_an_officer_upholds_the_claim(
    world, session, gov
) -> None:
    enrolment = await _checked(world, session, gov)
    admin = await world.user()
    before = (await _record(session, enrolment.id)).record_status_at

    await _student_says(session, enrolment, NoticeResponse.NO)
    record = await _record(session, enrolment.id)
    assert (record.record_status, record.status_reason, record.next_step) == (
        RecordStatus.DISPUTED,
        DISPUTED_REASON,
        DISPUTE_NEXT,
    )
    assert record.record_status_at is not None and record.record_status_at >= before
    dispute = await _dispute(session, enrolment)

    # documents asked for: the next step names the due date
    due = today_ist() + timedelta(days=9)
    await apply_action(
        session,
        admin,
        dispute.id,
        action=CaseActionKind.REQUEST_DOCS,
        note="Send the admission register.",
        due_date=due,
        assignee_id=None,
    )
    record = await _record(session, enrolment.id)
    assert record.record_status is RecordStatus.DISPUTED
    due_words = fmt_date(due).rsplit(" ", 1)[0]
    assert record.next_step == f"College asked for documents by {due_words}."

    # the officer upholds the college's claim: the contradiction is resolved, not evidence
    await apply_action(
        session,
        admin,
        dispute.id,
        action=CaseActionKind.UPHOLD,
        note="The register shows the student joined.",
        due_date=None,
        assignee_id=None,
    )
    student = (await _checks(session, enrolment.id))[CheckType.STUDENT]
    assert student.status is CheckStatus.CONTRADICTED
    assert student.resolved is not None
    assert (student.resolved["outcome"], student.resolved["by_id"]) == ("UPHELD", str(admin.id))
    assert student.resolved["case_id"] == str(dispute.id)
    assert isinstance(student.resolved["case_action_seq"], int)
    assert student.resolved["reason_code"] is None
    record = await _record(session, enrolment.id)
    # the joining record is still the independent evidence that countersigns
    assert record.record_status is RecordStatus.COUNTERSIGNED
    assert record.status_reason == COUNTERSIGNED_BY_COUNSELLING

    # AICTE reopens the case: disputed again
    await apply_action(
        session,
        admin,
        dispute.id,
        action=CaseActionKind.REOPEN,
        note="New statement from the student.",
        due_date=None,
        assignee_id=None,
    )
    assert (await _checks(session, enrolment.id))[CheckType.STUDENT].resolved is None
    assert (await _record(session, enrolment.id)).record_status is RecordStatus.DISPUTED


async def test_an_upheld_record_without_independent_evidence_awaits_it(world, session, gov) -> None:
    enrolment = await _checked(world, session, gov)
    admin = await world.user()
    await _student_says(session, enrolment, NoticeResponse.NO)
    # take away the joining record: only the decision would be left to countersign on
    admission = (await _checks(session, enrolment.id))[CheckType.ADMISSION]
    admission.status = CheckStatus.PENDING
    await session.flush()
    dispute = await _dispute(session, enrolment)
    await apply_action(
        session,
        admin,
        dispute.id,
        action=CaseActionKind.UPHOLD,
        note="Upheld.",
        due_date=None,
        assignee_id=None,
    )
    record = await _record(session, enrolment.id)
    assert dispute.status is FlagStatus.UPHELD
    assert record.record_status is RecordStatus.AWAITING_EVIDENCE
    assert record.next_step == (
        "Waiting for the joining record from the state admission authority."
    )


async def test_a_college_response_moves_the_next_step(world, session, gov) -> None:
    enrolment = await _checked(world, session, gov)
    admin = await world.user()
    await _student_says(session, enrolment, NoticeResponse.NO)
    dispute = await _dispute(session, enrolment)
    await apply_action(
        session,
        admin,
        dispute.id,
        action=CaseActionKind.REQUEST_DOCS,
        note="Send the register.",
        due_date=None,
        assignee_id=None,
    )
    registrar = User(
        email=f"registrar-{uuid.uuid4().hex[:8]}@college.demo",
        password_hash=hash_password(PASSWORD),
        name="Registrar",
        role=UserRole.INSTITUTION,
        institution_id=enrolment.institution_id,
    )
    session.add(registrar)
    await session.flush()
    await college_response(session, registrar, dispute.id, note="Attached.", files=[])
    record = await _record(session, enrolment.id)
    assert record.next_step == "The college responded; an officer decides the case."


async def test_records_that_are_not_active_are_left_alone(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov)
    enrolment.status = EnrolmentStatus.WITHDRAWN
    await session.flush()
    assert await refresh_record_status(session, [enrolment.id]) == 0
    record = await _record(session, enrolment.id)
    assert (record.record_status, record.record_status_at) == (
        RecordStatus.AWAITING_EVIDENCE,
        None,
    )


async def test_a_record_with_no_checks_waits_for_them(world, session, gov) -> None:
    _, _, enrolment = await _ravi(world, gov)
    assert await refresh_record_status(session, [enrolment.id]) == 1
    record = await _record(session, enrolment.id)
    assert (record.record_status, record.status_reason, record.next_step) == (
        RecordStatus.AWAITING_EVIDENCE,
        "This record has not been checked yet.",
        "Waiting for the checks to run.",
    )
    assert record.record_status_at is not None


async def test_a_case_against_another_institution_does_not_name_the_record(
    world, session, gov
) -> None:
    enrolment = await _checked(world, session, gov)
    other = await world.institution(aicte_id="1-XYZ-0002")
    session.add(
        Flag(
            type=FlagType.DUPLICATE_CROSS_INSTITUTION,
            severity=Severity.MEDIUM,
            status=FlagStatus.OPEN,
            institution_id=other.id,
            enrolment_id=None,
            related_enrolment_ids=[enrolment.id],
            evidence={"summary": "Seen at two colleges.", "facts": [], "related_enrolment_ids": []},
            dedupe_key=f"TEST:{uuid.uuid4()}",
        )
    )
    await session.flush()
    await refresh_record_status(session, [enrolment.id])
    assert (await _record(session, enrolment.id)).record_status is RecordStatus.COUNTERSIGNED


async def test_the_status_row_never_holds_a_stale_resolution(world, session, gov) -> None:
    enrolment = await _checked(world, session, gov)
    identity = (await _checks(session, enrolment.id))[CheckType.IDENTITY]
    identity.status = CheckStatus.CONTRADICTED
    identity.resolved = {"outcome": "UPHELD", "by": "x", "at": "y", "case_id": "z"}
    await session.flush()
    # the next run confirms identity again: the old decision no longer applies
    await run_checks(session, [enrolment.id], gov)
    identity = (await _checks(session, enrolment.id))[CheckType.IDENTITY]
    assert (identity.status, identity.resolved) == (CheckStatus.CONFIRMED, None)
