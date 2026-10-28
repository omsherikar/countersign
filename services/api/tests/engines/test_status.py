"""The record status rule (D35, R1 to R4): pure, from rows and unresolved cases."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.engine.status import (
    DISPUTE_NEXT,
    DISPUTED_REASON,
    ESCALATED_NEXT,
    NO_CASE_NEXT,
    NO_INDEPENDENT,
    NOT_CHECKED,
    OPEN_CASE_NEXT,
    RESPONDED_NEXT,
    SELF_ONLY,
    WAITING_FOR_CHECKS,
    CaseFact,
    RowFact,
    record_status,
)
from app.models.enums import CheckStatus, CheckType, FlagStatus, FlagType, RecordStatus, Severity

NOW = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)
C, X, P = CheckStatus.CONFIRMED, CheckStatus.CONTRADICTED, CheckStatus.PENDING
DUE, NA, DOWN = CheckStatus.NOT_YET_DUE, CheckStatus.NOT_APPLICABLE, CheckStatus.SOURCE_UNAVAILABLE
ID, SEAT, ADM, CRED, STU = (
    CheckType.IDENTITY,
    CheckType.SEAT,
    CheckType.ADMISSION,
    CheckType.STUDYING,
    CheckType.STUDENT,
)
SOURCES = {
    ID: ("APAAR registry", True),
    SEAT: ("AICTE approval 2026-27 (Seat Ledger, derived)", False),
    ADM: ("Counselling list", True),
    CRED: ("ABC credits", False),
    STU: ("Student reply", True),
}


def row(row_type: CheckType, state: CheckStatus, *, resolved: bool = False, **kw) -> RowFact:
    supplied_by, independent = SOURCES[row_type]
    return RowFact(
        row_type,
        state,
        independent=kw.get("independent", independent),
        resolved=resolved,
        supplied_by=supplied_by,
    )


def rows(identity=C, seat=C, admission=P, credits=DUE, student=P, **resolved) -> list[RowFact]:
    states = {ID: identity, SEAT: seat, ADM: admission, CRED: credits, STU: student}
    names = {"identity": ID, "seat": SEAT, "admission": ADM, "credits": CRED, "student": STU}
    done = {names[k.removesuffix("_resolved")] for k, v in resolved.items() if v}
    return [row(t, s, resolved=t in done) for t, s in states.items() if s is not None]


def case(
    flag_type: FlagType = FlagType.NAME_MISMATCH,
    status: FlagStatus = FlagStatus.OPEN,
    severity: Severity = Severity.LOW,
    *,
    due_on: date | None = None,
    response_received: bool = False,
    opened: int = 1,
) -> CaseFact:
    return CaseFact(
        id=uuid.uuid4(),
        type=flag_type,
        severity=severity,
        status=status,
        opened_at=datetime(2026, 8, opened, tzinfo=UTC),
        due_on=due_on,
        response_received=response_received,
    )


def status_of(record_rows, cases=()) -> RecordStatus:
    return record_status(record_rows, cases, now=NOW).status


# --------------------------------------------------------------------- precedence


def test_one_contradiction_outranks_four_confirmations() -> None:
    result = record_status(
        [row(ID, C), row(SEAT, C), row(ADM, X), row(CRED, C), row(STU, C)], [], now=NOW
    )
    assert result.status is RecordStatus.UNDER_REVIEW
    assert result.reason == "The joining record row contradicts the claim."
    assert result.next_step == NO_CASE_NEXT


def test_disputed_beats_everything() -> None:
    dispute = case(FlagType.STUDENT_DENIED, severity=Severity.HIGH, opened=5)
    others = [case(FlagType.EXCESS_ADMISSION, severity=Severity.HIGH, opened=1), case()]
    result = record_status(rows(seat=X, admission=X, student=X), [*others, dispute], now=NOW)
    assert result.status is RecordStatus.DISPUTED
    assert result.reason == DISPUTED_REASON
    assert result.next_step == DISPUTE_NEXT


def test_an_open_dispute_alone_makes_the_record_disputed() -> None:
    # the student changed the reply to Yes, but the dispute is not decided
    dispute = case(FlagType.STUDENT_DENIED, severity=Severity.HIGH)
    assert status_of(rows(admission=C, student=C), [dispute]) is RecordStatus.DISPUTED


def test_a_student_no_without_a_case_yet_is_still_disputed() -> None:
    assert status_of(rows(admission=C, student=X)) is RecordStatus.DISPUTED


def test_a_dispute_waiting_for_documents_names_the_due_date() -> None:
    dispute = case(
        FlagType.STUDENT_DENIED, FlagStatus.DOCS_REQUESTED, Severity.HIGH, due_on=date(2026, 8, 29)
    )
    result = record_status(rows(student=X), [dispute], now=NOW)
    assert (result.status, result.next_step) == (
        RecordStatus.DISPUTED,
        "College asked for documents by 29 Aug.",
    )


@pytest.mark.parametrize("severity", list(Severity))
def test_any_unresolved_case_puts_the_record_under_review(severity) -> None:
    result = record_status(rows(admission=C, student=C), [case(severity=severity)], now=NOW)
    assert result.status is RecordStatus.UNDER_REVIEW
    assert result.reason == "A case names this record: Name or date of birth mismatch."
    assert result.next_step == OPEN_CASE_NEXT


@pytest.mark.parametrize("status", [FlagStatus.UPHELD, FlagStatus.WITHDRAWN, FlagStatus.CORRECTED])
def test_decided_cases_are_not_unresolved(status) -> None:
    assert status_of(rows(admission=C), [case(status=status)]) is RecordStatus.COUNTERSIGNED


def test_the_contradicted_row_takes_the_next_step_from_the_case_that_decides_it() -> None:
    seat_case = case(FlagType.EXCESS_ADMISSION, FlagStatus.ESCALATED, Severity.HIGH, opened=9)
    other = case(FlagType.NAME_MISMATCH, FlagStatus.DOCS_REQUESTED, Severity.HIGH, opened=1)
    result = record_status(rows(seat=X), [other, seat_case], now=NOW)
    assert result.status is RecordStatus.UNDER_REVIEW
    assert result.reason == "The seat row contradicts the claim."
    assert result.next_step == ESCALATED_NEXT


def test_the_most_severe_then_oldest_case_is_named() -> None:
    low = case(FlagType.NAME_MISMATCH, severity=Severity.LOW, opened=1)
    newer = case(FlagType.LATE_REFILL, severity=Severity.MEDIUM, opened=9)
    older = case(FlagType.DUPLICATE_CROSS_INSTITUTION, severity=Severity.MEDIUM, opened=2)
    result = record_status(rows(), [low, newer, older], now=NOW)
    assert result.reason == "A case names this record: Duplicate across institutions."


# ------------------------------------------------------------- decisions (R2)


def test_an_upheld_contradiction_no_longer_blocks() -> None:
    result = record_status(rows(admission=C, student=X, student_resolved=True), [], now=NOW)
    assert result.status is RecordStatus.COUNTERSIGNED


def test_an_upheld_contradiction_is_never_evidence() -> None:
    # the officer upheld the claim against the student's No; nothing independent confirms
    result = record_status(rows(admission=P, student=X, student_resolved=True), [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.reason == NO_INDEPENDENT
    assert result.next_step == (
        "Waiting for the joining record from the state admission authority."
    )


def test_an_upheld_seat_contradiction_is_not_a_confirmed_seat() -> None:
    result = record_status(rows(seat=X, admission=C, seat_resolved=True), [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.reason == (
        "The seat row was contradicted and the case is decided; a decision is not evidence."
    )
    assert result.next_step == "Waiting for a source that confirms the seat."


def test_only_a_decided_contradiction_left_still_says_what_could_confirm() -> None:
    result = record_status(
        rows(admission=X, credits=NA, student=X, admission_resolved=True, student_resolved=True),
        [],
        now=NOW,
    )
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.next_step == "Waiting for a source that confirms the joining record."


# --------------------------------------------------------- the evidence rule


def test_identity_seat_and_one_independent_enrolment_row_countersign() -> None:
    result = record_status(rows(admission=C), [], now=NOW)
    assert result.status is RecordStatus.COUNTERSIGNED
    assert result.reason == (
        "Identity and seat are confirmed, and Counselling list confirms the enrolment."
    )
    assert result.next_step is None


def test_the_student_alone_can_countersign() -> None:
    assert status_of(rows(admission=P, credits=DUE, student=C)) is RecordStatus.COUNTERSIGNED


def test_self_issued_credits_alone_never_countersign() -> None:
    result = record_status(rows(admission=P, credits=C, student=P), [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.reason == SELF_ONLY
    assert result.next_step == (
        "Waiting for the joining record from the state admission authority."
    )


def test_a_seat_ledger_admission_alone_never_countersigns() -> None:
    ledger = RowFact(ADM, C, independent=False, supplied_by="AICTE approval (Seat Ledger)")
    result = record_status(
        [row(ID, C), row(SEAT, C), ledger, row(CRED, DUE), row(STU, P)], [], now=NOW
    )
    assert (result.status, result.reason) == (RecordStatus.AWAITING_EVIDENCE, SELF_ONLY)
    assert result.next_step == "Waiting for the student to confirm through DigiLocker."


def test_independent_credits_countersign() -> None:
    credits = RowFact(CRED, C, independent=True, supplied_by="ABC (affiliating university)")
    result = record_status(
        [row(ID, C), row(SEAT, C), row(ADM, P), credits, row(STU, P)], [], now=NOW
    )
    assert result.status is RecordStatus.COUNTERSIGNED
    assert "ABC (affiliating university)" in result.reason


@pytest.mark.parametrize("state", [DUE, DOWN, NA, P])
def test_not_yet_due_and_unavailable_never_contradict(state) -> None:
    result = record_status(
        rows(identity=C, seat=C, admission=state, credits=state, student=C), [], now=NOW
    )
    assert result.status is RecordStatus.COUNTERSIGNED
    unconfirmed = record_status(rows(identity=state, admission=state, credits=state), [], now=NOW)
    assert unconfirmed.status is RecordStatus.AWAITING_EVIDENCE


def test_identity_must_be_confirmed() -> None:
    result = record_status(rows(identity=NA, admission=C, student=C), [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.reason == "Identity is not confirmed yet."
    assert result.next_step == (
        "Waiting for the student to sign in with DigiLocker and claim the record."
    )


def test_a_source_outage_says_which_source_is_awaited() -> None:
    result = record_status(rows(identity=DOWN, admission=C), [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.next_step == "Waiting for APAAR registry to respond; a recheck asks again."


def test_the_seat_must_be_confirmed() -> None:
    result = record_status(rows(seat=P, admission=C), [], now=NOW)
    assert (result.status, result.reason) == (
        RecordStatus.AWAITING_EVIDENCE,
        "Seat is not confirmed yet.",
    )


def test_rows_not_yet_due_wait_behind_rows_being_asked() -> None:
    result = record_status(rows(admission=DUE, credits=DUE, student=P), [], now=NOW)
    assert result.next_step == "Waiting for the student to confirm through DigiLocker."
    only_due = record_status(rows(admission=NA, credits=DUE, student=NA), [], now=NOW)
    assert only_due.next_step == "Credits are due after the first semester result."


def test_a_record_with_no_rows_waits_for_the_checks() -> None:
    result = record_status([], [], now=NOW)
    assert (result.status, result.reason, result.next_step) == (
        RecordStatus.AWAITING_EVIDENCE,
        NOT_CHECKED,
        WAITING_FOR_CHECKS,
    )


def test_a_missing_row_is_not_evidence() -> None:
    result = record_status([row(ID, C), row(SEAT, C)], [], now=NOW)
    assert result.status is RecordStatus.AWAITING_EVIDENCE
    assert result.next_step == WAITING_FOR_CHECKS


# ----------------------------------------------------------------- next steps


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"due_on": date(2026, 8, 29)}, "College asked for documents by 29 Aug."),
        ({"due_on": date(2026, 8, 20)}, "College asked for documents by 20 Aug."),
        (
            {"due_on": date(2026, 8, 19)},
            "College documents were due by 19 Aug; an officer decides the case.",
        ),
        ({"due_on": date(2026, 8, 29), "response_received": True}, RESPONDED_NEXT),
        ({}, "College asked for documents."),
    ],
)
def test_a_document_request_gives_the_next_step(kwargs, expected) -> None:
    docs = case(FlagType.LATE_REFILL, FlagStatus.DOCS_REQUESTED, Severity.MEDIUM, **kwargs)
    result = record_status(rows(admission=C), [docs], now=NOW)
    assert (result.status, result.next_step) == (RecordStatus.UNDER_REVIEW, expected)


def test_the_due_date_is_read_on_the_indian_calendar() -> None:
    # 20 Aug 20:00 UTC is already 21 Aug in India: a 20 Aug due date has passed
    late = datetime(2026, 8, 20, 20, 0, tzinfo=UTC)
    docs = case(status=FlagStatus.DOCS_REQUESTED, due_on=date(2026, 8, 20))
    result = record_status(rows(), [docs], now=late)
    assert result.next_step == "College documents were due by 20 Aug; an officer decides the case."
