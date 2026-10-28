"""Replies: POST /notices/{token}/respond and their effects (API_CONTRACT §A3.4, §A3.8, D24)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app import credentials
from app.db.session import session_factory
from app.engine.checks import run_checks
from app.models.audit import AuditLog
from app.models.credential import Consent, Credential
from app.models.enums import (
    AuditAction,
    CaseActionKind,
    CheckStatus,
    CheckType,
    ConsentPurpose,
    ConsentState,
    CredentialKind,
    FlagStatus,
    FlagType,
    NoticeChannel,
    Severity,
)
from app.models.verification import CaseAction, Check, Flag, Notification
from app.notices.student_check import fmt_day
from tests.notices.conftest import delivered, notices_of

EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER


@pytest.fixture
def issued(monkeypatch) -> list:
    """Enrolments the code asked to issue a proof for."""
    calls: list = []

    async def issue_if_eligible(session, enrolment_id):
        calls.append(enrolment_id)
        return None

    monkeypatch.setattr(credentials, "issue_if_eligible", issue_if_eligible)
    return calls


async def check_of(enrolment_id) -> Check:
    async with session_factory()() as s:
        return (
            await s.execute(
                select(Check).where(
                    Check.enrolment_id == enrolment_id, Check.type == CheckType.STUDENT
                )
            )
        ).scalar_one()


async def denied_flag(enrolment_id) -> Flag | None:
    async with session_factory()() as s:
        return (
            await s.execute(select(Flag).where(Flag.dedupe_key == f"STUDENT_DENIED:{enrolment_id}"))
        ).scalar_one_or_none()


async def reply(public, token: str, response: str, comment: str | None = None):
    body = {"response": response} if comment is None else {"response": response, "comment": comment}
    return await public.post(f"/notices/{token}/respond", json=body)


async def test_a_yes_countersigns_records_consent_and_asks_for_the_proof(
    world, mailer, public, issued
):
    enrolment, tokens = await delivered(world, mailer)
    response = await reply(public, tokens[EMAIL], "YES", "ignored with a yes")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response"] == "YES" and body["previous_response"] is None
    responded = datetime.fromisoformat(body["responded_at"].replace("Z", "+00:00"))
    assert body["can_change_until"] == (responded + timedelta(days=7)).isoformat().replace(
        "+00:00", "Z"
    )
    check = await check_of(enrolment.id)
    assert check.status is CheckStatus.PASS
    assert check.detail["summary"] == f"Confirmed by the student on {fmt_day(responded)} (email)."
    assert check.detail["notice_state"] == "CONFIRMED"
    email, _ = await notices_of(enrolment.id)
    assert email.comment is None
    async with session_factory()() as s:
        [consent] = (
            (await s.execute(select(Consent).where(Consent.purpose == ConsentPurpose.NOTICE)))
            .scalars()
            .all()
        )
        [audit] = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "notification",
                        AuditLog.action == AuditAction.UPDATE,
                        AuditLog.entity_id == email.id,
                        AuditLog.after["via"].astext == "notice-link",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert (consent.purpose, consent.status, consent.channel) == (
        ConsentPurpose.NOTICE,
        ConsentState.GIVEN,
        "NOTICE_EMAIL",
    )
    assert consent.enrolment_id == enrolment.id and consent.notice_version == "v1"
    assert consent.notice_text == body["consent_text"]
    assert audit.actor_id is None
    assert audit.after == {"response": "YES", "previous_response": None, "via": "notice-link"}
    assert issued == [enrolment.id]
    assert await denied_flag(enrolment.id) is None

    # the same answer again changes nothing
    again = await reply(public, tokens[EMAIL], "YES")
    assert again.status_code == 200 and again.json()["responded_at"] == body["responded_at"]
    assert issued == [enrolment.id]


async def test_a_no_fails_the_check_and_raises_the_flag_with_the_comment_for_officers(
    world, mailer, public, clients, issued
):
    enrolment, tokens = await delivered(world, mailer)
    response = await reply(public, tokens[DIGILOCKER], "NO", "  I did not join this college. ")
    assert response.status_code == 200 and response.json()["response"] == "NO"
    check = await check_of(enrolment.id)
    assert check.status is CheckStatus.FAIL and check.detail["notice_state"] == "DENIED"
    assert check.detail["summary"].endswith("(DigiLocker).")
    flag = await denied_flag(enrolment.id)
    assert (flag.type, flag.severity, flag.status) == (
        FlagType.STUDENT_DENIED,
        Severity.HIGH,
        FlagStatus.OPEN,
    )
    assert flag.enrolment_id == enrolment.id and flag.related_enrolment_ids == [enrolment.id]
    async with session_factory()() as s:
        consents = (
            (await s.execute(select(Consent).where(Consent.purpose == ConsentPurpose.NOTICE)))
            .scalars()
            .all()
        )
        logged = (
            await s.execute(select(AuditLog.after).where(AuditLog.entity_type == "notification"))
        ).scalars()
        assert not any("did not join" in str(after) for after in logged)
    assert consents == []

    officer = (await clients["admin"].get(f"/flags/{flag.id}")).json()
    registrar = (await clients["abc"].get(f"/flags/{flag.id}")).json()
    comment = {"label": "Comment from the student", "value": "I did not join this college."}
    assert any(
        f["label"] == comment["label"] and f["value"] == comment["value"]
        for f in officer["evidence"]["facts"]
    )
    assert "Comment from the student" not in str(registrar)
    assert "did not join" not in str(registrar)
    # the enrolment page never carries the comment
    detail = (await clients["abc"].get(f"/enrolments/{enrolment.id}")).text
    assert "did not join" not in detail


async def test_a_no_on_one_channel_beats_a_yes_on_the_other(world, mailer, public, issued):
    enrolment, tokens = await delivered(world, mailer)
    await reply(public, tokens[EMAIL], "YES")
    assert (await check_of(enrolment.id)).status is CheckStatus.PASS
    await reply(public, tokens[DIGILOCKER], "NO")
    assert (await check_of(enrolment.id)).status is CheckStatus.FAIL
    assert (await denied_flag(enrolment.id)) is not None


async def test_no_then_yes_passes_keeps_the_flag_and_notes_it_once(
    world, mailer, public, clients, issued
):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    await reply(public, tokens[EMAIL], "NO", "Not me")
    flag = await denied_flag(enrolment.id)
    async with session_factory()() as s:
        await s.execute(
            update(Flag).where(Flag.id == flag.id).values(status=FlagStatus.DOCS_REQUESTED)
        )
        await s.commit()

    changed = await reply(public, tokens[EMAIL], "YES")
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["response"], body["previous_response"]) == ("YES", "NO")
    assert body["changed_at"] and body["can_change_until"] is None
    check = await check_of(enrolment.id)
    assert check.status is CheckStatus.PASS and check.detail["changed"] is True

    flag = await denied_flag(enrolment.id)
    assert flag.status is FlagStatus.DOCS_REQUESTED  # only officers resolve flags
    changed_at = datetime.fromisoformat(body["changed_at"].replace("Z", "+00:00"))
    assert flag.evidence["summary"].endswith(
        f"then changed the reply to Yes on {fmt_day(changed_at)}."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Reply changed"] == f"Yes on {fmt_day(changed_at)}"
    assert facts["Comment from the student"] == "Not me"
    async with session_factory()() as s:
        notes = (
            (
                await s.execute(
                    select(CaseAction).where(
                        CaseAction.flag_id == flag.id,
                        CaseAction.action == CaseActionKind.SYSTEM_NOTE,
                    )
                )
            )
            .scalars()
            .all()
        )
        consents = (
            (await s.execute(select(Consent).where(Consent.purpose == ConsentPurpose.NOTICE)))
            .scalars()
            .all()
        )
    assert [(n.note, n.actor_id) for n in notes] == [
        (
            f"The student changed the reply from No to Yes on {fmt_day(changed_at)}. "
            "The flag keeps its status until an officer decides.",
            None,
        )
    ]
    assert [c.status for c in consents] == [ConsentState.GIVEN]
    assert issued == [enrolment.id, enrolment.id]

    # a second change is refused
    again = await reply(public, tokens[EMAIL], "NO")
    assert again.status_code == 409
    assert again.json()["error"] == {
        "code": "NOTICE_ALREADY_CHANGED",
        "message": "You have already changed your answer once.",
        "details": {"reason": "CHANGED_ONCE"},
    }


async def test_yes_then_no_fails_and_raises_the_flag(world, mailer, public, issued):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    await reply(public, tokens[EMAIL], "YES")
    assert await denied_flag(enrolment.id) is None
    changed = await reply(public, tokens[EMAIL], "NO", "Someone used my details")
    assert changed.status_code == 200
    assert (await check_of(enrolment.id)).status is CheckStatus.FAIL
    flag = await denied_flag(enrolment.id)
    assert flag.status is FlagStatus.OPEN
    [notice] = await notices_of(enrolment.id)
    assert notice.comment == "Someone used my details"


async def test_a_change_after_seven_days_is_refused(world, mailer, public, issued):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    await reply(public, tokens[EMAIL], "YES")
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(
                responded_at=datetime.now(UTC) - timedelta(days=8),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await s.commit()
    # an answered notice stays readable after its expiry, without the change offer
    page = await public.get(f"/notices/{tokens[EMAIL]}")
    assert page.status_code == 200 and page.json()["can_change_until"] is None
    refused = await reply(public, tokens[EMAIL], "NO")
    assert refused.status_code == 409
    assert refused.json()["error"]["details"] == {"reason": "WINDOW_CLOSED"}
    assert refused.json()["error"]["message"] == (
        "Answers can be changed only within 7 days of the first reply."
    )


async def test_a_change_inside_the_window_is_allowed_after_expiry(world, mailer, public, issued):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    await reply(public, tokens[EMAIL], "NO")
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()
    assert (await reply(public, tokens[EMAIL], "YES")).status_code == 200


async def test_an_unanswered_expired_notice_cannot_be_answered(world, mailer, public, issued):
    enrolment, tokens = await delivered(world, mailer, apaar=None)
    async with session_factory()() as s:
        await s.execute(
            update(Notification)
            .where(Notification.enrolment_id == enrolment.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()
    response = await reply(public, tokens[EMAIL], "YES")
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "NOTICE_EXPIRED"
    assert issued == []


async def test_the_reply_body_is_validated(world, mailer, public, issued):
    _, tokens = await delivered(world, mailer, apaar=None)
    assert (await reply(public, tokens[EMAIL], "MAYBE")).status_code == 422
    too_long = await reply(public, tokens[EMAIL], "NO", "x" * 501)
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (await reply(public, tokens[EMAIL], "NO", "x" * 500)).status_code == 200


async def test_a_reupload_keeps_the_derived_status(world, mailer, public, issued):
    confirmed, yes_tokens = await delivered(world, mailer, apaar=None)
    denied, no_tokens = await delivered(world, mailer, apaar=None)
    await reply(public, yes_tokens[EMAIL], "YES")
    await reply(public, no_tokens[EMAIL], "NO")
    before = {e.id: (await check_of(e.id)).detail for e in (confirmed, denied)}
    # an upload that touches the rows runs all five checks again
    async with session_factory()() as s:
        await run_checks(s, [confirmed.id, denied.id], world.gov)
        await s.commit()
    assert (await check_of(confirmed.id)).status is CheckStatus.PASS
    assert (await check_of(denied.id)).status is CheckStatus.FAIL
    assert {e.id: (await check_of(e.id)).detail for e in (confirmed, denied)} == before
    assert (await denied_flag(denied.id)).status is FlagStatus.OPEN


async def test_a_yes_issues_the_enrolment_proof_and_a_no_does_not(world, mailer, public, clients):
    confirmed, yes_tokens = await delivered(world, mailer)
    denied, no_tokens = await delivered(world, mailer)
    await reply(public, yes_tokens[DIGILOCKER], "YES")
    await reply(public, no_tokens[EMAIL], "NO")
    async with session_factory()() as s:
        proofs = (await s.execute(select(Credential))).scalars().all()
    assert [(c.enrolment_id, c.kind, c.revoked) for c in proofs] == [
        (confirmed.id, CredentialKind.ENROLMENT, False)
    ]
    # the proof shows on enrolment detail and in the student's overview
    detail = (await clients["admin"].get(f"/enrolments/{confirmed.id}")).json()
    assert [(c["kind"], c["status"]) for c in detail["credentials"]] == [("ENROLMENT", "ACTIVE")]
    student = await world.student_login(confirmed)
    me = (await student.get("/students/me")).json()
    await student.aclose()
    assert [(c["kind"], c["enrolment_id"]) for c in me["credentials"]] == [
        ("ENROLMENT", str(confirmed.id))
    ]
    assert (await clients["admin"].get(f"/enrolments/{denied.id}")).json()["credentials"] == []
