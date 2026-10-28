"""The evidence rule: one status per record (D35, R1 to R3; API_CONTRACT §A4.3; ENGINES §17.2).

`decide` is pure: from a record's five rows, the unresolved cases that name it and a little
context it returns the status, the sentence that explains it and the next step. Precedence is
DISPUTED > UNDER_REVIEW > COUNTERSIGNED > AWAITING_EVIDENCE. There is no score: one
contradiction outranks any number of confirmations. An officer's decision resolves a
contradiction but is never evidence (R2). NOT_YET_DUE and SOURCE_UNAVAILABLE never
contradict (R4).

`refresh` is the only writer of `record_status`, `status_reason`, `next_step` and
`record_status_at`. `mark` and `settle` let a writer of rows, cases or enrolments queue its
records and the transaction owner refresh them before it commits. `mark_resolved` and
`clear_resolved` record an officer's decision on the rows a case covers.

`python -m app.engine.status --refresh-all [--academic-year 2026-27]` computes every
record's status once, after `alembic upgrade` or a seed.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.util import identity_key

from app.core import audit
from app.core.audit import AuditEntry
from app.engine import status_text as text
from app.engine.contracts import CHUNK_SIZE, DECIDED_FLAG_STATUSES, UNRESOLVED_FLAG_STATUSES
from app.models.enums import (
    AuditAction,
    CaseActionKind,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    NoticeDelivery,
    RecordStatus,
    Severity,
)
from app.models.student import Enrolment
from app.models.verification import CaseAction, Check, Flag, Notification

# the deck's row order (API_CONTRACT §A4.1)
ROW_ORDER = (
    CheckType.IDENTITY,
    CheckType.SEAT,
    CheckType.ADMISSION,
    CheckType.STUDYING,
    CheckType.STUDENT,
)
# rows that can show the student is enrolled; one of them, CONFIRMED and independent, is
# needed to countersign
ENROLMENT_ROWS = (CheckType.ADMISSION, CheckType.STUDYING, CheckType.STUDENT)
# the row each case type covers (API_CONTRACT §A4.10); other cases cover no row
CASE_ROW = {
    FlagType.INVALID_APAAR: CheckType.IDENTITY,
    FlagType.NAME_MISMATCH: CheckType.IDENTITY,
    FlagType.EXCESS_ADMISSION: CheckType.SEAT,
    FlagType.QUOTA_BREACH: CheckType.SEAT,
    FlagType.ELIGIBILITY_BREACH: CheckType.SEAT,
    FlagType.NOT_IN_JOINING_RECORD: CheckType.ADMISSION,
    FlagType.NO_ACADEMIC_ACTIVITY: CheckType.STUDYING,
    FlagType.STUDENT_DENIED: CheckType.STUDENT,
}
# cases about an institution, which name no record (API_CONTRACT §A4.3)
NAME_NO_RECORD = frozenset({FlagType.MISSING_FROM_UPLOAD, FlagType.ANOMALY})
SEVERITY_RANK = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
STATUS_DIRTY = "status_dirty"
DISPUTE_REVOCATION = "STUDENT_DISPUTE"


@dataclass(frozen=True, slots=True)
class RowFact:
    """One row of the record, as the rule reads it."""

    type: CheckType
    state: CheckStatus
    independent: bool
    resolved: bool  # checks.resolved is set
    resolved_at: datetime | None = None
    needs_review: bool = False  # detail.needs_review
    basis: str = ""  # detail.basis
    finding: str | None = None
    source_line: str = ""
    case_type: FlagType | None = None  # detail.case_type
    observed_at: datetime | None = None
    supplied_by: str = ""
    self_issued: bool = False  # detail.self_issued (Credits)


@dataclass(frozen=True, slots=True)
class CaseFact:
    """One unresolved case that names the record."""

    id: uuid.UUID
    type: FlagType
    severity: Severity
    status: FlagStatus
    opened_at: datetime
    docs_kind: str | None = None  # of the latest REQUEST_DOCS
    docs_due_on: date | None = None
    response_received: bool = False
    last_response_at: datetime | None = None
    escalated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecordContext:
    """What some sentences need beyond rows and cases."""

    today: date  # IST
    sent_at: datetime | None = None  # latest delivered notice
    issuer_name: str | None = None  # for next_step.credits
    next_sem: int | None = None
    # decided cases naming the record (next_step.case_reopen)
    decided_case_types: frozenset[FlagType] = frozenset()


@dataclass(frozen=True, slots=True)
class StatusResult:
    record_status: RecordStatus
    status_reason: str
    next_step: str | None
    # what decided it, for tests and logs: "ROW:STUDENT", "CASE:<uuid>", "RULE",
    # "EVIDENCE:ADMISSION"
    deciding: str


@dataclass(slots=True)
class StatusTally:
    refreshed: int = 0
    changed: int = 0
    became: dict[str, int] = field(default_factory=dict)
    countersigned: list[uuid.UUID] = field(default_factory=list)
    disputed: list[uuid.UUID] = field(default_factory=list)

    def merge(self, other: StatusTally) -> None:
        self.refreshed += other.refreshed
        self.changed += other.changed
        for status, n in other.became.items():
            self.became[status] = self.became.get(status, 0) + n
        self.countersigned.extend(other.countersigned)
        self.disputed.extend(other.disputed)


# ---------------------------------------------------------------------- the rule


def _unresolved_contradicted(row: RowFact | None) -> bool:
    return row is not None and row.state is CheckStatus.CONTRADICTED and not row.resolved


def identity_confirmed(row: RowFact | None) -> bool:
    """CONFIRMED, or a name an officer upheld after review (PENDING with needs_review)."""
    if row is None:
        return False
    if row.state is CheckStatus.CONFIRMED:
        return True
    return row.state is CheckStatus.PENDING and row.needs_review and row.resolved


def _sorted_cases(cases: Iterable[CaseFact]) -> list[CaseFact]:
    return sorted(
        (c for c in cases if c.status in UNRESOLVED_FLAG_STATUSES and c.type not in NAME_NO_RECORD),
        key=lambda c: (SEVERITY_RANK[c.severity], c.opened_at, str(c.id)),
    )


def case_next_step(case: CaseFact, today: date) -> str:
    """The next step an unresolved case gives: its last action decides."""
    if case.status is FlagStatus.ESCALATED:
        if case.escalated_at is None:
            return text.ESCALATED_UNDATED
        return text.ESCALATED.format(date=text.day(case.escalated_at, today))
    if case.status is FlagStatus.DOCS_REQUESTED:
        if case.response_received:
            if case.last_response_at is None:
                return text.RESPONDED_UNDATED
            return text.RESPONDED.format(date=text.day(case.last_response_at, today))
        words = text.DOCS_WORDS.get(case.docs_kind or "OTHER", text.DOCS_WORDS["OTHER"])
        if case.docs_due_on is None:
            return text.DOCS_REQUESTED_NO_DATE.format(docs_words=words)
        due = text.day(case.docs_due_on, today)
        if case.docs_due_on < today:
            return text.DOCS_OVERDUE.format(docs_words=words, due_date=due)
        return text.DOCS_REQUESTED.format(docs_words=words, due_date=due)
    if case.type is FlagType.STUDENT_DENIED:
        return text.DISPUTE_OPEN
    return text.CASE_OPEN.format(case_name=text.CASE_NAMES.get(case.type, case.type.value))


def _row_case(row: RowFact, cases: list[CaseFact]) -> CaseFact | None:
    """The unresolved case behind a contradicted row: the one the row raised, else one that
    covers the row."""
    if row.case_type is not None:
        for case in cases:
            if case.type is row.case_type:
                return case
    for case in cases:
        if CASE_ROW.get(case.type) is row.type:
            return case
    return None


def _contradiction_next_step(
    row: RowFact, cases: list[CaseFact], ctx: RecordContext
) -> tuple[str, str]:
    """(next step, deciding) for an unresolved-contradicted row."""
    case = _row_case(row, cases) or (cases[0] if cases else None)
    if case is not None:
        return case_next_step(case, ctx.today), f"CASE:{case.id}"
    # its case was decided, then the row was contradicted again
    for case_type in sorted(ctx.decided_case_types, key=lambda t: t.value):
        if case_type is row.case_type or CASE_ROW.get(case_type) is row.type:
            name = text.CASE_NAMES.get(case_type, case_type.value)
            return text.CASE_REOPEN.format(case_name=name), f"ROW:{row.type.value}"
    return text.CONTRADICTION_OPEN, f"ROW:{row.type.value}"


def _waiting_on(row_type: CheckType, row: RowFact | None, ctx: RecordContext) -> str | None:
    """The next step when this row is the first missing evidence, or None to look further."""
    if row is None:
        return None
    state = row.state
    if state is CheckStatus.SOURCE_UNAVAILABLE and row_type is not CheckType.SEAT:
        return text.SOURCE_UNAVAILABLE.format(source_name=row.supplied_by or "the source")
    if row_type is CheckType.IDENTITY and state is CheckStatus.NOT_APPLICABLE:
        return text.IDENTITY_CLAIM
    if row_type is CheckType.SEAT and state is CheckStatus.PENDING:
        return text.SEAT_TFW
    if row_type is CheckType.ADMISSION and state in (CheckStatus.PENDING, CheckStatus.NOT_YET_DUE):
        return text.JOINING_RECORD
    if row_type is CheckType.STUDYING and state in (CheckStatus.PENDING, CheckStatus.NOT_YET_DUE):
        issuer = ctx.issuer_name or "ABC"
        if ctx.next_sem is None:
            return text.CREDITS_UNNUMBERED.format(issuer_name=issuer)
        return text.CREDITS.format(issuer_name=issuer, sem=ctx.next_sem)
    if row_type is CheckType.STUDENT and state is CheckStatus.PENDING:
        if ctx.sent_at is None:
            return text.STUDENT_NOT_SENT
        return text.STUDENT.format(sent_date=text.day(ctx.sent_at, ctx.today))
    return None


def _not_confirmed(row_type: CheckType, row: RowFact | None) -> str:
    label = text.ROW_LABELS[row_type]
    finding = (row.finding or row.source_line) if row is not None else None
    if finding:
        return text.NOT_CONFIRMED.format(check=label, finding=finding)
    return text.NOT_CONFIRMED_PLAIN.format(check=label)


def decide(rows: Sequence[RowFact], cases: Sequence[CaseFact], ctx: RecordContext) -> StatusResult:
    """The record's one status (API_CONTRACT §A4.3). Pure: no database, no clock, no I/O."""
    by_type = {r.type: r for r in rows}
    ordered = [by_type[t] for t in ROW_ORDER if t in by_type]
    unresolved = _sorted_cases(cases)

    # 1 DISPUTED: the student contradicted the claim and that dispute is not decided
    student = by_type.get(CheckType.STUDENT)
    disputes = [c for c in unresolved if c.type is FlagType.STUDENT_DENIED]
    if student is not None and _unresolved_contradicted(student) and disputes:
        reason = (
            text.DISPUTED.format(reply_date=text.day(student.observed_at, ctx.today))
            if student.observed_at
            else text.DISPUTED_UNDATED
        )
        return StatusResult(
            RecordStatus.DISPUTED, reason, case_next_step(disputes[0], ctx.today), "ROW:STUDENT"
        )

    # 2 UNDER_REVIEW: a contradiction not decided, or any unresolved case naming the record
    contradicted = [r for r in ordered if _unresolved_contradicted(r)]
    if contradicted:
        row = contradicted[0]
        label = text.ROW_LABELS[row.type]
        reason = (
            text.UNDER_REVIEW_ROW.format(check=label, finding=row.finding)
            if row.finding
            else text.UNDER_REVIEW_ROW_PLAIN.format(check=label)
        )
        next_step, deciding = _contradiction_next_step(row, unresolved, ctx)
        return StatusResult(RecordStatus.UNDER_REVIEW, reason, next_step, deciding)
    if unresolved:
        case = unresolved[0]
        name = text.CASE_NAMES.get(case.type, case.type.value)
        return StatusResult(
            RecordStatus.UNDER_REVIEW,
            text.UNDER_REVIEW_CASE.format(case_name=name),
            case_next_step(case, ctx.today),
            f"CASE:{case.id}",
        )

    # 3 COUNTERSIGNED: identity and seat confirmed, and independent enrolment evidence
    identity, seat = by_type.get(CheckType.IDENTITY), by_type.get(CheckType.SEAT)
    identity_ok = identity_confirmed(identity)
    seat_ok = seat is not None and seat.state is CheckStatus.CONFIRMED
    enrolment_rows = [(t, by_type.get(t)) for t in ENROLMENT_ROWS]
    evidence = [
        r for _, r in enrolment_rows if r and r.state is CheckStatus.CONFIRMED and r.independent
    ]
    if identity_ok and seat_ok and evidence:
        words = text.join_words([text.evidence_words(r.type, ctx.issuer_name) for r in evidence])
        return StatusResult(
            RecordStatus.COUNTERSIGNED,
            text.COUNTERSIGNED.format(independent_rows=words),
            text.NONE,
            f"EVIDENCE:{evidence[0].type.value}",
        )

    # 4 AWAITING_EVIDENCE: the reason, then the first missing evidence
    upheld = [r.resolved_at for r in ordered if r.resolved and r.resolved_at]
    if ordered and not identity_ok:
        reason = _not_confirmed(CheckType.IDENTITY, identity)
    elif ordered and not seat_ok:
        reason = _not_confirmed(CheckType.SEAT, seat)
    elif upheld:
        reason = text.UPHELD.format(date=text.day(max(upheld), ctx.today))
    elif any(r and r.state is CheckStatus.CONFIRMED for _, r in enrolment_rows):
        reason = text.ONLY_SELF
    else:
        reason = text.NO_INDEPENDENT
    steps: list[tuple[CheckType, RowFact | None]] = []
    if not identity_ok:
        steps.append((CheckType.IDENTITY, identity))
    if not seat_ok:
        steps.append((CheckType.SEAT, seat))
    # NOT_APPLICABLE rows, and rows the college confirmed for itself, can never be evidence
    steps.extend(
        (t, r)
        for t, r in enrolment_rows
        if r is None or r.state not in (CheckStatus.CONFIRMED, CheckStatus.NOT_APPLICABLE)
    )
    for row_type, row in steps:
        next_step = _waiting_on(row_type, row, ctx)
        if next_step is not None:
            return StatusResult(
                RecordStatus.AWAITING_EVIDENCE, reason, next_step, f"EVIDENCE:{row_type.value}"
            )
    return StatusResult(RecordStatus.AWAITING_EVIDENCE, reason, text.NO_ROUTE, "RULE")


def left_active(
    status: EnrolmentStatus, status_date: date, by_decision: bool, today: date
) -> tuple[str | None, str | None]:
    """(status_reason, next_step) for an enrolment that is not ACTIVE."""
    if status is EnrolmentStatus.WITHDRAWN and by_decision:
        return None, text.WITHDRAWN.format(date=text.day(status_date, today))
    return None, None


# --------------------------------------------------------------------- the writer


def _chunks[T](items: Sequence[T], size: int = CHUNK_SIZE) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def row_fact(
    check_type: CheckType,
    state: CheckStatus,
    independent: bool,
    resolved: dict[str, Any] | None,
    detail: dict[str, Any] | None,
    observed_at: datetime | None,
    supplied_by: str,
) -> RowFact:
    """A RowFact from a stored check row."""
    detail = detail or {}
    case_type = detail.get("case_type")
    return RowFact(
        type=check_type,
        state=state,
        independent=independent,
        resolved=resolved is not None,
        resolved_at=_as_datetime((resolved or {}).get("at")),
        needs_review=bool(detail.get("needs_review")),
        basis=str(detail.get("basis") or ""),
        finding=detail.get("finding") or None,
        source_line=str(detail.get("source_line") or ""),
        case_type=FlagType(case_type) if case_type in FlagType.__members__ else None,
        observed_at=observed_at,
        supplied_by=supplied_by,
        self_issued=bool(detail.get("self_issued")),
    )


def _uuid_array(ids: Sequence[uuid.UUID]) -> Any:
    return literal(list(ids), type_=ARRAY(UUID(as_uuid=True)))


async def _cases(
    session: AsyncSession, owners: dict[uuid.UUID, uuid.UUID]
) -> tuple[dict[uuid.UUID, list[CaseFact]], dict[uuid.UUID, set[FlagType]]]:
    """The unresolved cases naming each record, and the types of the decided ones. A case
    names a record when it is the case's own enrolment, or a related enrolment at the
    case's institution (API_CONTRACT §A4.3)."""
    ids = list(owners)
    flags = (
        await session.execute(
            select(
                Flag.id,
                Flag.type,
                Flag.severity,
                Flag.status,
                Flag.opened_at,
                Flag.docs_due_on,
                Flag.response_received,
                Flag.institution_id,
                Flag.enrolment_id,
                Flag.related_enrolment_ids,
            ).where(
                Flag.type.not_in(NAME_NO_RECORD),
                or_(
                    Flag.enrolment_id.in_(ids),
                    Flag.related_enrolment_ids.op("&&")(_uuid_array(ids)),
                ),
            )
        )
    ).all()
    open_ids = [f.id for f in flags if f.status in UNRESOLVED_FLAG_STATUSES]
    last: dict[uuid.UUID, dict[CaseActionKind, datetime]] = {}
    if open_ids:
        for flag_id, action, at in (
            await session.execute(
                select(CaseAction.flag_id, CaseAction.action, func.max(CaseAction.at))
                .where(
                    CaseAction.flag_id.in_(open_ids),
                    CaseAction.action.in_(
                        [CaseActionKind.COLLEGE_RESPONSE, CaseActionKind.ESCALATE]
                    ),
                )
                .group_by(CaseAction.flag_id, CaseAction.action)
            )
        ).all():
            last.setdefault(flag_id, {})[action] = at
    unresolved: dict[uuid.UUID, list[CaseFact]] = {}
    decided: dict[uuid.UUID, set[FlagType]] = {}
    for f in flags:
        named = {f.enrolment_id} & owners.keys() if f.enrolment_id else set()
        named |= {i for i in f.related_enrolment_ids if owners.get(i) == f.institution_id}
        if f.status in DECIDED_FLAG_STATUSES:
            for enrolment_id in named:
                decided.setdefault(enrolment_id, set()).add(f.type)
            continue
        actions = last.get(f.id, {})
        fact = CaseFact(
            id=f.id,
            type=f.type,
            severity=f.severity,
            status=f.status,
            opened_at=f.opened_at,
            docs_due_on=f.docs_due_on,
            response_received=f.response_received,
            last_response_at=actions.get(CaseActionKind.COLLEGE_RESPONSE),
            escalated_at=actions.get(CaseActionKind.ESCALATE),
        )
        for enrolment_id in named:
            unresolved.setdefault(enrolment_id, []).append(fact)
    return unresolved, decided


def _issuer(rows: Sequence[RowFact]) -> str | None:
    """The issuer named on the Credits row ("ABC, issued by ..."), if any."""
    for row in rows:
        if row.type is CheckType.STUDYING and row.supplied_by.startswith("ABC, issued by "):
            return row.supplied_by.removeprefix("ABC, issued by ")
    return None


def _next_sem(rows: Sequence[RowFact], year_of_study: int, awaiting: Any) -> int | None:
    """The next semester whose credits are expected: the one the Credits row waits for, else
    the first of the current year of study."""
    if not any(row.type is CheckType.STUDYING for row in rows):
        return None
    if isinstance(awaiting, int):
        return awaiting
    return 2 * (year_of_study - 1) + 1


async def refresh(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    *,
    actor_id: uuid.UUID | None = None,
    issue: bool = True,
    audit_sink: list[AuditEntry] | None = None,
    now: datetime | None = None,
) -> StatusTally:
    """Recompute and write the status of the records among the ids (ENGINES §17.2).

    Writes record_status, status_reason, next_step and record_status_at (when the status
    changes), audits each change of status, revokes the attestations of a record that
    becomes DISPUTED and, with `issue`, issues for every COUNTERSIGNED record. A record that
    is not ACTIVE keeps its last status and gets the reason and next step of `left_active`.
    Flushes, never commits.
    """
    from app import credentials

    now = now or datetime.now(UTC)
    today = text.ist_date(now)
    tally = StatusTally()
    entries: list[AuditEntry] = []
    for part in _chunks(list(dict.fromkeys(enrolment_ids))):
        records = (
            await session.execute(
                select(
                    Enrolment.id,
                    Enrolment.institution_id,
                    Enrolment.status,
                    Enrolment.status_date,
                    Enrolment.year_of_study,
                    Enrolment.record_status,
                    Enrolment.status_reason,
                    Enrolment.next_step,
                    Enrolment.record_status_at,
                ).where(Enrolment.id.in_(part))
            )
        ).all()
        if not records:
            continue
        owners = {r.id: r.institution_id for r in records}
        rows: dict[uuid.UUID, list[RowFact]] = {}
        awaiting: dict[uuid.UUID, Any] = {}
        for enrolment_id, *values in (
            await session.execute(
                select(
                    Check.enrolment_id,
                    Check.type,
                    Check.status,
                    Check.independent,
                    Check.resolved,
                    Check.detail,
                    Check.observed_at,
                    Check.supplied_by,
                ).where(Check.enrolment_id.in_(list(owners)))
            )
        ).all():
            rows.setdefault(enrolment_id, []).append(row_fact(*values))
            if values[0] is CheckType.STUDYING:
                awaiting[enrolment_id] = (values[4] or {}).get("awaiting_semester")
        unresolved, decided = await _cases(session, owners)
        sent = dict(
            (
                await session.execute(
                    select(Notification.enrolment_id, func.max(Notification.sent_at))
                    .where(
                        Notification.enrolment_id.in_(list(owners)),
                        Notification.delivery_status == NoticeDelivery.SENT,
                    )
                    .group_by(Notification.enrolment_id)
                )
            ).all()
        )
        inactive = [r.id for r in records if r.status is not EnrolmentStatus.ACTIVE]
        by_decision: set[uuid.UUID] = set()
        if inactive:
            by_decision = set(
                (
                    await session.execute(
                        select(func.unnest(CaseAction.withdrawn_enrolment_ids)).where(
                            CaseAction.withdrawn_enrolment_ids.op("&&")(_uuid_array(inactive))
                        )
                    )
                ).scalars()
            )

        updates: list[dict[str, Any]] = []
        for r in records:
            tally.refreshed += 1
            if r.status is not EnrolmentStatus.ACTIVE:
                reason, next_step = left_active(r.status, r.status_date, r.id in by_decision, today)
                if (reason, next_step) != (r.status_reason, r.next_step):
                    updates.append({"id": r.id, "status_reason": reason, "next_step": next_step})
                continue
            facts = rows.get(r.id, [])
            ctx = RecordContext(
                today=today,
                sent_at=sent.get(r.id),
                issuer_name=_issuer(facts),
                next_sem=_next_sem(facts, r.year_of_study, awaiting.get(r.id)),
                decided_case_types=frozenset(decided.get(r.id, ())),
            )
            result = decide(facts, unresolved.get(r.id, []), ctx)
            if result.record_status is RecordStatus.COUNTERSIGNED:
                tally.countersigned.append(r.id)
            moved = result.record_status is not r.record_status
            same_words = (result.status_reason, result.next_step) == (r.status_reason, r.next_step)
            if not moved and same_words and r.record_status_at is not None:
                continue
            updates.append(
                {
                    "id": r.id,
                    "record_status": result.record_status,
                    "status_reason": result.status_reason,
                    "next_step": result.next_step,
                    "record_status_at": now
                    if moved or r.record_status_at is None
                    else r.record_status_at,
                }
            )
            if not moved:
                continue
            tally.changed += 1
            tally.became[result.record_status.value] = (
                tally.became.get(result.record_status.value, 0) + 1
            )
            entries.append(
                AuditEntry(
                    action=AuditAction.UPDATE,
                    entity_type="enrolment",
                    entity_id=r.id,
                    actor_id=actor_id,
                    before={"record_status": r.record_status.value},
                    after={"record_status": result.record_status.value},
                )
            )
            if result.record_status is RecordStatus.DISPUTED:
                tally.disputed.append(r.id)
        if updates:
            await session.execute(update(Enrolment), updates)
            _sync_loaded(session, updates)
    # a record that becomes DISPUTED loses its attestation (R6)
    for enrolment_id in tally.disputed:
        await credentials.revoke_for_enrolment(
            session, enrolment_id, DISPUTE_REVOCATION, None, audit_sink=entries
        )
    if audit_sink is not None:
        audit_sink.extend(entries)
    elif entries:
        await audit.record_many(session, entries)
    if issue:
        for enrolment_id in tally.countersigned:
            await credentials.issue_if_eligible(session, enrolment_id)
    return tally


def _sync_loaded(session: AsyncSession, updates: list[dict[str, Any]]) -> None:
    """Enrolments already loaded in the session see the written values."""
    for values in updates:
        loaded = session.identity_map.get(identity_key(Enrolment, values["id"]))
        if loaded is None:
            continue
        for key, value in values.items():
            if key != "id":
                set_committed_value(loaded, key, value)


def mark(session: AsyncSession, enrolment_ids: Iterable[uuid.UUID | None]) -> None:
    """Queue records for `settle`; cheap, synchronous, safe to call many times."""
    dirty: set[uuid.UUID] = session.info.setdefault(STATUS_DIRTY, set())
    dirty.update(i for i in enrolment_ids if i is not None)


async def settle(session: AsyncSession, *, issue: bool = True) -> StatusTally:
    """Refresh every queued record, repeating until nothing is queued. The actor is the
    request's user (`session.info["actor_id"]`), else the system."""
    tally = StatusTally()
    while dirty := session.info.pop(STATUS_DIRTY, None):
        tally.merge(
            await refresh(
                session,
                sorted(dirty, key=str),
                actor_id=session.info.get("actor_id"),
                issue=issue,
            )
        )
    return tally


async def commit(session: AsyncSession, *, issue: bool = True) -> None:
    """Settle, then commit."""
    await settle(session, issue=issue)
    await session.commit()


# ---------------------------------------------------------------- decisions (R2)


def named_enrolments(flag: Flag) -> list[uuid.UUID]:
    """The enrolments a case names: its own and the related ones."""
    return [i for i in dict.fromkeys([flag.enrolment_id, *flag.related_enrolment_ids]) if i]


async def mark_resolved(
    session: AsyncSession,
    flag: Flag,
    outcome: FlagStatus,
    *,
    actor_id: uuid.UUID,
    at: datetime,
    case_action_seq: int,
    reason_code: str | None = None,
) -> None:
    """An officer upheld the case (API_CONTRACT §A4.10): on each ACTIVE record it names, the
    row it covers, when CONTRADICTED (or PENDING with needs_review for NAME_MISMATCH), keeps
    its state and carries {outcome, case_id, case_action_seq, by_id, at, reason_code}, and no
    longer counts as unresolved (R2)."""
    row_type = CASE_ROW.get(flag.type)
    named = named_enrolments(flag)
    if row_type is None or not named:
        return
    resolved = {
        "outcome": outcome.value,
        "case_id": str(flag.id),
        "case_action_seq": case_action_seq,
        "by_id": str(actor_id),
        "at": at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "reason_code": reason_code,
    }
    states = [Check.status == CheckStatus.CONTRADICTED]
    if flag.type is FlagType.NAME_MISMATCH:
        states.append(
            and_(
                Check.status == CheckStatus.PENDING,
                Check.detail["needs_review"].as_boolean().is_(True),
            )
        )
    await session.execute(
        update(Check)
        .where(
            Check.enrolment_id.in_(named),
            Check.type == row_type,
            or_(*states),
            Check.enrolment_id.in_(
                select(Enrolment.id).where(
                    Enrolment.institution_id == flag.institution_id,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
            ),
        )
        .values(resolved=resolved)
        .execution_options(synchronize_session=False)
    )


async def clear_resolved(session: AsyncSession, flag: Flag) -> None:
    """The case was reopened: the rows its decision resolved count as unresolved again."""
    named = named_enrolments(flag)
    if not named:
        return
    await session.execute(
        update(Check)
        .where(
            Check.enrolment_id.in_(named),
            Check.resolved["case_id"].astext == str(flag.id),
        )
        .values(resolved=None)
        .execution_options(synchronize_session=False)
    )


# ------------------------------------------------------------------------- CLI


async def refresh_all(academic_year: str | None = None) -> StatusTally:
    """Every record's status, one committed transaction per chunk of records."""
    from app.db.session import session_factory

    factory = session_factory()
    async with factory() as session:
        stmt = select(Enrolment.id).order_by(Enrolment.id)
        if academic_year:
            stmt = stmt.where(Enrolment.academic_year == academic_year)
        ids = list((await session.execute(stmt)).scalars())
    tally = StatusTally()
    for part in _chunks(ids):
        async with factory() as session:
            tally.merge(await refresh(session, part, issue=False))
            await session.commit()
    return tally


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.engine.status",
        description="Compute the status of every record (D35) and store it.",
    )
    parser.add_argument("--refresh-all", action="store_true", required=True)
    parser.add_argument("--academic-year", default=None, help="only this roll year, e.g. 2026-27")
    args = parser.parse_args(argv)
    from app.db.session import dispose_engine

    async def run() -> StatusTally:
        try:
            return await refresh_all(args.academic_year)
        finally:
            await dispose_engine()

    tally = asyncio.run(run())
    became = ", ".join(f"{n} {status}" for status, n in sorted(tally.became.items())) or "none"
    print(f"refreshed {tally.refreshed} records; {tally.changed} changed status ({became})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
