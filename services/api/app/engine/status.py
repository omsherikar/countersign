"""Record status (D35, R1 to R3).

`record_status` is pure: from a record's five rows and the unresolved cases that name it, it
returns one status with the sentence that explains it and the next step. Precedence is
DISPUTED > UNDER_REVIEW > COUNTERSIGNED > AWAITING_EVIDENCE. There is no score: one
contradiction outranks any number of confirmations. An officer's decision resolves a
contradiction but is never evidence, so it never counts towards COUNTERSIGNED (R2).
NOT_YET_DUE and SOURCE_UNAVAILABLE never contradict (R4).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from app.engine.contracts import CHECK_ORDER, UNRESOLVED_FLAG_STATUSES
from app.engine.evidence import FLAG_NAMES, MONTHS
from app.models.enums import (
    CheckStatus,
    CheckType,
    FlagStatus,
    FlagType,
    RecordStatus,
    Severity,
)

# the row labels of the record card (D34)
ROW_LABELS = {
    CheckType.IDENTITY: "Identity",
    CheckType.SEAT: "Seat",
    CheckType.ADMISSION: "Joining record",
    CheckType.STUDYING: "Credits",
    CheckType.STUDENT: "Student",
}
# rows that can show the student is enrolled; one of them, CONFIRMED and independent, is
# needed to countersign
ENROLMENT_ROWS = (CheckType.ADMISSION, CheckType.STUDYING, CheckType.STUDENT)
# the row each case type decides (R1); other cases name records without deciding a row
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
SEVERITY_RANK = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
# due dates are Indian calendar dates
IST = timezone(timedelta(hours=5, minutes=30), "IST")

NOT_CHECKED = "This record has not been checked yet."
WAITING_FOR_CHECKS = "Waiting for the checks to run."
DISPUTED_REASON = "The student said they never joined, and the dispute is not decided yet."
DISPUTE_NEXT = "An officer decides the student dispute."
OPEN_CASE_NEXT = "An officer decides the case."
NO_CASE_NEXT = "An officer reviews the contradiction."
ESCALATED_NEXT = "Escalated to AICTE for a decision."
RESPONDED_NEXT = "The college responded; an officer decides the case."
DOCS_NEXT = "College asked for documents."
DOCS_BY = "College asked for documents by {due}."
DOCS_LATE = "College documents were due by {due}; an officer decides the case."
SELF_ONLY = "Only the college's own records confirm the enrolment so far."
NO_INDEPENDENT = "No independent source has confirmed the enrolment yet."
NOTHING_CAN_CONFIRM = "No source can confirm the enrolment yet."

# what happens next for a row that is not yet the evidence it could be, by type and state
WAITING: dict[tuple[CheckType, CheckStatus], str] = {
    (CheckType.IDENTITY, CheckStatus.PENDING): "Waiting for an officer to review the name match.",
    (CheckType.IDENTITY, CheckStatus.NOT_APPLICABLE): (
        "Waiting for the student to sign in with DigiLocker and claim the record."
    ),
    (CheckType.SEAT, CheckStatus.PENDING): "Waiting for a seat in the approved intake.",
    (CheckType.ADMISSION, CheckStatus.PENDING): (
        "Waiting for the joining record from the state admission authority."
    ),
    (CheckType.ADMISSION, CheckStatus.NOT_YET_DUE): (
        "The joining record is due after the reporting deadline."
    ),
    (CheckType.STUDYING, CheckStatus.PENDING): "Waiting for credits to be recorded in ABC.",
    (CheckType.STUDYING, CheckStatus.NOT_YET_DUE): (
        "Credits are due after the first semester result."
    ),
    (CheckType.STUDENT, CheckStatus.PENDING): (
        "Waiting for the student to confirm through DigiLocker."
    ),
}


@dataclass(frozen=True, slots=True)
class RowFact:
    """One row of the record: its evidence state, provenance and whether a decision
    resolved its contradiction."""

    type: CheckType
    state: CheckStatus
    independent: bool = False
    resolved: bool = False
    supplied_by: str = ""


@dataclass(frozen=True, slots=True)
class CaseFact:
    """One unresolved case naming the record, with its last action's due date."""

    id: uuid.UUID
    type: FlagType
    severity: Severity
    status: FlagStatus
    opened_at: datetime
    due_on: date | None = None
    response_received: bool = False


@dataclass(frozen=True, slots=True)
class StatusResult:
    status: RecordStatus
    reason: str
    next_step: str | None


# ---------------------------------------------------------------------- the rule


def _day(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1]}"


def _ist_today(now: datetime) -> date:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(IST).date()


def case_next_step(case: CaseFact, now: datetime) -> str:
    """What happens next on an unresolved case: its last action decides."""
    if case.status is FlagStatus.ESCALATED:
        return ESCALATED_NEXT
    if case.status is FlagStatus.DOCS_REQUESTED:
        if case.response_received:
            return RESPONDED_NEXT
        if case.due_on is None:
            return DOCS_NEXT
        if case.due_on < _ist_today(now):
            return DOCS_LATE.format(due=_day(case.due_on))
        return DOCS_BY.format(due=_day(case.due_on))
    return OPEN_CASE_NEXT


def _source(row: RowFact) -> str:
    return row.supplied_by or "the source"


def row_next_step(row_type: CheckType, row: RowFact | None) -> str:
    """What the record waits for on a row that is not yet the evidence it could be."""
    label = ROW_LABELS[row_type].lower()
    if row is None:
        return WAITING_FOR_CHECKS
    if row.state is CheckStatus.SOURCE_UNAVAILABLE:
        return f"Waiting for {_source(row)} to respond; a recheck asks again."
    if row.state is CheckStatus.CONTRADICTED:
        return f"Waiting for a source that confirms the {label}."
    if row.state is CheckStatus.CONFIRMED:  # confirmed, but by the college itself
        return f"Waiting for an independent source to confirm the {label}."
    return WAITING.get((row_type, row.state), f"Waiting for the {label} row.")


def _unresolved_reason(row: RowFact) -> str:
    return f"The {ROW_LABELS[row.type].lower()} row contradicts the claim."


def _decided_reason(row: RowFact) -> str:
    return (
        f"The {ROW_LABELS[row.type].lower()} row was contradicted and the case is decided; "
        "a decision is not evidence."
    )


def _not_confirmed_reason(row_type: CheckType, row: RowFact | None) -> str:
    if row is not None and row.state is CheckStatus.CONTRADICTED:
        return _decided_reason(row)
    return f"{ROW_LABELS[row_type]} is not confirmed yet."


def _wait_rank(row: RowFact | None) -> int | None:
    """How soon a row can still become evidence: a source being asked first, then a row not
    yet due, then a decided contradiction; None when it never can (n/a, or confirmed by
    the college itself)."""
    if row is None or row.state in (CheckStatus.PENDING, CheckStatus.SOURCE_UNAVAILABLE):
        return 0
    if row.state is CheckStatus.NOT_YET_DUE:
        return 1
    if row.state is CheckStatus.CONTRADICTED:
        return 2
    return None


def _sorted_cases(cases: Iterable[CaseFact]) -> list[CaseFact]:
    return sorted(
        (c for c in cases if c.status in UNRESOLVED_FLAG_STATUSES),
        key=lambda c: (SEVERITY_RANK[c.severity], c.opened_at, str(c.id)),
    )


def record_status(
    rows: Iterable[RowFact], unresolved_cases: Iterable[CaseFact], *, now: datetime
) -> StatusResult:
    """The record's one status (D35), the row or case that decided it, and the next step."""
    by_type = {r.type: r for r in rows}
    ordered = [by_type[t] for t in CHECK_ORDER if t in by_type]
    cases = _sorted_cases(unresolved_cases)

    # DISPUTED: the student contradicted the claim and that is not decided
    disputes = [c for c in cases if c.type is FlagType.STUDENT_DENIED]
    student = by_type.get(CheckType.STUDENT)
    student_contradicts = (
        student is not None and student.state is CheckStatus.CONTRADICTED and not student.resolved
    )
    if disputes or student_contradicts:
        next_step = case_next_step(disputes[0], now) if disputes else DISPUTE_NEXT
        if next_step == OPEN_CASE_NEXT:
            next_step = DISPUTE_NEXT
        return StatusResult(RecordStatus.DISPUTED, DISPUTED_REASON, next_step)

    # UNDER_REVIEW: a contradiction not yet decided, or any unresolved case
    contradicted = [r for r in ordered if r.state is CheckStatus.CONTRADICTED and not r.resolved]
    if contradicted:
        row = contradicted[0]
        deciding = [c for c in cases if CASE_ROW.get(c.type) is row.type] or cases
        next_step = case_next_step(deciding[0], now) if deciding else NO_CASE_NEXT
        return StatusResult(RecordStatus.UNDER_REVIEW, _unresolved_reason(row), next_step)
    if cases:
        case = cases[0]
        name = FLAG_NAMES.get(case.type, case.type.value)
        return StatusResult(
            RecordStatus.UNDER_REVIEW,
            f"A case names this record: {name}.",
            case_next_step(case, now),
        )

    if not ordered:
        return StatusResult(RecordStatus.AWAITING_EVIDENCE, NOT_CHECKED, WAITING_FOR_CHECKS)

    # COUNTERSIGNED: identity and seat confirmed, and one independent enrolment row
    for row_type in (CheckType.IDENTITY, CheckType.SEAT):
        row = by_type.get(row_type)
        if row is None or row.state is not CheckStatus.CONFIRMED:
            return StatusResult(
                RecordStatus.AWAITING_EVIDENCE,
                _not_confirmed_reason(row_type, row),
                row_next_step(row_type, row),
            )
    enrolment_rows = [(t, by_type.get(t)) for t in ENROLMENT_ROWS]
    evidence = [
        r for _, r in enrolment_rows if r and r.state is CheckStatus.CONFIRMED and r.independent
    ]
    if evidence:
        source = evidence[0].supplied_by or "an independent source"
        reason = f"Identity and seat are confirmed, and {source} confirms the enrolment."
        return StatusResult(RecordStatus.COUNTERSIGNED, reason, None)

    # AWAITING_EVIDENCE: name the first evidence that can still arrive
    self_confirmed = any(r and r.state is CheckStatus.CONFIRMED for _, r in enrolment_rows)
    candidates = sorted(
        ((t, r) for t, r in enrolment_rows if _wait_rank(r) is not None),
        key=lambda pair: _wait_rank(pair[1]),
    )
    reason = SELF_ONLY if self_confirmed else NO_INDEPENDENT
    if not candidates:
        return StatusResult(RecordStatus.AWAITING_EVIDENCE, NOTHING_CAN_CONFIRM, None)
    row_type, row = candidates[0]
    return StatusResult(RecordStatus.AWAITING_EVIDENCE, reason, row_next_step(row_type, row))
