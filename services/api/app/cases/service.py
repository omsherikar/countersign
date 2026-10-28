"""Officer case work on flags (D25). `add_system_note` is used by the notices loop and the
flags engine; the rest of the case service lives here too.

Every function runs in the caller's transaction and flushes, never commits. Engines never
change a flag's status; only `apply_action` does, through the transition table.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

import app.credentials as credentials
from app.cases import transitions
from app.cases.attachments import StoredFile
from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.errors import ApiError, not_found
from app.engine.evidence import fmt_date
from app.engine.status import (
    clear_resolved,
    mark_resolved,
    named_enrolments,
    refresh_record_status,
)
from app.engine.upload.types import INDIA
from app.models.enums import AuditAction, CaseActionKind, FlagStatus, FlagType, UserRole
from app.models.geo import Region
from app.models.institution import Institution, Programme
from app.models.user import User
from app.models.verification import CaseAction, CaseAttachment, Flag
from app.notices.mailer import MailMessage

EVIDENCE_UPDATED_NOTE = "Evidence updated after the decision."
NOTE_MAX = 2000
DUE_MAX_DAYS = 90
# the revocation reason code when an officer withdraws the claim (its wire value is unchanged)
WITHDRAW_REASON = "FLAG_CONFIRMED"

NOTE_REQUIRED = "Add a note before you continue."
NOTE_TOO_LONG = "Write at most 2,000 characters."
DUE_RANGE = "Choose a date from today up to 90 days ahead."
ASSIGNEE_MISSING = "Choose an officer, or send null to remove the assignee."
ASSIGNEE_UNSEEN = "Choose an officer who can see this flag."
ASSIGNEE_NOT_AICTE = "Escalate to an AICTE officer."

# copy deck flag.<TYPE>.name
FLAG_NAMES = {
    FlagType.EXCESS_ADMISSION: "Excess admission",
    FlagType.QUOTA_BREACH: "Quota breach",
    FlagType.LATE_REFILL: "Late refill",
    FlagType.INVALID_APAAR: "APAAR not verified",
    FlagType.NAME_MISMATCH: "Name or date of birth mismatch",
    FlagType.DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
    FlagType.DUPLICATE_WITHIN_UPLOAD: "Duplicate within institution",
    FlagType.DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
    FlagType.NO_ACADEMIC_ACTIVITY: "No academic activity",
    FlagType.STUDENT_DENIED: "Student denied",
    FlagType.GHOST_RING: "Shared contact ring",
    FlagType.ANOMALY: "Unusual pattern",
    FlagType.NOT_IN_JOINING_RECORD: "Not in the joining record",
    FlagType.ELIGIBILITY_BREACH: "Category eligibility breach",
    FlagType.MISSING_FROM_UPLOAD: "Missing from upload",
}
# copy deck email.docs_request.*
DOCS_SUBJECT = "Documents requested by AICTE: {flag_name}, {where}"
DOCS_BODY = (
    "{role_word} has asked {institution_name} for documents about a flag. "
    'Flag: {flag_name}, {where}. Evidence: {summary} Request: "{note}" {due_sentence}'
    "Sign in to Countersign and open the flag to respond: {link}. "
    "Attach PDF, PNG or JPEG files, up to 3, 5 MB each. "
    "Nothing about your college or its students has changed; an officer decides after "
    "reading your response. This email went to every registrar account of your college."
)
DOCS_DUE = "Please reply by {due_date}."


@dataclass(slots=True)
class ActionResult:
    flag: Flag
    action: CaseAction
    # the REQUEST_DOCS emails, sent by the router after the commit
    messages: list[MailMessage] = field(default_factory=list)


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def invalid(field_name: str, message: str) -> ApiError:
    """422 on one field, in the shape of the validation handler."""
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field_name}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field_name, "message": message}]},
    )


def today_ist() -> date:
    return datetime.now(INDIA).date()


# --------------------------------------------------------------------------- scope


def scope_flags(stmt: Select, user: User) -> Select:
    """Restrict a SELECT joined to the flag's institution to what the user may see."""
    if user.role is UserRole.AICTE_ADMIN:
        return stmt
    if user.role is UserRole.RO_OFFICER:
        return stmt.where(Institution.region_id == user.region_id)
    if user.role is UserRole.INSTITUTION:
        return stmt.where(Flag.institution_id == user.institution_id)
    return stmt.where(false())


async def scoped_flag(
    session: AsyncSession, user: User, flag_id: uuid.UUID, *, for_update: bool = False
) -> Flag:
    """The flag, or 404 "Flag not found." outside the caller's scope."""
    stmt = scope_flags(
        select(Flag)
        .join(Institution, Institution.id == Flag.institution_id)
        .where(Flag.id == flag_id),
        user,
    )
    if for_update:
        stmt = stmt.with_for_update(of=Flag)
    flag = (
        await session.execute(stmt.execution_options(populate_existing=True))
    ).scalar_one_or_none()
    if flag is None:
        raise not_found("Flag")
    return flag


async def _flag_region(session: AsyncSession, flag: Flag) -> uuid.UUID:
    region_id = (
        await session.execute(
            select(Institution.region_id).where(Institution.id == flag.institution_id)
        )
    ).scalar_one()
    return region_id


def can_be_assigned(officer: User | None, region_id: uuid.UUID) -> bool:
    """An active AICTE officer, or an active regional officer of the flag's region."""
    if officer is None or not officer.is_active:
        return False
    if officer.role is UserRole.AICTE_ADMIN:
        return True
    return officer.role is UserRole.RO_OFFICER and officer.region_id == region_id


# -------------------------------------------------------------------------- actions


async def _checked_assignee(
    session: AsyncSession, flag: Flag, assignee_id: uuid.UUID, *, escalate: bool
) -> uuid.UUID:
    officer = await session.get(User, assignee_id)
    if not can_be_assigned(officer, await _flag_region(session, flag)):
        raise invalid("assignee_id", ASSIGNEE_UNSEEN)
    assert officer is not None
    if escalate and officer.role is not UserRole.AICTE_ADMIN:
        raise invalid("assignee_id", ASSIGNEE_NOT_AICTE)
    return officer.id


async def apply_action(
    session: AsyncSession,
    user: User,
    flag_id: uuid.UUID,
    *,
    action: CaseActionKind,
    note: str | None,
    due_date: date | None,
    assignee_id: uuid.UUID | None,
    assignee_given: bool = True,
) -> ActionResult:
    """One officer action (API_CONTRACT §A3.9, §A3.10). Scope 404, then 403 or 409 from the
    table, then the field rules (422). Flushes only; REQUEST_DOCS returns its emails."""
    flag = await scoped_flag(session, user, flag_id, for_update=True)
    new_status = transitions.check(user.role, flag.status, action)

    note = (note or "").strip() or None
    if action is CaseActionKind.ASSIGN:
        note = None
    elif note is None:
        raise invalid("note", NOTE_REQUIRED)
    elif len(note) > NOTE_MAX:
        raise invalid("note", NOTE_TOO_LONG)
    if action is CaseActionKind.REQUEST_DOCS and due_date is not None:
        today = today_ist()
        if not today <= due_date <= today + timedelta(days=DUE_MAX_DAYS):
            raise invalid("due_date", DUE_RANGE)
    else:
        due_date = None
    assignee: uuid.UUID | None = None
    if action is CaseActionKind.ASSIGN:
        if not assignee_given:
            raise invalid("assignee_id", ASSIGNEE_MISSING)
        if assignee_id is not None:
            assignee = await _checked_assignee(session, flag, assignee_id, escalate=False)
    elif action is CaseActionKind.ESCALATE and assignee_id is not None:
        assignee = await _checked_assignee(session, flag, assignee_id, escalate=True)

    now = datetime.now(UTC)
    from_status = flag.status
    flag.status = new_status
    if action is CaseActionKind.REQUEST_DOCS:
        flag.docs_due_on = due_date
        flag.response_received = False
    elif action is CaseActionKind.ESCALATE:
        if assignee is not None:
            flag.assignee_id = assignee
    elif action in (CaseActionKind.UPHOLD, CaseActionKind.WITHDRAW):
        flag.resolved_at = now
    elif action is CaseActionKind.ASSIGN:
        flag.assignee_id = assignee
    elif action is CaseActionKind.REOPEN:
        flag.resolved_at = None
        flag.docs_due_on = None
        flag.response_received = False
    flag.last_action_at = now

    records_assignee = action is CaseActionKind.ASSIGN or assignee is not None
    row = CaseAction(
        flag_id=flag.id,
        actor_id=user.id,
        action=action,
        note=note,
        attachments=[],
        at=now,
        from_status=from_status,
        to_status=new_status,
        due_date=due_date,
        assignee_id=assignee if records_assignee else None,
    )
    session.add(row)
    await session.flush()
    after: dict[str, Any] = {
        "action": action.value,
        "from_status": from_status.value,
        "to_status": new_status.value,
        "case_action_seq": row.seq,
    }
    if records_assignee:
        after["assignee_id"] = str(assignee) if assignee else None
    if due_date is not None:
        after["due_date"] = due_date.isoformat()
    # the note is never written to the audit log
    await audit.record(session, user.id, AuditAction.UPDATE, "flag", flag.id, after=after)

    # an upheld claim resolves the contradiction it decided, without becoming evidence (R2)
    if action is CaseActionKind.UPHOLD:
        await mark_resolved(
            session,
            flag,
            FlagStatus.UPHELD,
            actor_id=user.id,
            at=now,
            case_action_seq=row.seq,
            reason_code=row.reason_code,
        )
    elif action is CaseActionKind.REOPEN:
        await clear_resolved(session, flag)
    await refresh_record_status(session, named_enrolments(flag), now=now)

    if action is CaseActionKind.UPHOLD:
        for enrolment_id in named_enrolments(flag):
            await credentials.issue_if_eligible(session, enrolment_id)
    elif action is CaseActionKind.WITHDRAW and flag.enrolment_id is not None:
        # nothing on the enrolment, its seat or its checks changes; its proofs are revoked
        await credentials.revoke_for_enrolment(session, flag.enrolment_id, WITHDRAW_REASON, user.id)

    messages: list[MailMessage] = []
    if action is CaseActionKind.REQUEST_DOCS:
        messages = await docs_request_messages(session, flag, row, user)
    return ActionResult(flag=flag, action=row, messages=messages)


async def college_response(
    session: AsyncSession,
    user: User,
    flag_id: uuid.UUID,
    *,
    note: str,
    files: Sequence[StoredFile],
) -> CaseAction:
    """The college's answer while DOCS_REQUESTED: the status stays, the flag is marked as
    answered and each stored file gets a `case_attachments` row. Flushes only."""
    flag = await scoped_flag(session, user, flag_id, for_update=True)
    status = transitions.check(user.role, flag.status, CaseActionKind.COLLEGE_RESPONSE)
    now = datetime.now(UTC)
    row = CaseAction(
        flag_id=flag.id,
        actor_id=user.id,
        action=CaseActionKind.COLLEGE_RESPONSE,
        note=note,
        attachments=[],
        at=now,
        from_status=flag.status,
        to_status=status,
    )
    session.add(row)
    await session.flush()
    attachments = [
        CaseAttachment(
            id=uuid.uuid4(),
            flag_id=flag.id,
            case_action_seq=row.seq,
            filename=stored.filename,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            storage_key=stored.storage_key,
            uploaded_by_id=user.id,
            created_at=now,
        )
        for stored in files
    ]
    session.add_all(attachments)
    flag.response_received = True
    flag.last_action_at = now
    await session.flush()
    await refresh_record_status(session, named_enrolments(flag), now=now)
    entries = [
        AuditEntry(
            action=AuditAction.UPDATE,
            entity_type="flag",
            entity_id=flag.id,
            actor_id=user.id,
            after={
                "action": CaseActionKind.COLLEGE_RESPONSE.value,
                "from_status": status.value,
                "to_status": status.value,
                "case_action_seq": row.seq,
            },
        ),
        *(
            AuditEntry(
                action=AuditAction.CREATE,
                entity_type="case_attachment",
                entity_id=attachment.id,
                actor_id=user.id,
                after={
                    "flag_id": str(flag.id),
                    "sha256": attachment.sha256,
                    "size_bytes": attachment.size_bytes,
                    "content_type": attachment.content_type,
                },
            )
            for attachment in attachments
        ),
    ]
    await audit.record_many(session, entries)
    return row


async def add_system_note(session: AsyncSession, flag: Flag, text: str) -> CaseAction:
    """A SYSTEM_NOTE in the flag's history; never changes the flag's status. Flushes only."""
    now = datetime.now(UTC)
    row = CaseAction(
        flag_id=flag.id,
        actor_id=None,
        action=CaseActionKind.SYSTEM_NOTE,
        note=text,
        attachments=[],
        from_status=flag.status,
        to_status=flag.status,
        at=now,
    )
    session.add(row)
    flag.last_action_at = now
    await session.flush()
    await audit.record(
        session,
        None,
        AuditAction.CREATE,
        "case_action",
        flag.id,
        after={"action": CaseActionKind.SYSTEM_NOTE.value, "seq": row.seq},
    )
    return row


# -------------------------------------------------------------------------- history


async def history(session: AsyncSession, flag: Flag, user: User) -> list[dict[str, Any]]:
    """The flag's case actions in seq order as CaseHistoryItem dicts (§A3.13). A college
    never sees ASSIGN rows, the notes officers keep to themselves, or the assignee."""
    college = user.role is UserRole.INSTITUTION
    actor = aliased(User)
    assignee = aliased(User)
    rows = (
        await session.execute(
            select(
                CaseAction,
                actor.id,
                actor.name,
                actor.role,
                assignee.id,
                assignee.name,
            )
            .outerjoin(actor, actor.id == CaseAction.actor_id)
            .outerjoin(assignee, assignee.id == CaseAction.assignee_id)
            .where(CaseAction.flag_id == flag.id)
            .order_by(CaseAction.seq)
        )
    ).all()
    files: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for attachment in (
        await session.execute(
            select(CaseAttachment)
            .where(CaseAttachment.flag_id == flag.id)
            .order_by(CaseAttachment.created_at, CaseAttachment.filename, CaseAttachment.id)
        )
    ).scalars():
        files[attachment.case_action_seq].append(
            {
                "id": str(attachment.id),
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size_bytes": attachment.size_bytes,
                "sha256": attachment.sha256,
            }
        )
    out: list[dict[str, Any]] = []
    for row, actor_id, actor_name, actor_role, assignee_id, assignee_name in rows:
        if college and row.action is CaseActionKind.ASSIGN:
            continue
        hide_note = college and row.action in transitions.NOTE_INTERNAL
        out.append(
            {
                "seq": row.seq,
                "at": _iso(row.at),
                "action": row.action.value,
                "from_status": row.from_status.value if row.from_status else None,
                "to_status": row.to_status.value if row.to_status else None,
                "actor": {"id": str(actor_id), "name": actor_name, "role": actor_role.value}
                if actor_id is not None
                else None,
                "note": None if hide_note else row.note,
                "due_date": _iso(row.due_date),
                "assignee": {"id": str(assignee_id), "name": assignee_name}
                if assignee_id is not None and not college
                else None,
                "attachments": files.get(row.seq, []),
            }
        )
    return out


# ------------------------------------------------------------------------ officers


async def assignable_officers(
    session: AsyncSession, user: User, *, roles: Sequence[UserRole], flag: Flag | None
) -> Select:
    """Active officers the caller may pick, AICTE first then by name (§A3.14). A regional
    officer sees AICTE officers and its own region's officers; with a flag, only officers
    who may be assigned that flag."""
    stmt = (
        select(User.id, User.name, User.role, Region.code)
        .outerjoin(Region, Region.id == User.region_id)
        .where(User.is_active.is_(True), User.role.in_(list(roles)))
    )
    if user.role is UserRole.RO_OFFICER:
        stmt = stmt.where(or_(User.role == UserRole.AICTE_ADMIN, User.region_id == user.region_id))
    if flag is not None:
        region_id = await _flag_region(session, flag)
        stmt = stmt.where(or_(User.role == UserRole.AICTE_ADMIN, User.region_id == region_id))
    rank = case((User.role == UserRole.AICTE_ADMIN, 0), else_=1)
    return stmt.order_by(rank, User.name, User.id)


# --------------------------------------------------------------------------- email


async def _role_word(session: AsyncSession, user: User) -> str:
    if user.role is UserRole.RO_OFFICER and user.region_id is not None:
        region = await session.get(Region, user.region_id)
        if region is not None:
            return f"The {region.name} regional office"
    return "An AICTE officer"


async def docs_request_messages(
    session: AsyncSession, flag: Flag, action: CaseAction, user: User
) -> list[MailMessage]:
    """One email per active registrar of the flag's institution. It names no student and
    no officer, and quotes the summary the college itself sees."""
    institution = await session.get(Institution, flag.institution_id)
    assert institution is not None
    programme = await session.get(Programme, flag.programme_id) if flag.programme_id else None
    year = flag.academic_year or ""
    where = f"{programme.code}, {year}" if programme is not None else year
    evidence = flag.evidence or {}
    values = {
        "role_word": await _role_word(session, user),
        "institution_name": institution.name,
        "flag_name": FLAG_NAMES.get(flag.type, flag.type.value),
        "where": where,
        "summary": evidence.get("summary_for_institution") or evidence.get("summary") or "",
        "note": action.note or "",
        "due_sentence": DOCS_DUE.format(due_date=fmt_date(action.due_date)) + " "
        if action.due_date
        else "",
        "link": f"{get_settings().web_origin.rstrip('/')}/college/flags/{flag.id}",
    }
    recipients = (
        await session.execute(
            select(User.email)
            .where(
                User.role == UserRole.INSTITUTION,
                User.institution_id == flag.institution_id,
                User.is_active.is_(True),
            )
            .order_by(User.email)
        )
    ).scalars()
    subject = DOCS_SUBJECT.format(**values)
    body = DOCS_BODY.format(**values)
    return [MailMessage(to=email, subject=subject, body=body) for email in recipients]
