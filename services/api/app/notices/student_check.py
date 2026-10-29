"""The STUDENT row, derived from the enrolment's notices (D24, D37; API_CONTRACT §A3.8, §A4.4).

The row never calls an adapter. `derive` is pure: it reads the notice facts and the
student's contact details on the subject and returns the row, with one STUDENT_DENIED case
intent (shown as "Student dispute") whenever a notice says No or once said No. Every answer
comes from a student signed in through DigiLocker, so an answered row is supplied by the
student and independent of the college. The student's comment travels only in memory and
into the officers-only fact of that case.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.contracts import CheckOutcome, FlagIntent
from app.engine.flags import dedupe_key
from app.models.enums import (
    CheckStatus,
    CheckType,
    ConsentStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    NoticeResponse,
    Severity,
)
from app.models.verification import Notification

if TYPE_CHECKING:
    from app.engine.checks.base import CheckSubject

SOURCE = "STUDENT_NOTICE"
SUPPLIED_BY = "Student via DigiLocker sign-in"
RULE_SOURCE = "Student's answer after DigiLocker sign-in"
FACT_SOURCE = "Student sign-in via DigiLocker"
# Dates inside sentences are the Indian calendar date (A3.1).
IST = timezone(timedelta(hours=5, minutes=30), "IST")

CHANNEL_WORDS = {NoticeChannel.EMAIL: "email", NoticeChannel.DIGILOCKER: "DigiLocker"}
CHANNEL_NAMES = {NoticeChannel.EMAIL: "Email", NoticeChannel.DIGILOCKER: "DigiLocker"}

# copy deck §6 `case.system_note.reply_changed`
REPLY_CHANGED_NOTE = (
    "The student changed the answer from No to Yes on {changed_date}. "
    "The case keeps its status until an officer decides."
)
# copy deck §15 Student findings; the quotation marks are part of the text
SAID_NO = '"I never joined"'
SAID_YES = '"I joined"'
DIGILOCKER_LINE = "Student sign-in via DigiLocker · {date}"


@dataclass(frozen=True, slots=True)
class NoticeFact:
    id: uuid.UUID
    channel: NoticeChannel
    delivery_status: NoticeDelivery
    sent_at: datetime | None
    expires_at: datetime
    response: NoticeResponse | None
    responded_at: datetime | None
    previous_response: NoticeResponse | None
    changed_at: datetime | None
    comment: str | None  # in memory only; goes only into the officer-only evidence fact


def ist_date(at: datetime) -> date:
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(IST).date()


def fmt_day(at: datetime) -> str:
    """`5 Oct 2026` for a timestamp, on the Indian calendar."""
    return ev.fmt_date(ist_date(at))


def wire_time(at: datetime | None) -> str | None:
    if at is None:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def fact_from_row(row: Notification) -> NoticeFact:
    return NoticeFact(
        id=row.id,
        channel=row.channel,
        delivery_status=row.delivery_status,
        sent_at=row.sent_at,
        expires_at=row.expires_at,
        response=row.response,
        responded_at=row.responded_at,
        previous_response=row.previous_response,
        changed_at=row.changed_at,
        comment=row.comment,
    )


async def load_notice_facts(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[NoticeFact, ...]]:
    """Every notice of each enrolment, oldest first, in one query."""
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return {}
    rows = await session.execute(
        select(
            Notification.enrolment_id,
            Notification.id,
            Notification.channel,
            Notification.delivery_status,
            Notification.sent_at,
            Notification.expires_at,
            Notification.response,
            Notification.responded_at,
            Notification.previous_response,
            Notification.changed_at,
            Notification.comment,
        )
        .where(Notification.enrolment_id.in_(ids))
        .order_by(Notification.enrolment_id, Notification.created_at, Notification.id)
    )
    out: dict[uuid.UUID, list[NoticeFact]] = {}
    for enrolment_id, *values in rows.all():
        out.setdefault(enrolment_id, []).append(NoticeFact(*values))
    return {k: tuple(v) for k, v in out.items()}


def has_linked_apaar(subject: CheckSubject) -> bool:
    return subject.consent_status is ConsentStatus.LINKED and subject.apaar_last4 is not None


def reachable(subject: CheckSubject) -> bool:
    return subject.has_email or has_linked_apaar(subject)


def _answered_at(notice: NoticeFact) -> datetime:
    """When the current answer was given: the change when there was one."""
    at = notice.changed_at or notice.responded_at
    assert at is not None
    return at


def _sent_or_created(notice: NoticeFact) -> datetime:
    """The send time; for a notice answered before it was delivered, its creation time."""
    if notice.sent_at is not None:
        return notice.sent_at
    return notice.expires_at - timedelta(days=get_rules().notices.expiry_days)


def _latest(notices: Sequence[NoticeFact]) -> NoticeFact:
    """The most recently delivered notice."""
    return max(notices, key=lambda n: (n.sent_at or n.expires_at, n.expires_at))


def _day(at: datetime, now: datetime) -> str:
    """`12 Aug` in the current calendar year, `12 Aug 2025` otherwise (API_CONTRACT §A4.1)."""
    return ev.short_date(ist_date(at), ist_date(now))


def _answered(
    status: CheckStatus,
    basis: str,
    state: str,
    finding: str,
    summary: str,
    notice: NoticeFact,
) -> tuple[CheckStatus, dict[str, Any]]:
    return status, {
        "summary": summary,
        "finding": finding,
        "source_line": DIGILOCKER_LINE,
        "basis": basis,
        "notice_state": state,
        "channel": notice.channel.value,
        "sent_at": wire_time(notice.sent_at),
        "responded_at": wire_time(_answered_at(notice)),
        "changed": notice.changed_at is not None,
    }


def _waiting(basis: str, finding: str, source_line: str, summary: str, **extra: Any):
    return CheckStatus.PENDING, {
        "summary": summary,
        "finding": finding,
        "source_line": source_line,
        "basis": basis,
        **extra,
    }


def _status_and_detail(subject: CheckSubject, now: datetime) -> tuple[CheckStatus, dict[str, Any]]:
    notices = subject.notices
    no = [n for n in notices if n.response is NoticeResponse.NO]
    if no:
        notice = min(no, key=_answered_at)
        when = _day(_answered_at(notice), now)
        return _answered(
            CheckStatus.CONTRADICTED,
            "DENIED",
            "DENIED",
            SAID_NO,
            f"The student signed in with DigiLocker on {when} and said they never joined.",
            notice,
        )
    yes = [n for n in notices if n.response is NoticeResponse.YES]
    if yes:
        notice = min(yes, key=_answered_at)
        if notice.previous_response is NoticeResponse.NO and notice.changed_at is not None:
            assert notice.responded_at is not None
            summary = (
                f"The student said they never joined on {_day(notice.responded_at, now)}, "
                f"then changed the answer to Yes on {_day(notice.changed_at, now)}."
            )
            return _answered(
                CheckStatus.CONFIRMED, "CONFIRMED_CHANGED", "CONFIRMED", SAID_YES, summary, notice
            )
        when = _day(_answered_at(notice), now)
        return _answered(
            CheckStatus.CONFIRMED,
            "CONFIRMED",
            "CONFIRMED",
            SAID_YES,
            f"The student signed in with DigiLocker on {when} and said they joined.",
            notice,
        )

    delivered = [n for n in notices if n.delivery_status is NoticeDelivery.SENT]
    if not delivered:
        extra: dict[str, Any] = {}
        if any(n.delivery_status is NoticeDelivery.FAILED for n in notices):
            extra["delivery_failed"] = True
        if subject.notice_consent_withdrawn:
            extra["consent_withdrawn"] = True
        # no email and no linked APAAR: no notice can be sent, but the student can still
        # sign in and answer
        state = "NOT_SENT" if reachable(subject) else "UNREACHABLE"
        return _waiting(
            state,
            "notice not sent yet",
            "No notice sent yet",
            "Notice not sent yet.",
            notice_state=state,
            **extra,
        )

    live = [n for n in delivered if n.expires_at > now]
    if live:
        notice = _latest(live)
        assert notice.sent_at is not None
        sent = _day(notice.sent_at, now)
        return _waiting(
            "SENT",
            "no answer yet",
            f"Notice sent {sent}",
            f"Notice sent on {sent}; no answer yet.",
            notice_state="SENT",
            channel=notice.channel.value,
            sent_at=wire_time(notice.sent_at),
        )
    notice = _latest(delivered)
    expired = _day(notice.expires_at, now)
    return _waiting(
        "EXPIRED",
        "no answer",
        f"Notice expired {expired}",
        f"No answer before the notice expired on {expired}. Silence never counts against "
        "the record.",
        notice_state="EXPIRED",
        channel=notice.channel.value,
        sent_at=wire_time(notice.sent_at),
    )


def student_denied_evidence(notice: NoticeFact, *, enrolment_id: uuid.UUID) -> dict[str, Any]:
    """The Student dispute evidence for the notice that carried (or carried, then dropped) a
    No (copy deck §5)."""
    sent_date = fmt_day(_sent_or_created(notice))
    changed_to_yes = (
        notice.response is NoticeResponse.YES
        and notice.previous_response is NoticeResponse.NO
        and notice.changed_at is not None
    )
    if changed_to_yes:
        assert notice.changed_at is not None and notice.responded_at is not None
        replied_on = fmt_day(notice.responded_at)
        summary = (
            f"The student said they never joined on {replied_on}, "
            f"then changed the answer to Yes on {fmt_day(notice.changed_at)}."
        )
    else:
        replied_on = fmt_day(_answered_at(notice))
        summary = (
            f"The student said they never joined, after signing in with DigiLocker on {replied_on}."
        )
    facts = [
        ev.fact("Signed in with", "DigiLocker", FACT_SOURCE),
        ev.fact("Notice sent", sent_date, "Countersign"),
        ev.fact("Answered on", replied_on, FACT_SOURCE),
    ]
    if changed_to_yes:
        assert notice.changed_at is not None
        facts.append(ev.fact("Answer changed", f"Yes on {fmt_day(notice.changed_at)}", FACT_SOURCE))
    facts.append(
        ev.fact(
            "Comment from the student",
            notice.comment or "None",
            FACT_SOURCE,
            audience=ev.AUDIENCE_OFFICER,
        )
    )
    return {
        "summary": summary,
        "facts": facts,
        "related_enrolment_ids": [str(enrolment_id)],
        "rule_source": RULE_SOURCE,
    }


def _denied_notice(notices: Sequence[NoticeFact]) -> NoticeFact | None:
    """The No that decides the check, else a No later changed to Yes."""
    no = [n for n in notices if n.response is NoticeResponse.NO]
    if no:
        return min(no, key=_answered_at)
    dropped = [
        n
        for n in notices
        if n.previous_response is NoticeResponse.NO and n.response is NoticeResponse.YES
    ]
    if dropped:
        return min(dropped, key=lambda n: n.responded_at or n.expires_at)
    return None


def _deciding_notice(notices: Sequence[NoticeFact]) -> NoticeFact | None:
    """The notice whose answer decides the check: the first No, else the first Yes."""
    for response in (NoticeResponse.NO, NoticeResponse.YES):
        answers = [n for n in notices if n.response is response]
        if answers:
            return min(answers, key=_answered_at)
    return None


def derive(subject: CheckSubject, *, now: datetime | None = None) -> CheckOutcome:
    """The STUDENT outcome for one enrolment; the first matching row of §A3.8 wins. An
    answer carries its provenance: the student, independent of the college, when they
    answered (D34)."""
    now = now or datetime.now(UTC)
    status, detail = _status_and_detail(subject, now)
    deciding = _deciding_notice(subject.notices)
    flags: tuple[FlagIntent, ...] = ()
    denied = _denied_notice(subject.notices)
    if denied is not None:
        flags = (
            FlagIntent(
                type=FlagType.STUDENT_DENIED,
                severity=Severity.HIGH,
                institution_id=subject.institution_id,
                academic_year=subject.academic_year,
                dedupe_key=dedupe_key(FlagType.STUDENT_DENIED, subject.enrolment_id),
                evidence=student_denied_evidence(denied, enrolment_id=subject.enrolment_id),
                programme_id=subject.programme_id,
                enrolment_id=subject.enrolment_id,
            ),
        )
    if status is CheckStatus.CONTRADICTED:
        detail["case_type"] = FlagType.STUDENT_DENIED.value
    if deciding is None:
        return CheckOutcome(
            type=CheckType.STUDENT, status=status, source=SOURCE, detail=detail, flags=flags
        )
    return CheckOutcome(
        type=CheckType.STUDENT,
        status=status,
        source=SOURCE,
        detail=detail,
        flags=flags,
        supplied_by=SUPPLIED_BY,
        observed_at=_answered_at(deciding),
        independent=True,
    )
