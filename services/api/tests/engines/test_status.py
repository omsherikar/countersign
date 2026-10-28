"""The evidence rule (D35, R1 to R4; API_CONTRACT §A4.3): `decide` is pure."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.engine import status_text as text
from app.engine.status import CaseFact, RecordContext, RowFact, decide, left_active
from app.models.enums import (
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    RecordStatus,
    Severity,
)

TODAY = date(2026, 8, 20)
CTX = RecordContext(today=TODAY, next_sem=1)
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
    SEAT: ("AICTE approval v1, 2026-27 (Seat Ledger, derived)", False),
    ADM: ("State admission authority", True),
    CRED: ("ABC credits", False),
    STU: ("Student via DigiLocker sign-in", True),
}
UPHELD_AT = datetime(2026, 8, 19, 6, 0, tzinfo=UTC)
REPLIED_AT = datetime(2026, 8, 18, 6, 0, tzinfo=UTC)


def row(row_type: CheckType, state: CheckStatus, *, resolved: bool = False, **kw) -> RowFact:
    supplied_by, independent = SOURCES[row_type]
    return RowFact(
        type=row_type,
        state=state,
        independent=kw.pop("independent", independent),
        resolved=resolved,
        resolved_at=UPHELD_AT if resolved else None,
        supplied_by=kw.pop("supplied_by", supplied_by),
        observed_at=kw.pop("observed_at", REPLIED_AT if row_type is STU else None),
        **kw,
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
    opened: int = 1,
    **kw,
) -> CaseFact:
    return CaseFact(
        id=uuid.uuid4(),
        type=flag_type,
        severity=severity,
        status=status,
        opened_at=datetime(2026, 8, opened, tzinfo=UTC),
        **kw,
    )


def status_of(record_rows, cases=(), ctx=CTX) -> RecordStatus:
    return decide(record_rows, list(cases), ctx).record_status


def dispute(**kw) -> CaseFact:
    return case(FlagType.STUDENT_DENIED, severity=Severity.HIGH, **kw)


# --------------------------------------------------------------------- precedence


def test_one_contradiction_outranks_four_confirmations() -> None:
    result = decide([row(ID, C), row(SEAT, C), row(ADM, X), row(CRED, C), row(STU, C)], [], CTX)
    assert result.record_status is RecordStatus.UNDER_REVIEW
    assert result.status_reason == "Joining record is contradicted."
    assert result.next_step == text.CONTRADICTION_OPEN
    assert result.deciding == "ROW:ADMISSION"


def test_a_contradiction_names_its_finding() -> None:
    found = row(ADM, X, finding="not found")
    result = decide([row(ID, C), row(SEAT, C), found], [], CTX)
    assert result.status_reason == "Joining record is contradicted: not found."


def test_disputed_beats_everything() -> None:
    others = [case(FlagType.EXCESS_ADMISSION, severity=Severity.HIGH), case()]
    result = decide(rows(seat=X, admission=X, student=X), [*others, dispute(opened=5)], CTX)
    assert result.record_status is RecordStatus.DISPUTED
    assert result.status_reason == (
        "The student said they never joined, after signing in with DigiLocker on 18 Aug."
    )
    assert result.next_step == text.DISPUTE_OPEN
    assert result.deciding == "ROW:STUDENT"


def test_a_dispute_needs_both_the_contradicted_row_and_the_open_case() -> None:
    # the student changed the reply to Yes: the dispute is open, the row no longer says No
    changed = decide(rows(admission=C, student=C), [dispute()], CTX)
    assert changed.record_status is RecordStatus.UNDER_REVIEW
    assert changed.status_reason == "An open Student dispute case names this record."
    assert changed.next_step == text.DISPUTE_OPEN
    # a No with no case yet holds the record under review on its row
    no_case = decide(rows(admission=C, student=X), [], CTX)
    assert (no_case.record_status, no_case.status_reason) == (
        RecordStatus.UNDER_REVIEW,
        "Student is contradicted.",
    )


def test_a_dispute_waiting_for_documents_names_them_and_the_date() -> None:
    asked = dispute(
        status=FlagStatus.DOCS_REQUESTED, docs_kind="ADMISSION", docs_due_on=date(2026, 8, 29)
    )
    result = decide(rows(student=X), [asked], CTX)
    assert (result.record_status, result.next_step) == (
        RecordStatus.DISPUTED,
        "College asked for admission documents by 29 Aug.",
    )


@pytest.mark.parametrize("severity", list(Severity))
def test_any_unresolved_case_puts_the_record_under_review(severity) -> None:
    result = decide(rows(admission=C, student=C), [case(severity=severity)], CTX)
    assert result.record_status is RecordStatus.UNDER_REVIEW
    assert result.status_reason == "An open Name or date of birth mismatch case names this record."
    assert result.next_step == (
        "Waiting for an officer to review the Name or date of birth mismatch case."
    )


@pytest.mark.parametrize("flag_type", [FlagType.MISSING_FROM_UPLOAD, FlagType.ANOMALY])
def test_institution_cases_name_no_record(flag_type) -> None:
    assert status_of(rows(admission=C), [case(flag_type)]) is RecordStatus.COUNTERSIGNED


@pytest.mark.parametrize("status", [FlagStatus.UPHELD, FlagStatus.WITHDRAWN, FlagStatus.CORRECTED])
def test_decided_cases_are_not_unresolved(status) -> None:
    assert status_of(rows(admission=C), [case(status=status)]) is RecordStatus.COUNTERSIGNED


def test_the_contradicted_row_takes_the_next_step_from_the_case_that_covers_it() -> None:
    seat_case = case(
        FlagType.EXCESS_ADMISSION,
        FlagStatus.ESCALATED,
        Severity.HIGH,
        opened=9,
        escalated_at=datetime(2026, 8, 12, 6, tzinfo=UTC),
    )
    other = case(FlagType.NAME_MISMATCH, FlagStatus.OPEN, Severity.HIGH, opened=1)
    result = decide(rows(seat=X), [other, seat_case], CTX)
    assert result.record_status is RecordStatus.UNDER_REVIEW
    assert result.status_reason == "Seat is contradicted."
    assert result.next_step == "Escalated to AICTE on 12 Aug; waiting for a decision."
    assert result.deciding == f"CASE:{seat_case.id}"


def test_the_case_a_row_raised_comes_first() -> None:
    raised = case(FlagType.ELIGIBILITY_BREACH, FlagStatus.OPEN, Severity.MEDIUM, opened=9)
    covering = case(FlagType.QUOTA_BREACH, FlagStatus.ESCALATED, Severity.HIGH, opened=1)
    seat = row(SEAT, X, case_type=FlagType.ELIGIBILITY_BREACH)
    result = decide([row(ID, C), seat], [covering, raised], CTX)
    assert (
        result.next_step == "Waiting for an officer to review the Seat category not eligible case."
    )


def test_the_most_severe_then_oldest_case_is_named() -> None:
    low = case(FlagType.NAME_MISMATCH, severity=Severity.LOW, opened=1)
    newer = case(FlagType.LATE_REFILL, severity=Severity.MEDIUM, opened=9)
    older = case(FlagType.DUPLICATE_CROSS_INSTITUTION, severity=Severity.MEDIUM, opened=2)
    result = decide(rows(), [low, newer, older], CTX)
    assert result.status_reason == "An open Duplicate across institutions case names this record."
    assert result.deciding == f"CASE:{older.id}"


def test_a_row_contradicted_again_after_its_case_was_decided_asks_for_a_reopen() -> None:
    ctx = RecordContext(today=TODAY, decided_case_types=frozenset({FlagType.EXCESS_ADMISSION}))
    result = decide(rows(seat=X), [], ctx)
    assert result.next_step == "Waiting for an officer to reopen the Excess admission case."


# ------------------------------------------------------------- decisions (R2)


def test_an_upheld_contradiction_no_longer_blocks() -> None:
    result = decide(rows(admission=C, student=X, student_resolved=True), [], CTX)
    assert result.record_status is RecordStatus.COUNTERSIGNED


def test_an_upheld_contradiction_is_never_evidence() -> None:
    # the officer upheld the claim against the student's No; nothing independent confirms
    result = decide(rows(admission=P, student=X, student_resolved=True), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == (
        "An officer upheld the claim on 19 Aug, but no evidence independent of the college "
        "confirms the record yet."
    )
    assert result.next_step == text.JOINING_RECORD


def test_an_upheld_seat_contradiction_is_not_a_confirmed_seat() -> None:
    result = decide(rows(seat=X, admission=C, seat_resolved=True), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == "Seat is not confirmed yet."
    assert result.next_step == "Waiting for credits from ABC after the semester 1 result."


def test_an_upheld_name_review_confirms_identity() -> None:
    review = row(ID, P, needs_review=True, resolved=True)
    record = [review, row(SEAT, C), row(ADM, C)]
    assert status_of(record) is RecordStatus.COUNTERSIGNED
    waiting = [row(ID, P, needs_review=True), row(SEAT, C), row(ADM, C)]
    assert status_of(waiting) is RecordStatus.AWAITING_EVIDENCE


# --------------------------------------------------------- the evidence rule


def test_identity_seat_and_one_independent_enrolment_row_countersign() -> None:
    result = decide(rows(admission=C), [], CTX)
    assert result.record_status is RecordStatus.COUNTERSIGNED
    assert result.status_reason == (
        "Identity, seat and the joining record confirm the record, and nothing is unresolved."
    )
    assert result.next_step == "None. The evidence is complete."
    assert result.deciding == "EVIDENCE:ADMISSION"


def test_the_student_alone_can_countersign() -> None:
    result = decide(rows(admission=P, credits=DUE, student=C), [], CTX)
    assert result.record_status is RecordStatus.COUNTERSIGNED
    assert "the student's own answer" in result.status_reason


def test_self_issued_credits_alone_never_countersign() -> None:
    result = decide(rows(admission=P, credits=C, student=P), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == text.ONLY_SELF
    assert result.next_step == text.JOINING_RECORD


def test_a_seat_ledger_admission_alone_never_countersigns() -> None:
    ledger = row(ADM, C, independent=False, supplied_by="Seat Ledger")
    record = [row(ID, C), row(SEAT, C), ledger, row(CRED, NA), row(STU, P)]
    result = decide(record, [], CTX)
    assert (result.record_status, result.status_reason) == (
        RecordStatus.AWAITING_EVIDENCE,
        text.ONLY_SELF,
    )
    assert result.next_step == text.STUDENT_NOT_SENT
    sent = RecordContext(today=TODAY, sent_at=datetime(2026, 8, 10, 6, tzinfo=UTC))
    assert decide(record, [], sent).next_step == (
        "Waiting for evidence independent of the college; the student's notice was sent on 10 Aug."
    )


def test_independent_credits_countersign_with_their_issuer() -> None:
    credits = row(CRED, C, independent=True, supplied_by="ABC, issued by MSTU")
    ctx = RecordContext(today=TODAY, issuer_name="MSTU")
    result = decide([row(ID, C), row(SEAT, C), row(ADM, P), credits, row(STU, P)], [], ctx)
    assert result.record_status is RecordStatus.COUNTERSIGNED
    assert result.status_reason == (
        "Identity, seat and credits from MSTU confirm the record, and nothing is unresolved."
    )


@pytest.mark.parametrize("state", [DUE, DOWN, NA, P])
def test_not_yet_due_and_unavailable_never_contradict(state) -> None:
    result = decide(rows(identity=C, seat=C, admission=state, credits=state, student=C), [], CTX)
    assert result.record_status is RecordStatus.COUNTERSIGNED
    unconfirmed = decide(rows(identity=state, admission=state, credits=state), [], CTX)
    assert unconfirmed.record_status is RecordStatus.AWAITING_EVIDENCE


def test_identity_must_be_confirmed() -> None:
    result = decide(rows(identity=NA, admission=C, student=C), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == "Identity is not confirmed yet."
    assert result.next_step == text.IDENTITY_CLAIM
    lined = [row(ID, NA, source_line="APAAR not linked"), row(SEAT, C), row(ADM, C)]
    assert decide(lined, [], CTX).status_reason == (
        "Identity is not confirmed yet: APAAR not linked."
    )


def test_a_source_outage_names_the_source_awaited() -> None:
    result = decide(rows(identity=DOWN, admission=C), [], CTX)
    assert result.next_step == (
        "Waiting for APAAR registry, which did not respond; it is asked again at the next recheck."
    )


def test_the_seat_must_be_confirmed() -> None:
    result = decide(rows(seat=P, admission=C), [], CTX)
    assert (result.record_status, result.status_reason, result.next_step) == (
        RecordStatus.AWAITING_EVIDENCE,
        "Seat is not confirmed yet.",
        text.SEAT_TFW,
    )


def test_the_first_missing_evidence_follows_the_row_order() -> None:
    result = decide(rows(admission=DUE, credits=P, student=P), [], CTX)
    assert result.next_step == text.JOINING_RECORD
    credits = decide(rows(admission=NA, credits=DUE, student=P), [], CTX)
    assert credits.next_step == "Waiting for credits from ABC after the semester 1 result."
    nothing = decide(rows(admission=NA, credits=NA, student=NA), [], CTX)
    assert (nothing.next_step, nothing.deciding) == (text.NO_ROUTE, "RULE")


def test_a_record_with_no_rows_awaits_evidence() -> None:
    result = decide([], [], CTX)
    assert (result.record_status, result.status_reason, result.next_step) == (
        RecordStatus.AWAITING_EVIDENCE,
        text.NO_INDEPENDENT,
        text.NO_ROUTE,
    )


def test_a_missing_row_is_not_evidence() -> None:
    assert status_of([row(ID, C), row(SEAT, C)]) is RecordStatus.AWAITING_EVIDENCE


# ----------------------------------------------------------------- next steps


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"docs_due_on": date(2026, 8, 29)}, "College asked for documents by 29 Aug."),
        ({"docs_due_on": date(2026, 8, 20)}, "College asked for documents by 20 Aug."),
        (
            {"docs_due_on": date(2026, 8, 19)},
            "College was asked for documents by 19 Aug; no response yet.",
        ),
        (
            {
                "docs_due_on": date(2026, 8, 29),
                "response_received": True,
                "last_response_at": datetime(2026, 8, 21, 6, tzinfo=UTC),
            },
            "College responded on 21 Aug; waiting for an officer's decision.",
        ),
        ({}, "College asked for documents; no reply date set."),
        (
            {"docs_kind": "CREDITS", "docs_due_on": date(2026, 8, 29)},
            "College asked for semester results by 29 Aug.",
        ),
    ],
)
def test_a_document_request_gives_the_next_step(kwargs, expected) -> None:
    docs = case(FlagType.LATE_REFILL, FlagStatus.DOCS_REQUESTED, Severity.MEDIUM, **kwargs)
    result = decide(rows(admission=C), [docs], CTX)
    assert (result.record_status, result.next_step) == (RecordStatus.UNDER_REVIEW, expected)


def test_a_date_in_another_year_carries_the_year() -> None:
    late = case(status=FlagStatus.DOCS_REQUESTED, docs_due_on=date(2025, 12, 1))
    result = decide(rows(), [late], CTX)
    assert result.next_step == "College was asked for documents by 1 Dec 2025; no response yet."


def test_dates_are_read_on_the_indian_calendar() -> None:
    # 20 Aug 20:00 UTC is already 21 Aug in India
    assert text.day(datetime(2026, 8, 20, 20, 0, tzinfo=UTC), TODAY) == "21 Aug"


def test_a_record_withdrawn_by_decision_says_so() -> None:
    by_decision = left_active(EnrolmentStatus.WITHDRAWN, date(2026, 8, 20), True, TODAY)
    assert by_decision == (
        None,
        "None. The record was withdrawn by an officer's decision on 20 Aug.",
    )
    assert left_active(EnrolmentStatus.WITHDRAWN, date(2026, 8, 20), False, TODAY) == (None, None)
    assert left_active(EnrolmentStatus.GRADUATED, date(2026, 8, 20), False, TODAY) == (None, None)
