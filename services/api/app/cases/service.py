"""Officer case work on flags (D25, D43). `add_system_note` is used by the notices loop and
the flags engine; the rest of the case service lives here too, and the three decisions
(UPHOLD, CORRECT, WITHDRAW) are dispatched to `app.cases.decisions`.

Every function runs in the caller's transaction and flushes, never commits; the records a
case names are queued with `status.mark`, and the transaction owner settles them before it
commits (`settle_effects` for a case action). Engines never change a flag's status; only
`apply_action` does, through the transition table.
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

from app.adapters.base import AdapterSet
from app.cases import decisions, transitions
from app.cases.attachments import StoredFile
from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.errors import ApiError
from app.engine import status, versions
from app.engine.evidence import fmt_date
from app.engine.status import named_enrolments
from app.engine.upload.types import INDIA
from app.models.enums import AuditAction, CaseActionKind, FlagType, UserRole
from app.models.geo import Region
from app.models.institution import Institution, Programme
from app.models.user import User
from app.models.verification import CaseAction, CaseAttachment, Flag
from app.notices.mailer import MailMessage

EVIDENCE_UPDATED_NOTE = "Evidence updated after the decision."
NOTE_MAX = 2000
DUE_MAX_DAYS = 90

NOTE_REQUIRED = "Add a note before you continue."
REASON_REQUIRED = "Choose a reason and write a note before you decide."
REASON_MISSING = "Choose a reason before you continue."
REASON_UNKNOWN = "Choose one of the reasons for this decision."
DOCS_KIND_MISSING = "Choose what the college should send."
CASE_NOT_FOUND = "Case not found."
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
    FlagType.STUDENT_DENIED: "Student dispute",
    FlagType.GHOST_RING: "Shared contact ring",
    FlagType.ANOMALY: "Unusual pattern",
    FlagType.NOT_IN_JOINING_RECORD: "Not in joining record",
    FlagType.ELIGIBILITY_BREACH: "Seat category not eligible",
    FlagType.MISSING_FROM_UPLOAD: "Missing from upload",
}
# copy deck email.docs_request.*
DOCS_SUBJECT = "Documents requested by AICTE: {flag_name}, {where}"
DOCS_BODY = (
    "{role_word} has asked {institution_name} for {docs_words} about a case. "
    'Case: {flag_name}, {where}. Evidence: {summary} Request: "{note}" {due_sentence}'
    "Sign in to Countersign and open the case to respond: {link}. "
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
    # API_CONTRACT §A4.9 `effects`; `records` and attestations are filled by settle_effects
    effects: decisions.Effects | None = None
    tracker: decisions.Tracker | None = None


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


def case_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", CASE_NOT_FOUND)


async def scoped_flag(
    session: AsyncSession, user: User, flag_id: uuid.UUID, *, for_update: bool = False
) -> Flag:
    """The flag, or 404 "Case not found." outside the caller's scope."""
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
        raise case_not_found()
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


def allowed_actions(role: UserRole, flag: Flag) -> list[str]:
    """What the table (§A4.8) and the case's type (§A4.10) allow the role now."""
    return [
        a.value
        for a in transitions.allowed_actions(role, flag.status)
        if decisions.available(flag, a)
    ]


def _reason_rules(action: CaseActionKind, reason_code: str | None, note: str | None) -> str | None:
    """The reason code an action keeps (§A4.9): required with the note for the three
    decisions and ESCALATE (422 REASON_REQUIRED), one of the action's codes."""
    if action not in transitions.REASONED:
        return None
    missing: list[dict[str, str]] = []
    if reason_code is None:
        missing.append({"field": "reason_code", "message": REASON_MISSING})
    if note is None:
        missing.append({"field": "note", "message": NOTE_REQUIRED})
    if missing:
        raise ApiError(422, "REASON_REQUIRED", REASON_REQUIRED, {"fields": missing})
    if reason_code not in decisions.REASON_CODES[action]:
        raise invalid("reason_code", REASON_UNKNOWN)
    return reason_code


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
    reason_code: str | None = None,
    docs_kind: str | None = None,
    withdrawn_enrolment_ids: list[uuid.UUID] | None = None,
    correction: dict[str, Any] | None = None,
    approval_version: int | None = None,
    adapters: AdapterSet | None = None,
) -> ActionResult:
    """One officer action (API_CONTRACT §A4.8, §A4.9). Scope 404, then 403 or 409 from the
    table, then 409 DECISION_NOT_AVAILABLE for the case's type, then the field rules (422,
    and 409 for records a case does not name or a version that does not cover). Writes the
    case action, dispatches a decision to `app.cases.decisions`, applies the multi-record
    rule and queues the named records' statuses. Flushes only; REQUEST_DOCS returns its
    emails, and `settle_effects` completes the effects once the statuses are settled."""
    flag = await scoped_flag(session, user, flag_id, for_update=True)
    new_status = transitions.check(user.role, flag.status, action)
    if not decisions.available(flag, action):
        raise decisions.not_available(flag, action, allowed_actions(user.role, flag))

    note = (note or "").strip() or None
    if action is CaseActionKind.ASSIGN:
        note = None
    reason_code = (reason_code or "").strip() or None
    reason_code = _reason_rules(action, reason_code, note)
    if note is None and action is not CaseActionKind.ASSIGN:
        raise invalid("note", NOTE_REQUIRED)
    if note is not None and len(note) > NOTE_MAX:
        raise invalid("note", NOTE_TOO_LONG)
    if action is CaseActionKind.REQUEST_DOCS:
        if docs_kind not in decisions.DOCS_KINDS:
            raise invalid("docs_kind", DOCS_KIND_MISSING)
    else:
        docs_kind = None
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

    # the decisions' own field rules, before anything is written
    withdraw_ids: list[uuid.UUID] = []
    plan: decisions.CorrectionPlan | None = None
    approval: dict[str, Any] | None = None
    if action is CaseActionKind.WITHDRAW:
        withdraw_ids = await decisions.check_withdraw(session, flag, withdrawn_enrolment_ids)
    elif action is CaseActionKind.CORRECT:
        plan = await decisions.check_correct(session, flag, correction)
    elif action is CaseActionKind.UPHOLD:
        approval = await decisions.check_uphold(session, flag, approval_version)
    tracker = decisions.Tracker()
    await tracker.remember(session, named_enrolments(flag))

    now = datetime.now(UTC)
    from_status = flag.status
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
        reason_code=docs_kind if action is CaseActionKind.REQUEST_DOCS else reason_code,
        withdrawn_enrolment_ids=withdraw_ids,
    )
    session.add(row)
    await session.flush()

    if action is CaseActionKind.UPHOLD:
        effects = await decisions.uphold(
            session, flag, user, row, approval=approval, tracker=tracker
        )
    elif action is CaseActionKind.CORRECT:
        assert plan is not None
        effects = await decisions.correct(
            session, flag, user, row, plan=plan, adapters=adapters, tracker=tracker
        )
    elif action is CaseActionKind.WITHDRAW:
        effects = await decisions.withdraw(
            session,
            flag,
            user,
            row,
            enrolment_ids=withdraw_ids,
            adapters=adapters,
            tracker=tracker,
        )
    else:
        effects = decisions.Effects(case_status=from_status)
        if action is CaseActionKind.REOPEN:
            await decisions.clear_resolutions(session, flag, user.id)

    # a multi-record case stays as it is while a record it names is still outstanding
    if (
        action in (CaseActionKind.WITHDRAW, CaseActionKind.CORRECT)
        and decisions.rule_of(flag).scope == "MULTI_RECORD"
        and await decisions.outstanding(session, flag)
    ):
        new_status = from_status

    flag.status = new_status
    row.to_status = new_status
    effects.case_status = new_status
    if new_status in transitions.DECIDED and from_status not in transitions.DECIDED:
        flag.resolved_at = now
    if action is CaseActionKind.REQUEST_DOCS:
        flag.docs_due_on = due_date
        flag.response_received = False
    elif action is CaseActionKind.ESCALATE:
        if assignee is not None:
            flag.assignee_id = assignee
    elif action is CaseActionKind.ASSIGN:
        flag.assignee_id = assignee
    elif action is CaseActionKind.REOPEN:
        flag.resolved_at = None
        flag.docs_due_on = None
        flag.response_received = False
    flag.last_action_at = now
    await session.flush()

    after: dict[str, Any] = {
        "action": action.value,
        "from_status": from_status.value,
        "to_status": new_status.value,
        "case_action_seq": row.seq,
    }
    if reason_code is not None:
        after["reason_code"] = reason_code
    if docs_kind is not None:
        after["docs_kind"] = docs_kind
    if withdraw_ids:
        after["withdrawn_enrolment_ids"] = [str(i) for i in withdraw_ids]
    if plan is not None:
        after["fields"] = list(plan.values)
    if approval is not None:
        after["approval_version"] = approval["version"]
    if records_assignee:
        after["assignee_id"] = str(assignee) if assignee else None
    if due_date is not None:
        after["due_date"] = due_date.isoformat()
    # the note, names and dates of birth are never written to the audit log
    await audit.record(session, user.id, AuditAction.UPDATE, "flag", flag.id, after=after)
    status.mark(session, named_enrolments(flag))

    messages: list[MailMessage] = []
    if action is CaseActionKind.REQUEST_DOCS:
        messages = await docs_request_messages(session, flag, row, user)
    return ActionResult(flag=flag, action=row, messages=messages, effects=effects, tracker=tracker)


async def settle_effects(session: AsyncSession, result: ActionResult) -> dict[str, Any]:
    """Settle the queued statuses (issuing and revoking attestations as they say) and
    complete the action's effects with the records and attestations that changed."""
    await status.settle(session)
    effects = result.effects or decisions.Effects(case_status=result.flag.status)
    if result.tracker is not None:
        await result.tracker.finish(
            session, effects, decision=result.action.action in transitions.DECISIONS
        )
    return effects.as_dict()


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
    same = transitions.check(user.role, flag.status, CaseActionKind.COLLEGE_RESPONSE)
    now = datetime.now(UTC)
    row = CaseAction(
        flag_id=flag.id,
        actor_id=user.id,
        action=CaseActionKind.COLLEGE_RESPONSE,
        note=note,
        attachments=[],
        at=now,
        from_status=flag.status,
        to_status=same,
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
    status.mark(session, named_enrolments(flag))
    entries = [
        AuditEntry(
            action=AuditAction.UPDATE,
            entity_type="flag",
            entity_id=flag.id,
            actor_id=user.id,
            after={
                "action": CaseActionKind.COLLEGE_RESPONSE.value,
                "from_status": same.value,
                "to_status": same.value,
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
    """The flag's case actions in seq order as CaseHistoryItem dicts (§A3.13, §A4.11). A
    college never sees ASSIGN rows, the notes officers keep to themselves, or the assignee;
    it does see reason codes, document kinds, its corrections and the withdrawn records."""
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
    corrections = await versions.for_case_action(
        session, [r.seq for r, *_ in rows if r.action is CaseActionKind.CORRECT]
    )
    out: list[dict[str, Any]] = []
    for row, actor_id, actor_name, actor_role, assignee_id, assignee_name in rows:
        if college and row.action is CaseActionKind.ASSIGN:
            continue
        hide_note = college and row.action in transitions.NOTE_INTERNAL
        stored = row.correction if isinstance(row.correction, dict) else {}
        correction = None
        if row.action is CaseActionKind.CORRECT:
            version = corrections.get(row.seq)
            correction = {
                "enrolment_id": (version or {}).get("enrolment_id") or stored.get("enrolment_id"),
                "changes": (version or {}).get("changes", []),
            }
        docs = row.action is CaseActionKind.REQUEST_DOCS
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
                "reason_code": None if docs else row.reason_code,
                "docs_kind": row.reason_code if docs else None,
                "approval_version": stored.get("approval_version")
                if row.action is CaseActionKind.UPHOLD
                else None,
                "correction": correction,
                "withdrawn_enrolment_ids": [str(i) for i in row.withdrawn_enrolment_ids or []],
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
        "docs_words": decisions.DOCS_WORDS.get(action.reason_code or "", "documents"),
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
