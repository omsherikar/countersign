"""The transition table, cell by cell, against API_CONTRACT §A4.8 written out again here."""

from __future__ import annotations

import pytest

from app.cases import transitions
from app.core.errors import ApiError
from app.models.enums import CaseActionKind, FlagStatus, UserRole

A, R, C = UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION
OPEN, DOCS, ESC, UPHELD, WITHDRAWN, CORRECTED = (
    FlagStatus.OPEN,
    FlagStatus.DOCS_REQUESTED,
    FlagStatus.ESCALATED,
    FlagStatus.UPHELD,
    FlagStatus.WITHDRAWN,
    FlagStatus.CORRECTED,
)
ACTIONS = [
    "UPHOLD",
    "CORRECT",
    "WITHDRAW",
    "REQUEST_DOCS",
    "ESCALATE",
    "NOTE",
    "ASSIGN",
    "REOPEN",
    "COLLEGE_RESPONSE",
]
# one row per status, one cell per action above: (new status, roles) or None for 409
CONTRACT = {
    OPEN: [(UPHELD, {A, R}), (CORRECTED, {A, R}), (WITHDRAWN, {A, R}), (DOCS, {A, R}),
           (ESC, {A, R}), (OPEN, {A, R}), (OPEN, {A, R}), None, None],
    DOCS: [(UPHELD, {A, R}), (CORRECTED, {A, R}), (WITHDRAWN, {A, R}), (DOCS, {A, R}),
           (ESC, {A, R}), (DOCS, {A, R}), (DOCS, {A, R}), None, (DOCS, {C})],
    ESC: [(UPHELD, {A}), (CORRECTED, {A}), (WITHDRAWN, {A}), (DOCS, {A}),
          None, (ESC, {A, R}), (ESC, {A}), None, None],
    UPHELD: [None, None, None, None, None, (UPHELD, {A, R}), None, (OPEN, {A}), None],
    CORRECTED: [None, None, None, None, None, (CORRECTED, {A, R}), None, (OPEN, {A}), None],
    WITHDRAWN: [None, None, None, None, None, (WITHDRAWN, {A, R}), None, (OPEN, {A}), None],
}  # fmt: skip
CELLS = [
    (status, CaseActionKind(action), cell)
    for status, row in CONTRACT.items()
    for action, cell in zip(ACTIONS, row, strict=True)
]


def test_every_cell_for_every_role() -> None:
    for status, action, cell in CELLS:
        for role in UserRole:
            where = f"{role.value} {action.value} from {status.value}"
            if cell is None:
                with pytest.raises(ApiError) as caught:
                    transitions.check(role, status, action)
                assert caught.value.status_code == 409, where
                assert caught.value.code == "FLAG_TRANSITION_INVALID", where
                assert caught.value.details["status"] == status.value, where
                assert caught.value.details["action"] == action.value, where
                assert transitions.target(status, action) is None, where
                continue
            new_status, roles = cell
            assert transitions.target(status, action) is new_status, where
            if role in roles:
                assert transitions.check(role, status, action) is new_status, where
            else:
                with pytest.raises(ApiError) as caught:
                    transitions.check(role, status, action)
                assert caught.value.status_code == 403, where
                assert caught.value.code == "FORBIDDEN", where


def test_table_has_no_cell_the_contract_lacks() -> None:
    contract_cells = {(s, a) for s, a, cell in CELLS if cell is not None}
    assert set(transitions.TABLE) == contract_cells
    # SYSTEM_NOTE is written by the system only, never through the table
    assert all(a is not CaseActionKind.SYSTEM_NOTE for _, a in transitions.TABLE)


def test_allowed_actions_follow_the_action_bar_order() -> None:
    order = [a.value for a in transitions.OFFICER_ACTIONS]
    assert order == [
        "UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS", "ESCALATE", "NOTE", "ASSIGN", "REOPEN"
    ]  # fmt: skip
    words = lambda role, status: [a.value for a in transitions.allowed_actions(role, status)]  # noqa: E731
    undecided = ["UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS", "ESCALATE", "NOTE", "ASSIGN"]
    assert words(A, OPEN) == undecided
    assert words(R, DOCS) == undecided
    assert words(A, ESC) == ["UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS", "NOTE", "ASSIGN"]
    assert words(R, ESC) == ["NOTE"]
    for decided in (UPHELD, CORRECTED, WITHDRAWN):
        assert words(A, decided) == ["NOTE", "REOPEN"]
        assert words(R, decided) == ["NOTE"]
    for status in FlagStatus:
        assert words(C, status) == []
        assert words(UserRole.UNIVERSITY, status) == []


def test_the_409_names_the_status_in_words_and_what_is_allowed() -> None:
    with pytest.raises(ApiError) as caught:
        transitions.check(A, UPHELD, CaseActionKind.UPHOLD)
    assert caught.value.message == "This action is not possible while the case is claim upheld."
    assert caught.value.details == {
        "status": "UPHELD",
        "action": "UPHOLD",
        "allowed_actions": ["NOTE", "REOPEN"],
    }
    with pytest.raises(ApiError) as caught:
        transitions.check(C, OPEN, CaseActionKind.COLLEGE_RESPONSE)
    assert caught.value.message == ("This action is not possible while the case is open.")
    with pytest.raises(ApiError) as caught:
        transitions.check(A, CORRECTED, CaseActionKind.CORRECT)
    assert caught.value.message.endswith("while the case is claim corrected.")
    with pytest.raises(ApiError) as caught:
        transitions.check(R, DOCS, CaseActionKind.REOPEN)
    assert "waiting for documents" in caught.value.message


def test_notes_are_required_except_on_assign() -> None:
    for action in transitions.OFFICER_ACTIONS:
        assert transitions.note_required(action) is (action is not CaseActionKind.ASSIGN)
    assert transitions.NOTE_INTERNAL.isdisjoint(transitions.NOTE_SHOWN_TO_COLLEGE)
    # the college reads the notes of the three decisions and of a document request
    for action in ("UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS"):
        assert CaseActionKind(action) in transitions.NOTE_SHOWN_TO_COLLEGE
