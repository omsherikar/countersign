"""Creating and delivering student notices (D23, API_CONTRACT §A3.2, ENGINES §16.2, §16.3).

A notice is created QUEUED with a placeholder token hash. Each delivery try mints a fresh
token, commits its hash and only then sends the link, so a plaintext token exists only in
the process that sends it and in the message itself. Email goes first; DigiLocker calls
run concurrently behind a semaphore, and an outage of either is retried in the same call
after a pause before the row is marked FAILED.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import credentials
from app.adapters.base import (
    AdapterRequestError,
    AdapterSet,
    RealAdapterDisabled,
    SourceUnavailable,
)
from app.adapters.factory import build_adapters
from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.crypto import decrypt
from app.core.rules import get_rules
from app.db.session import session_factory
from app.engine.checks import refresh_student
from app.engine.contracts import CHUNK_SIZE
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    ConsentStatus,
    EnrolmentStatus,
    NoticeChannel,
    NoticeDelivery,
    UploadStatus,
)
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.verification import Check, Notification
from app.notices.mailer import NO_ANSWER, Mailer, MailMessage, build_mailer
from app.notices.student_check import fmt_day
from app.privacy.service import notice_consent_withdrawn

log = logging.getLogger("countersign.notices")

RETRY_PAUSES_SECONDS = (5, 20)  # before the second and the third try
MAX_ATTEMPTS = 3
DIGILOCKER_TRIP = 5  # consecutive unavailable calls that end a DigiLocker pass

# copy deck §8 and §23: notice.email_subject, notice.email_body (sent in English with the
# Hindi text under it), notice.digilocker. A notice only points to DigiLocker sign-in (D37):
# nothing in it can record an answer.
EMAIL_SUBJECT = "{institution_name} has reported an enrolment in your name"
EMAIL_BODY = (
    "{institution_name} has told AICTE that you joined {programme_name} in {academic_year}. "
    "To see what they reported and to answer, open {link} and sign in with DigiLocker. "
    "Your answer is recorded only after you sign in with DigiLocker; nothing in this email "
    "can record it. The link works until {expires_date}. Never share your DigiLocker OTP "
    "with anyone, including AICTE or your college."
)
EMAIL_BODY_HI = (
    "{institution_name} ने AICTE को बताया है कि आपने {academic_year} में {programme_name} में "
    "प्रवेश लिया है। उन्होंने क्या बताया है यह देखने और उत्तर देने के लिए {link} खोलें और "
    "DigiLocker से साइन इन करें। आपका उत्तर DigiLocker से साइन इन करने के बाद ही दर्ज होता है; "
    "इस ईमेल से कुछ भी दर्ज नहीं हो सकता। यह लिंक {expires_date} तक काम करेगा। अपना DigiLocker "
    "OTP किसी के साथ साझा न करें, AICTE या अपने कॉलेज के साथ भी नहीं।"
)
# proposed notice.email_provisional_line (API_CONTRACT §A4.13): a student without a linked
# APAAR needs the provisional id to claim the record after signing in
EMAIL_PROVISIONAL_LINE = (
    "Your college recorded you without an APAAR. Your provisional ID is {provisional_id}; "
    "you need it to claim the record after signing in."
)
DIGILOCKER_TEXT = (
    "{institution_name} has reported that you joined {programme_short} ({academic_year}). "
    "Sign in to Countersign with DigiLocker to answer."
)
# The stored email text keeps this slot where the link goes; the link is put in only
# when the message is sent, so it is never stored.
LINK_SLOT = "{link}"
NOTICE_HEADER = "X-Countersign-Notice"

# last_error sentences (API_CONTRACT §A3.2)
NO_ACCOUNT = "No DigiLocker account."
DIGILOCKER_DOWN = "DigiLocker did not respond."
DIGILOCKER_REFUSED = "DigiLocker refused the notice."
DIGILOCKER_OFF = "DigiLocker is not connected."
NO_EMAIL = "No email address on record."
NO_APAAR = "No linked APAAR on record."


@dataclass(frozen=True, slots=True)
class NoticeContext:
    """What a notice says: the claim the college made."""

    institution_name: str
    programme_name: str
    programme_code: str
    academic_year: str
    expires_at: datetime
    # in full, only for a student without a linked APAAR (the email carries it)
    provisional_id: str | None = None


@dataclass(slots=True)
class DeliveryTally:
    sent: int = 0
    failed: int = 0
    tries: int = 0
    by_error: dict[str, int] = field(default_factory=dict)

    def failure(self, error: str) -> None:
        self.failed += 1
        self.by_error[error] = self.by_error.get(error, 0) + 1


def programme_short(name: str, code: str) -> str:
    """`B.Tech CSE` for `B.Tech Computer Science and Engineering`, else the name (§A3.1)."""
    first = name.split(" ", 1)[0]
    return f"{first} {code}" if "." in first else name


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def mint_token() -> tuple[str, str]:
    """(token, sha256 hex). 32 random bytes, URL-safe: 43 characters."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def placeholder_hash() -> str:
    """A unique hash of a value nobody keeps, until the first delivery try mints a token."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def notice_link(token: str) -> str:
    return f"{get_settings().web_origin.rstrip('/')}/student/notices/{token}"


def notice_text(channel: NoticeChannel, facts: NoticeContext) -> tuple[str, str]:
    """(subject or "", text without the link). The email text keeps LINK_SLOT."""
    values = {
        "institution_name": facts.institution_name,
        "programme_name": facts.programme_name,
        "programme_short": programme_short(facts.programme_name, facts.programme_code),
        "academic_year": facts.academic_year,
    }
    if channel is NoticeChannel.EMAIL:
        expires_date = fmt_day(facts.expires_at)
        english = EMAIL_BODY.format(**values, link=LINK_SLOT, expires_date=expires_date)
        if facts.provisional_id:
            english += " " + EMAIL_PROVISIONAL_LINE.format(provisional_id=facts.provisional_id)
        hindi = EMAIL_BODY_HI.format(**values, link=LINK_SLOT, expires_date=expires_date)
        return EMAIL_SUBJECT.format(**values), f"{english}\n\n{hindi}"
    return "", DIGILOCKER_TEXT.format(**values)


def _chunks[T](items: Sequence[T], size: int = CHUNK_SIZE) -> list[Sequence[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


# ------------------------------------------------------------------------- creation


async def needs_notice(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> list[uuid.UUID]:
    """The enrolments among the ids with no live and no answered notice, in their order."""
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return []
    now = datetime.now(UTC)
    covered = set(
        (
            await session.execute(
                select(Notification.enrolment_id)
                .where(
                    Notification.enrolment_id.in_(ids),
                    or_(
                        Notification.response.is_not(None),
                        and_(
                            Notification.delivery_status != NoticeDelivery.FAILED,
                            Notification.expires_at > now,
                        ),
                    ),
                )
                .distinct()
            )
        ).scalars()
    )
    return [i for i in ids if i not in covered]


def channels_for(
    email: str | None, consent: ConsentStatus, apaar_last4: str | None
) -> list[NoticeChannel]:
    """EMAIL when an address is on record, DIGILOCKER when the APAAR is linked."""
    out: list[NoticeChannel] = []
    if email:
        out.append(NoticeChannel.EMAIL)
    if consent is ConsentStatus.LINKED and apaar_last4 is not None:
        out.append(NoticeChannel.DIGILOCKER)
    return out


async def create_notices(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    *,
    resent_by_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    now: datetime | None = None,
) -> list[Notification]:
    """One QUEUED notice per channel for each ACTIVE enrolment among the ids, audited.

    Enrolments whose student has no channel get none. Flushes, never commits.
    """
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return []
    now = now or datetime.now(UTC)
    expires_at = now + timedelta(days=get_rules().notices.expiry_days)
    rows = (
        await session.execute(
            select(
                Enrolment.id,
                Enrolment.student_id,
                Enrolment.academic_year,
                Student.email,
                Student.consent_status,
                Student.apaar_last4,
                Student.provisional_id,
                Institution.name,
                Programme.name,
                Programme.code,
            )
            .join(Student, Student.id == Enrolment.student_id)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .where(Enrolment.id.in_(ids), Enrolment.status == EnrolmentStatus.ACTIVE)
        )
    ).all()
    by_id = {row[0]: row for row in rows}
    created: list[Notification] = []
    for enrolment_id in ids:
        row = by_id.get(enrolment_id)
        if row is None:
            continue
        _, student_id, year, email, consent, last4, provisional, inst_name, prog_name, prog_code = (
            row
        )
        linked = consent is ConsentStatus.LINKED and last4 is not None
        facts = NoticeContext(
            inst_name, prog_name, prog_code, year, expires_at, None if linked else provisional
        )
        for channel in channels_for(email, consent, last4):
            created.append(
                Notification(
                    id=uuid.uuid4(),
                    student_id=student_id,
                    enrolment_id=enrolment_id,
                    channel=channel,
                    token_hash=placeholder_hash(),
                    message=notice_text(channel, facts)[1],
                    delivery_status=NoticeDelivery.QUEUED,
                    attempts=0,
                    expires_at=expires_at,
                    resent_by_id=resent_by_id,
                )
            )
    if not created:
        return []
    session.add_all(created)
    await session.flush()
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.CREATE,
                entity_type="notification",
                entity_id=n.id,
                actor_id=actor_id,
                after={
                    "enrolment_id": str(n.enrolment_id),
                    "channel": n.channel.value,
                    "resent": resent_by_id is not None,
                },
            )
            for n in created
        ],
    )
    return created


# ------------------------------------------------------------------------- delivery


@dataclass(slots=True)
class _Job:
    id: uuid.UUID
    channel: NoticeChannel
    link: str
    text: str
    subject: str
    email: str | None
    apaar_encrypted: bytes | None


@dataclass(frozen=True, slots=True)
class _Outcome:
    ok: bool
    error: str | None = None
    transient: bool = False


@dataclass(slots=True)
class _Breaker:
    """Ends a DigiLocker pass after DIGILOCKER_TRIP unavailable calls in a row."""

    in_a_row: int = 0
    tripped: bool = False

    def record(self, unavailable: bool) -> None:
        self.in_a_row = self.in_a_row + 1 if unavailable else 0
        if self.in_a_row >= DIGILOCKER_TRIP:
            self.tripped = True


async def _mint(
    factory: async_sessionmaker[AsyncSession], ids: Sequence[uuid.UUID], channel: NoticeChannel
) -> list[_Job]:
    """One transaction: a fresh token per QUEUED row and one more try counted."""
    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    Notification,
                    Student.email,
                    Student.apaar_encrypted,
                    Student.consent_status,
                    Institution.name,
                    Programme.name,
                    Programme.code,
                    Enrolment.academic_year,
                )
                .join(Enrolment, Enrolment.id == Notification.enrolment_id)
                .join(Student, Student.id == Notification.student_id)
                .join(Institution, Institution.id == Enrolment.institution_id)
                .join(Programme, Programme.id == Enrolment.programme_id)
                .where(
                    Notification.id.in_(list(ids)),
                    Notification.channel == channel,
                    Notification.delivery_status == NoticeDelivery.QUEUED,
                    Notification.attempts < MAX_ATTEMPTS,
                )
                .order_by(Notification.id)
                .with_for_update(of=Notification, skip_locked=True)
            )
        ).all()
        jobs: list[_Job] = []
        for notice, email, apaar, consent, inst_name, prog_name, prog_code, year in rows:
            token, digest = mint_token()
            notice.token_hash = digest
            notice.attempts += 1
            subject = ""
            if channel is NoticeChannel.EMAIL:
                facts = NoticeContext(inst_name, prog_name, prog_code, year, notice.expires_at)
                subject = notice_text(channel, facts)[0]
            linked = consent is ConsentStatus.LINKED
            jobs.append(
                _Job(
                    id=notice.id,
                    channel=channel,
                    link=notice_link(token),
                    text=notice.message,
                    subject=subject,
                    email=email,
                    apaar_encrypted=apaar if linked else None,
                )
            )
        await session.commit()
    return jobs


async def _send_emails(jobs: Sequence[_Job], mailer: Mailer) -> dict[uuid.UUID, _Outcome]:
    outcomes: dict[uuid.UUID, _Outcome] = {}
    sendable = [j for j in jobs if j.email]
    for job in jobs:
        if not job.email:
            outcomes[job.id] = _Outcome(ok=False, error=NO_EMAIL)
    if not sendable:
        return outcomes
    messages = [
        MailMessage(
            to=job.email or "",
            subject=job.subject,
            body=job.text.replace(LINK_SLOT, job.link),
            headers={NOTICE_HEADER: str(job.id)},
        )
        for job in sendable
    ]
    try:
        results = await asyncio.to_thread(mailer.send_many, messages)
    except Exception:
        log.exception("mailer failed", extra={"data": {"messages": len(messages)}})
        results = []
    for i, job in enumerate(sendable):
        if i >= len(results):
            outcomes[job.id] = _Outcome(ok=False, error=NO_ANSWER, transient=True)
            continue
        result = results[i]
        outcomes[job.id] = _Outcome(ok=result.ok, error=result.error, transient=result.transient)
    return outcomes


async def _notify(
    job: _Job, adapters: AdapterSet, gate: asyncio.Semaphore, breaker: _Breaker
) -> _Outcome:
    apaar = None
    if job.apaar_encrypted:
        try:
            apaar = decrypt(job.apaar_encrypted)
        except ValueError:
            apaar = None
    if not apaar:
        return _Outcome(ok=False, error=NO_APAAR)
    async with gate:
        if breaker.tripped:
            return _Outcome(ok=False, error=DIGILOCKER_DOWN, transient=True)
        try:
            result = await adapters.digilocker.notify(apaar, job.text, job.link)
        except SourceUnavailable:
            breaker.record(unavailable=True)
            return _Outcome(ok=False, error=DIGILOCKER_DOWN, transient=True)
        except AdapterRequestError as exc:
            breaker.record(unavailable=False)
            if exc.status_code == 404:
                return _Outcome(ok=False, error=NO_ACCOUNT)
            return _Outcome(ok=False, error=DIGILOCKER_REFUSED)
        except RealAdapterDisabled:
            return _Outcome(ok=False, error=DIGILOCKER_OFF)
        except Exception:
            log.exception("digilocker notify failed", extra={"data": {"notice": str(job.id)}})
            breaker.record(unavailable=True)
            return _Outcome(ok=False, error=DIGILOCKER_DOWN, transient=True)
    breaker.record(unavailable=False)
    if result.delivered:
        return _Outcome(ok=True)
    if result.reason == "APAAR_NOT_LINKED":
        return _Outcome(ok=False, error=NO_ACCOUNT)
    return _Outcome(ok=False, error=DIGILOCKER_REFUSED)


async def _record(
    factory: async_sessionmaker[AsyncSession],
    outcomes: dict[uuid.UUID, _Outcome],
    tally: DeliveryTally,
) -> list[uuid.UUID]:
    """One transaction: SENT, FAILED, or QUEUED again for another try; returns the latter."""
    retry: list[uuid.UUID] = []
    if not outcomes:
        return retry
    now = datetime.now(UTC)
    entries: list[AuditEntry] = []
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(Notification)
                    .where(Notification.id.in_(list(outcomes)))
                    .order_by(Notification.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for notice in rows:
            outcome = outcomes[notice.id]
            tally.tries += 1
            if not outcome.ok:
                # the link of a failed try must never open the notice
                notice.token_hash = placeholder_hash()
            if outcome.ok:
                notice.delivery_status = NoticeDelivery.SENT
                notice.sent_at = now
                notice.last_error = None
                tally.sent += 1
            elif outcome.transient and notice.attempts < MAX_ATTEMPTS:
                notice.last_error = outcome.error
                retry.append(notice.id)
                continue
            else:
                notice.delivery_status = NoticeDelivery.FAILED
                notice.last_error = outcome.error
                tally.failure(outcome.error or DIGILOCKER_DOWN)
            after: dict[str, object] = {
                "delivery_status": notice.delivery_status.value,
                "attempts": notice.attempts,
            }
            if notice.last_error:
                after["last_error"] = notice.last_error
            entries.append(
                AuditEntry(
                    action=AuditAction.UPDATE,
                    entity_type="notification",
                    entity_id=notice.id,
                    after=after,
                )
            )
        await session.flush()
        await audit.record_many(session, entries)
        await session.commit()
    return retry


async def _by_channel(
    factory: async_sessionmaker[AsyncSession], ids: Sequence[uuid.UUID]
) -> dict[NoticeChannel, list[uuid.UUID]]:
    """The ids split by channel, each list in the order given."""
    channel_of: dict[uuid.UUID, NoticeChannel] = {}
    async with factory() as session:
        for chunk in _chunks(ids, 10 * CHUNK_SIZE):
            rows = await session.execute(
                select(Notification.id, Notification.channel).where(
                    Notification.id.in_(list(chunk))
                )
            )
            channel_of.update((i, c) for i, c in rows.all())
    out: dict[NoticeChannel, list[uuid.UUID]] = {c: [] for c in NoticeChannel}
    for notification_id in ids:
        if notification_id in channel_of:
            out[channel_of[notification_id]].append(notification_id)
    return out


async def _deliver_pass(
    factory: async_sessionmaker[AsyncSession],
    remaining: dict[NoticeChannel, list[uuid.UUID]],
    adapters: AdapterSet,
    mailer: Mailer,
    tally: DeliveryTally,
) -> dict[NoticeChannel, list[uuid.UUID]]:
    """Every row once, all the email first (one send per 500, so one SMTP connection per
    500), then DigiLocker. Returns the rows to try again."""
    retry: dict[NoticeChannel, list[uuid.UUID]] = {c: [] for c in NoticeChannel}
    for chunk in _chunks(remaining[NoticeChannel.EMAIL]):
        jobs = await _mint(factory, chunk, NoticeChannel.EMAIL)
        if jobs:
            outcomes = await _send_emails(jobs, mailer)
            retry[NoticeChannel.EMAIL] += await _record(factory, outcomes, tally)
    breaker = _Breaker()
    gate = asyncio.Semaphore(max(1, get_settings().checks_concurrency))
    for chunk in _chunks(remaining[NoticeChannel.DIGILOCKER]):
        jobs = await _mint(factory, chunk, NoticeChannel.DIGILOCKER)
        if not jobs:
            continue
        results = await asyncio.gather(*(_notify(j, adapters, gate, breaker) for j in jobs))
        outcomes = {j.id: r for j, r in zip(jobs, results, strict=True)}
        retry[NoticeChannel.DIGILOCKER] += await _record(factory, outcomes, tally)
    return retry


async def deliver(
    factory: async_sessionmaker[AsyncSession],
    notification_ids: Sequence[uuid.UUID],
    *,
    adapters: AdapterSet,
    mailer: Mailer,
) -> DeliveryTally:
    """Deliver QUEUED notices: up to MAX_ATTEMPTS tries, pausing before each retry."""
    tally = DeliveryTally()
    remaining = await _by_channel(factory, list(dict.fromkeys(notification_ids)))
    for attempt in range(MAX_ATTEMPTS):
        if not any(remaining.values()):
            break
        if attempt:
            await asyncio.sleep(RETRY_PAUSES_SECONDS[attempt - 1])
        remaining = await _deliver_pass(factory, remaining, adapters, mailer, tally)
    return tally


async def issue_due_proofs(session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]) -> int:
    """`credentials.issue_if_eligible` for those among the enrolments whose STUDENT check
    is PASS, the first condition of eligibility; returns how many proofs were issued."""
    ids = list(dict.fromkeys(enrolment_ids))
    issued = 0
    for chunk in _chunks(ids):
        passed = (
            await session.execute(
                select(Check.enrolment_id)
                .where(
                    Check.enrolment_id.in_(list(chunk)),
                    Check.type == CheckType.STUDENT,
                    Check.status == CheckStatus.CONFIRMED,
                )
                .order_by(Check.enrolment_id)
            )
        ).scalars()
        for enrolment_id in list(passed):
            if await credentials.issue_if_eligible(session, enrolment_id) is not None:
                issued += 1
    return issued


async def _refresh(
    factory: async_sessionmaker[AsyncSession],
    enrolment_ids: Sequence[uuid.UUID],
    *,
    issue: bool,
) -> None:
    """In chunks, one transaction each: re-derive STUDENT, then issue proofs that are due."""
    for chunk in _chunks(list(dict.fromkeys(enrolment_ids))):
        async with factory() as session:
            await refresh_student(session, chunk)
            if issue:
                await issue_due_proofs(session, chunk)
            await session.commit()


async def deliver_notices(
    notification_ids: Sequence[uuid.UUID],
    *,
    factory: async_sessionmaker[AsyncSession] | None = None,
    adapters: AdapterSet | None = None,
    mailer: Mailer | None = None,
) -> int:
    """Deliver the given notices, then refresh the STUDENT check of their enrolments.

    The body of the task `countersign.deliver_notices` (resends, and QUEUED rows a stopped
    worker left behind). Returns how many were sent.
    """
    ids = list(dict.fromkeys(notification_ids))
    if not ids:
        return 0
    factory = factory or session_factory()
    own_adapters = adapters is None
    adapters = adapters if adapters is not None else build_adapters()
    try:
        tally = await deliver(factory, ids, adapters=adapters, mailer=mailer or build_mailer())
    finally:
        if own_adapters:
            await adapters.aclose()
    async with factory() as session:
        enrolment_ids = list(
            (
                await session.execute(
                    select(Notification.enrolment_id).where(Notification.id.in_(ids)).distinct()
                )
            ).scalars()
        )
    await _refresh(factory, enrolment_ids, issue=False)
    log.info(
        "notices delivered",
        extra={"data": {"sent": tally.sent, "failed": tally.failed, "tries": tally.tries}},
    )
    return tally.sent


async def send_notices_for_batch(
    batch_id: uuid.UUID,
    *,
    factory: async_sessionmaker[AsyncSession] | None = None,
    adapters: AdapterSet | None = None,
    mailer: Mailer | None = None,
) -> int:
    """Create and deliver the notices of one DONE batch; returns how many it created.

    Every ACTIVE enrolment of the batch that needs a notice gets one per channel, whatever
    its Identity result; a student who withdrew notice consent or has no channel gets none.
    A second run creates nothing. Owns its sessions and commits (ENGINES §16.2).
    """
    factory = factory or session_factory()
    async with factory() as session:
        batch = await session.get(UploadBatch, batch_id)
        if batch is None or batch.status is not UploadStatus.DONE:
            return 0
        rows = (
            await session.execute(
                select(Enrolment.id, Enrolment.student_id)
                .where(
                    Enrolment.upload_batch_id == batch_id,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
                .order_by(Enrolment.source_row_no.nulls_last(), Enrolment.id)
            )
        ).all()
    if not rows:
        return 0
    student_of = {enrolment_id: student_id for enrolment_id, student_id in rows}
    enrolment_ids = list(student_of)

    created: list[uuid.UUID] = []
    for chunk in _chunks(enrolment_ids):
        async with factory() as session:
            need = await needs_notice(session, chunk)
            withdrawn = await notice_consent_withdrawn(session, [student_of[e] for e in need])
            need = [e for e in need if student_of[e] not in withdrawn]
            notices = await create_notices(session, need, resent_by_id=None, actor_id=None)
            await session.commit()
            created.extend(n.id for n in notices)

    if created:
        own_adapters = adapters is None
        adapters = adapters if adapters is not None else build_adapters()
        try:
            tally = await deliver(
                factory, created, adapters=adapters, mailer=mailer or build_mailer()
            )
        finally:
            if own_adapters:
                await adapters.aclose()
        log.info(
            "batch notices delivered",
            extra={
                "data": {
                    "batch_id": str(batch_id),
                    "created": len(created),
                    "sent": tally.sent,
                    "failed": tally.failed,
                    "errors": tally.by_error,
                }
            },
        )
    await _refresh(factory, enrolment_ids, issue=True)
    return len(created)
