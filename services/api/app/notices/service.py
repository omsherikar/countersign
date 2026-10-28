"""The notice page, replies, resends and the notice lists (D23, D24, API_CONTRACT §A3.3 to §A3.7).

`apply_reply` is the one code path for a reply, whether it comes through the public link or
the demo seed: it records the answer, the student's notice consent on a Yes, re-derives the
STUDENT check (which raises or refreshes STUDENT_DENIED), notes a No changed to Yes on the
flag's history, and asks for the enrolment proof. Services raise ApiError with the Addendum
3 codes, so the routers stay thin.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import credentials
from app.cases.service import add_system_note
from app.core import audit
from app.core.crypto import mask_apaar
from app.core.errors import ApiError
from app.core.rules import get_rules
from app.engine.checks import refresh_student
from app.engine.flags import dedupe_key
from app.models.credential import Credential
from app.models.enums import (
    AuditAction,
    ConsentPurpose,
    ConsentState,
    EnrolmentStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    NoticeResponse,
    UserRole,
)
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Flag, Notification
from app.notices.dispatch import channels_for, create_notices
from app.notices.student_check import REPLY_CHANGED_NOTE, fmt_day, wire_time
from app.privacy.notice import NOTICE_VERSION, consent_text
from app.privacy.service import notice_consent_withdrawn, record_consent

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
COMMENT_MAX = 500
CONSENT_CHANNELS = {
    NoticeChannel.EMAIL: "NOTICE_EMAIL",
    NoticeChannel.DIGILOCKER: "NOTICE_DIGILOCKER",
}
VIA_LINK = "notice-link"
VIA_SEED = "demo-seed"


@dataclass(frozen=True, slots=True)
class ReplyOutcome:
    notice: Notification
    recorded: bool  # False when the same answer came again and nothing changed
    changed: bool  # the one allowed change of answer
    credential: Credential | None = None


def notice_consent(institution_name: str) -> str:
    """The NOTICE consent text (copy deck consent.notice) a Yes records, D30."""
    return consent_text(ConsentPurpose.NOTICE, institution_name=institution_name)


def _not_found() -> ApiError:
    return ApiError(404, "NOTICE_NOT_FOUND", "This link is not valid.", {})


def _expired() -> ApiError:
    return ApiError(
        410, "NOTICE_EXPIRED", "This link has expired. Ask your college to resend the notice.", {}
    )


def _window() -> timedelta:
    return timedelta(days=get_rules().notices.change_window_days)


def notice_state(notice: Notification, now: datetime) -> str:
    """QUEUED, FAILED, AWAITING, EXPIRED or ANSWERED (§A3.6)."""
    if notice.response is not None:
        return "ANSWERED"
    if notice.delivery_status is NoticeDelivery.FAILED:
        return "FAILED"
    if notice.delivery_status is NoticeDelivery.QUEUED:
        return "QUEUED"
    return "EXPIRED" if notice.expires_at <= now else "AWAITING"


def is_live(notice: Notification, now: datetime) -> bool:
    return (
        notice.response is None
        and notice.delivery_status is not NoticeDelivery.FAILED
        and notice.expires_at > now
    )


def can_change_until(notice: Notification, now: datetime) -> datetime | None:
    if notice.responded_at is None or notice.changed_at is not None:
        return None
    until = notice.responded_at + _window()
    return until if until > now else None


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


# --------------------------------------------------------------------- the public page


async def find_by_token(
    session: AsyncSession, token: str, *, for_update: bool = False
) -> Notification:
    """The notice the link token opens; 404 NOTICE_NOT_FOUND, the same for any bad token."""
    if not TOKEN_RE.fullmatch(token or ""):
        raise _not_found()
    stmt = select(Notification).where(
        Notification.token_hash == hashlib.sha256(token.encode("ascii")).hexdigest()
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    notice = (await session.execute(stmt)).scalar_one_or_none()
    if notice is None:
        raise _not_found()
    return notice


def masked_id(student: Student) -> tuple[str, str]:
    """(id_kind, id_masked) as public surfaces show them (§A3.1)."""
    if student.apaar_last4:
        return "APAAR", mask_apaar(student.apaar_last4) or ""
    provisional = student.provisional_id or ""
    return "PROVISIONAL", "PRV-XXXX" + (provisional[-4:] if provisional else "XXXX")


async def public_body(
    session: AsyncSession, notice: Notification, *, now: datetime | None = None
) -> dict[str, Any]:
    """The §A3.3 body: the claim and the answer, with no name, birth date or full id."""
    now = now or datetime.now(UTC)
    enrolment, student, institution, programme = (
        await session.execute(
            select(Enrolment, Student, Institution, Programme)
            .join(Student, Student.id == Enrolment.student_id)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .where(Enrolment.id == notice.enrolment_id)
        )
    ).one()
    id_kind, id_masked = masked_id(student)
    return {
        "channel": notice.channel.value,
        "institution_name": institution.name,
        "programme_code": programme.code,
        "programme_name": programme.name,
        "academic_year": enrolment.academic_year,
        "year_of_study": enrolment.year_of_study,
        "id_kind": id_kind,
        "id_masked": id_masked,
        "uploaded_at": wire_time(enrolment.uploaded_at),
        "sent_at": wire_time(notice.sent_at),
        "expires_at": wire_time(notice.expires_at),
        "response": _value(notice.response),
        "responded_at": wire_time(notice.responded_at),
        "previous_response": _value(notice.previous_response),
        "changed_at": wire_time(notice.changed_at),
        "can_change_until": wire_time(can_change_until(notice, now)),
        "consent_text": notice_consent(institution.name),
        "notice_version": NOTICE_VERSION,
    }


async def open_notice(session: AsyncSession, token: str) -> dict[str, Any]:
    """GET /notices/{token}: 410 for an unanswered notice past its expiry; the first view
    sets `opened_at`; every view is a READ in the audit chain with no actor."""
    notice = await find_by_token(session, token, for_update=True)
    now = datetime.now(UTC)
    if notice.response is None and notice.expires_at <= now:
        raise _expired()
    if notice.opened_at is None:
        notice.opened_at = now
    await audit.record(
        session, None, AuditAction.READ, "notification", notice.id, after={"via": VIA_LINK}
    )
    return await public_body(session, notice, now=now)


async def respond(
    session: AsyncSession, token: str, response: NoticeResponse, comment: str | None
) -> dict[str, Any]:
    """POST /notices/{token}/respond: the §A3.3 body after the reply."""
    notice = await find_by_token(session, token, for_update=True)
    outcome = await apply_reply(session, notice, response, comment, via=VIA_LINK)
    return await public_body(session, outcome.notice)


async def respond_for_enrolment(
    session: AsyncSession,
    enrolment_id: uuid.UUID,
    channel: NoticeChannel,
    response: NoticeResponse,
    comment: str | None,
    *,
    via: str = VIA_SEED,
) -> Notification:
    """A reply without a token (the demo seed, D31): the latest delivered notice of the
    channel, else the latest notice of that channel, else of the other channel."""
    notices = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.enrolment_id == enrolment_id)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
            )
        )
        .scalars()
        .all()
    )

    def pick(rows: list[Notification]) -> Notification | None:
        sent = [n for n in rows if n.delivery_status is NoticeDelivery.SENT]
        return (sent or rows or [None])[0]

    chosen = pick([n for n in notices if n.channel is channel]) or pick(list(notices))
    if chosen is None:
        raise _not_found()
    outcome = await apply_reply(session, chosen, response, comment, via=via)
    return outcome.notice


async def _denied_flag(session: AsyncSession, enrolment_id: uuid.UUID) -> Flag | None:
    return (
        await session.execute(
            select(Flag).where(Flag.dedupe_key == dedupe_key(FlagType.STUDENT_DENIED, enrolment_id))
        )
    ).scalar_one_or_none()


def _clean_comment(response: NoticeResponse, comment: str | None) -> str | None:
    if response is not NoticeResponse.NO or comment is None:
        return None
    return comment.strip()[:COMMENT_MAX] or None


async def apply_reply(
    session: AsyncSession,
    notice: Notification,
    response: NoticeResponse,
    comment: str | None,
    *,
    via: str,
    now: datetime | None = None,
) -> ReplyOutcome:
    """Rules 2 to 5 of §A3.4 and their effects, in the caller's transaction."""
    now = now or datetime.now(UTC)
    notice = (
        await session.execute(
            select(Notification)
            .where(Notification.id == notice.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    first = notice.response
    changed = False
    if first is None:
        if notice.expires_at <= now:
            raise _expired()
        notice.response = response
        notice.responded_at = now
        notice.comment = _clean_comment(response, comment)
    elif first is response:
        return ReplyOutcome(notice=notice, recorded=False, changed=False)
    else:
        if notice.changed_at is not None:
            raise ApiError(
                409,
                "NOTICE_ALREADY_CHANGED",
                "You have already changed your answer once.",
                {"reason": "CHANGED_ONCE"},
            )
        assert notice.responded_at is not None
        if now > notice.responded_at + _window():
            raise ApiError(
                409,
                "NOTICE_ALREADY_CHANGED",
                "Answers can be changed only within 7 days of the first reply.",
                {"reason": "WINDOW_CLOSED"},
            )
        notice.previous_response = first
        notice.response = response
        notice.changed_at = now
        if response is NoticeResponse.NO:
            notice.comment = _clean_comment(response, comment)
        changed = True
    await session.flush()
    await audit.record(
        session,
        None,
        AuditAction.UPDATE,
        "notification",
        notice.id,
        before={"response": _value(first)},
        after={
            "response": response.value,
            "previous_response": _value(notice.previous_response),
            "via": via,
        },
    )
    enrolment = await session.get(Enrolment, notice.enrolment_id)
    assert enrolment is not None
    if response is NoticeResponse.YES:
        institution = await session.get(Institution, enrolment.institution_id)
        assert institution is not None
        await record_consent(
            session,
            student_id=notice.student_id,
            purpose=ConsentPurpose.NOTICE,
            status=ConsentState.GIVEN,
            channel=CONSENT_CHANNELS[notice.channel],
            notice_text=notice_consent(institution.name),
            enrolment_id=enrolment.id,
        )
    await refresh_student(session, [enrolment.id])
    if changed and response is NoticeResponse.YES:
        flag = await _denied_flag(session, enrolment.id)
        if flag is not None:
            assert notice.changed_at is not None
            await add_system_note(
                session, flag, REPLY_CHANGED_NOTE.format(changed_date=fmt_day(notice.changed_at))
            )
    credential = await credentials.issue_if_eligible(session, enrolment.id)
    return ReplyOutcome(notice=notice, recorded=True, changed=changed, credential=credential)


# ------------------------------------------------------------------------- resends


async def _notices_of(session: AsyncSession, enrolment_id: uuid.UUID) -> list[Notification]:
    """Every notice of the enrolment, newest first."""
    return list(
        (
            await session.execute(
                select(Notification)
                .where(Notification.enrolment_id == enrolment_id)
                .order_by(
                    Notification.created_at.desc(),
                    Notification.channel,
                    Notification.id,
                )
            )
        )
        .scalars()
        .all()
    )


def resends_used(notices: list[Notification]) -> int:
    """Rows with `resent_by_id` on the channel that has most of them (§A3.5)."""
    counts = Counter(n.channel for n in notices if n.resent_by_id is not None)
    return max(counts.values(), default=0)


async def _block(
    session: AsyncSession, enrolment: Enrolment, notices: list[Notification], now: datetime
) -> ApiError | None:
    """Why a resend is not possible now, in the order of §A3.5; None when it is."""
    rules = get_rules().notices
    if enrolment.status is not EnrolmentStatus.ACTIVE:
        return ApiError(
            409, "CONFLICT", "Notices go only to active enrolments.", {"reason": "NOT_ACTIVE"}
        )
    if any(n.response is not None for n in notices):
        return ApiError(
            409, "NOTICE_LIVE", "The student has already replied.", {"reason": "ANSWERED"}
        )
    live = [n for n in notices if is_live(n, now)]
    if live:
        notice = max(live, key=lambda n: n.expires_at)
        sent = notice.sent_at or notice.created_at or now
        return ApiError(
            409,
            "NOTICE_LIVE",
            f"A notice sent on {fmt_day(sent)} is open until {fmt_day(notice.expires_at)}.",
            {"reason": "LIVE", "expires_at": wire_time(notice.expires_at)},
        )
    if await notice_consent_withdrawn(session, [enrolment.student_id]):
        return ApiError(
            409,
            "CONFLICT",
            "The student has asked not to receive notices.",
            {"reason": "CONSENT_WITHDRAWN"},
        )
    student = await session.get(Student, enrolment.student_id)
    assert student is not None
    if not channels_for(student.email, student.consent_status, student.apaar_last4):
        return ApiError(
            409,
            "CONFLICT",
            "The student has no email address or linked APAAR to send a notice to.",
            {"reason": "NO_CHANNEL"},
        )
    if resends_used(notices) >= rules.resend_limit:
        return ApiError(
            429,
            "RESEND_LIMIT",
            f"This notice has been resent {rules.resend_limit} times this academic year.",
            {"limit": rules.resend_limit},
        )
    return None


async def resend(session: AsyncSession, enrolment: Enrolment, user: User) -> list[Notification]:
    """New QUEUED notices for an enrolment with no live and no answered notice (§A3.5).

    The caller commits and then hands delivery to the worker.
    """
    await session.execute(
        select(Enrolment.id).where(Enrolment.id == enrolment.id).with_for_update()
    )
    now = datetime.now(UTC)
    blocked = await _block(session, enrolment, await _notices_of(session, enrolment.id), now)
    if blocked is not None:
        raise blocked
    return await create_notices(
        session, [enrolment.id], resent_by_id=user.id, actor_id=user.id, now=now
    )


async def resend_state(session: AsyncSession, enrolment: Enrolment, user: User) -> dict[str, Any]:
    """`{allowed, blocked_by, resends_left}` for enrolment detail and the resend answer."""
    notices = await _notices_of(session, enrolment.id)
    left = max(0, get_rules().notices.resend_limit - resends_used(notices))
    if user.role not in (UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION):
        return {"allowed": False, "blocked_by": "ROLE", "resends_left": left}
    blocked = await _block(session, enrolment, notices, datetime.now(UTC))
    if blocked is None:
        return {"allowed": True, "blocked_by": None, "resends_left": left}
    reason = blocked.details.get("reason") or "LIMIT"
    return {"allowed": False, "blocked_by": reason, "resends_left": left}


# --------------------------------------------------------------------------- lists


def enrolment_notice(notice: Notification, now: datetime) -> dict[str, Any]:
    """EnrolmentNotice (§A3.7): never the token, the message or the comment."""
    return {
        "id": str(notice.id),
        "channel": notice.channel.value,
        "state": notice_state(notice, now),
        "delivery_status": notice.delivery_status.value,
        "attempts": notice.attempts,
        "last_error": notice.last_error,
        "sent_at": wire_time(notice.sent_at),
        "expires_at": wire_time(notice.expires_at),
        "response": _value(notice.response),
        "responded_at": wire_time(notice.responded_at),
        "previous_response": _value(notice.previous_response),
        "changed_at": wire_time(notice.changed_at),
        "resent": notice.resent_by_id is not None,
    }


async def notices_for_enrolment(
    session: AsyncSession, enrolment_id: uuid.UUID
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    return [enrolment_notice(n, now) for n in await _notices_of(session, enrolment_id)]


async def notices_for_student(session: AsyncSession, student_id: uuid.UUID) -> list[dict[str, Any]]:
    """StudentNotice (§A3.6), newest first. There is no link: only its hash is stored."""
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(Notification, Enrolment.academic_year, Institution.name, Programme.name)
            .join(Enrolment, Enrolment.id == Notification.enrolment_id)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .where(Notification.student_id == student_id)
            .order_by(Notification.created_at.desc(), Notification.channel, Notification.id)
        )
    ).all()
    return [
        {
            "id": str(notice.id),
            "enrolment_id": str(notice.enrolment_id),
            "channel": notice.channel.value,
            "institution_name": institution_name,
            "programme_name": programme_name,
            "academic_year": academic_year,
            "state": notice_state(notice, now),
            "delivery_status": notice.delivery_status.value,
            "sent_at": wire_time(notice.sent_at),
            "expires_at": wire_time(notice.expires_at),
            "response": _value(notice.response),
            "responded_at": wire_time(notice.responded_at),
            "changed_at": wire_time(notice.changed_at),
            "can_change_until": wire_time(can_change_until(notice, now)),
        }
        for notice, academic_year, institution_name, programme_name in rows
    ]
