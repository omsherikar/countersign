"""The evidence rule, row by row of API_CONTRACT §A4.3 (D35, R1 to R4).

`decide` is pure. Each test names the row of the contract's tables it proves: the four
statuses in precedence, every `status_reason` and every `next_step`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.engine.status import RecordContext, decide
from app.models.enums import FlagStatus, FlagType, RecordStatus, Severity
from tests.engines.test_status import (
    ADM,
    CRED,
    CTX,
    DOWN,
    DUE,
    ID,
    NA,
    SEAT,
    STU,
    TODAY,
    C,
    P,
    X,
    case,
    dispute,
    row,
    rows,
)

# ----------------------------------------------------------- the rule, in order


def test_one_contradiction_outranks_four_confirmations() -> None:
    result = decide([row(ID, C), row(SEAT, C), row(ADM, C), row(CRED, C), row(STU, X)], [], CTX)
    assert result.record_status is RecordStatus.UNDER_REVIEW
    assert result.status_reason == "Student is contradicted."


def test_disputed_needs_the_contradicted_student_row_and_an_open_dispute() -> None:
    student_said_no = rows(admission=C, student=X)
    assert decide(student_said_no, [dispute()], CTX).record_status is RecordStatus.DISPUTED
    # the row without its case, or the case without the row, is only under review
    assert decide(student_said_no, [], CTX).record_status is RecordStatus.UNDER_REVIEW
    assert decide(rows(admission=C, student=C), [dispute()], CTX).record_status is (
        RecordStatus.UNDER_REVIEW
    )
    # a decided dispute is not unresolved
    upheld = rows(admission=C, student=X, student_resolved=True)
    assert decide(upheld, [dispute(status=FlagStatus.UPHELD)], CTX).record_status is (
        RecordStatus.COUNTERSIGNED
    )


def test_disputed_reason_and_next_step() -> None:
    result = decide(rows(admission=C, student=X), [dispute()], CTX)
    assert result.status_reason == (
        "The student said they never joined, after signing in with DigiLocker on 18 Aug."
    )
    assert result.next_step == "Waiting for an officer to review the student's dispute."
    assert result.deciding == "ROW:STUDENT"


@pytest.mark.parametrize("severity", list(Severity))
def test_any_unresolved_case_naming_the_record_puts_it_under_review(severity) -> None:
    result = decide(rows(admission=C), [case(FlagType.LATE_REFILL, severity=severity)], CTX)
    assert result.record_status is RecordStatus.UNDER_REVIEW
    assert result.status_reason == "An open Late refill case names this record."
    assert result.next_step == "Waiting for an officer to review the Late refill case."


def test_an_upheld_row_alone_never_countersigns() -> None:
    # the joining record was contradicted and upheld; nothing independent confirms it
    result = decide(rows(admission=X, admission_resolved=True), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == (
        "An officer upheld the claim on 19 Aug, but no evidence independent of the college "
        "confirms the record yet."
    )


def test_self_issued_credits_alone_await_evidence() -> None:
    own = row(CRED, C, independent=False, self_issued=True, supplied_by="ABC, issued by X")
    result = decide([row(ID, C), row(SEAT, C), row(ADM, P), own, row(STU, P)], [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.status_reason == (
        "The only enrolment evidence so far comes from the college itself."
    )


def test_a_review_level_name_upheld_counts_as_identity_confirmed() -> None:
    review = row(ID, P, needs_review=True, resolved=True)
    record = [review, row(SEAT, C), row(ADM, C), row(CRED, DUE), row(STU, P)]
    assert decide(record, [], CTX).record_status is RecordStatus.COUNTERSIGNED
    # not upheld yet: the name waits for the officer
    pending = row(ID, P, needs_review=True)
    assert decide([pending, *record[1:]], [], CTX).record_status is (RecordStatus.AWAITING_EVIDENCE)


@pytest.mark.parametrize(
    ("evidence", "words"),
    [
        ({"admission": C}, "the joining record"),
        ({"student": C}, "the student's own answer"),
        ({"admission": C, "student": C}, "the joining record and the student's own answer"),
    ],
)
def test_countersigned_names_its_independent_rows(evidence, words) -> None:
    result = decide(rows(**evidence), [], CTX)
    assert result.record_status is RecordStatus.COUNTERSIGNED
    assert result.status_reason == (
        f"Identity, seat and {words} confirm the record, and nothing is unresolved."
    )
    assert result.next_step == "None. The evidence is complete."


def test_countersigned_names_the_issuer_of_independent_credits() -> None:
    credits = row(CRED, C, independent=True, issuer_name="Maharashtra State Technical University")
    record = [row(ID, C), row(SEAT, C), row(ADM, P), credits, row(STU, P)]
    ctx = RecordContext(today=TODAY, issuer_name="Maharashtra State Technical University")
    assert decide(record, [], ctx).status_reason == (
        "Identity, seat and credits from Maharashtra State Technical University confirm the "
        "record, and nothing is unresolved."
    )


def test_the_seat_never_counts_as_enrolment_evidence() -> None:
    assert decide(rows(admission=P, credits=DUE, student=P), [], CTX).record_status is (
        RecordStatus.AWAITING_EVIDENCE
    )


@pytest.mark.parametrize("state", [DUE, DOWN, NA, P])
def test_waiting_states_never_contradict(state) -> None:
    result = decide(rows(admission=state), [], CTX)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE


# ------------------------------------------------------------- status_reason


def test_awaiting_reasons_in_order() -> None:
    assert decide(rows(identity=NA), [], CTX).status_reason == "Identity is not confirmed yet."
    with_line = row(ID, NA, source_line="APAAR not linked; alternative route not used yet")
    assert decide([with_line, row(SEAT, C)], [], CTX).status_reason == (
        "Identity is not confirmed yet: APAAR not linked; alternative route not used yet."
    )
    tfw = row(SEAT, P, finding="TFW income certificate not reported")
    assert decide([row(ID, C), tfw], [], CTX).status_reason == (
        "Seat is not confirmed yet: TFW income certificate not reported."
    )
    assert decide(rows(), [], CTX).status_reason == (
        "No enrolment evidence independent of the college yet."
    )
    assert decide([], [], CTX).status_reason == (
        "No enrolment evidence independent of the college yet."
    )


def test_under_review_names_the_first_contradicted_row_in_row_order() -> None:
    record = [
        row(ID, C),
        row(SEAT, X, finding="beyond approved intake"),
        row(ADM, X, finding="not found"),
        row(CRED, DUE),
        row(STU, P),
    ]
    result = decide(record, [], CTX)
    assert result.status_reason == "Seat is contradicted: beyond approved intake."


# ------------------------------------------------------------------ next_step

SENT_AT = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("record", "ctx", "expected"),
    [
        (
            [row(ID, NA)],
            CTX,
            "Waiting for the student to sign in with DigiLocker and claim this record with "
            "its provisional ID.",
        ),
        (
            [row(ID, DOWN)],
            CTX,
            "Waiting for APAAR registry, which did not respond; it is asked again at the next "
            "recheck.",
        ),
        (
            [row(ID, C), row(SEAT, P)],
            CTX,
            "Waiting for the college to report the TFW income certificate.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, P)],
            CTX,
            "Waiting for the joining record from the state admission authority.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, DUE, deadline=date(2026, 9, 30))],
            CTX,
            "Waiting for the joining record; the state admission authority publishes it by 30 Sep.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, DOWN, supplied_by="State admission authority")],
            CTX,
            "Waiting for State admission authority, which did not respond; it is asked again "
            "at the next recheck.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, X, resolved=True), row(CRED, DUE)],
            RecordContext(
                today=TODAY, issuer_name="Maharashtra State Technical University", next_sem=1
            ),
            "Waiting for credits from Maharashtra State Technical University after the semester "
            "1 result.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, X, resolved=True), row(CRED, NA), row(STU, P)],
            RecordContext(today=TODAY, sent_at=SENT_AT),
            "Waiting for evidence independent of the college; the student's notice was sent on "
            "10 Aug.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, X, resolved=True), row(CRED, NA), row(STU, P)],
            CTX,
            "Waiting for evidence independent of the college; no notice has reached the "
            "student yet.",
        ),
        (
            [row(ID, C), row(SEAT, C), row(ADM, X, resolved=True), row(CRED, NA)],
            CTX,
            "Waiting for evidence independent of the college.",
        ),
    ],
)
def test_awaiting_takes_the_next_step_from_the_first_missing_evidence(
    record, ctx, expected
) -> None:
    result = decide(record, [], ctx)
    assert result.record_status is RecordStatus.AWAITING_EVIDENCE
    assert result.next_step == expected


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "status": FlagStatus.DOCS_REQUESTED,
                "docs_kind": "ADMISSION",
                "docs_due_on": date(2026, 8, 29),
            },
            "College asked for admission documents by 29 Aug.",
        ),
        (
            {"status": FlagStatus.DOCS_REQUESTED, "docs_kind": "JOINING"},
            "College asked for the joining report; no reply date set.",
        ),
        (
            {
                "status": FlagStatus.DOCS_REQUESTED,
                "docs_kind": "IDENTITY",
                "docs_due_on": date(2026, 8, 1),
            },
            "College was asked for identity documents by 1 Aug; no response yet.",
        ),
        (
            {
                "status": FlagStatus.DOCS_REQUESTED,
                "response_received": True,
                "last_response_at": datetime(2026, 8, 15, 6, tzinfo=UTC),
            },
            "College responded on 15 Aug; waiting for an officer's decision.",
        ),
        (
            {"status": FlagStatus.ESCALATED, "escalated_at": datetime(2026, 8, 16, 6, tzinfo=UTC)},
            "Escalated to AICTE on 16 Aug; waiting for a decision.",
        ),
    ],
)
def test_a_dispute_follows_its_case(kwargs, expected) -> None:
    result = decide(rows(admission=C, student=X), [dispute(**kwargs)], CTX)
    assert (result.record_status, result.next_step) == (RecordStatus.DISPUTED, expected)


def test_a_row_contradicted_again_after_its_case_was_decided_asks_for_a_reopen() -> None:
    ctx = RecordContext(today=TODAY, decided_case_types=frozenset({FlagType.NOT_IN_JOINING_RECORD}))
    record = rows(admission=X)
    record[2] = row(ADM, X, finding="not found", case_type=FlagType.NOT_IN_JOINING_RECORD)
    result = decide(record, [], ctx)
    assert result.next_step == "Waiting for an officer to reopen the Not in joining record case."
