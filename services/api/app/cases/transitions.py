"""The case transition table (API_CONTRACT §A4.8, D25, D43). Pure: no database, no I/O.

Each cell maps (status, action) to the status after the action and the roles that may take
it. A pair that is not in the table is not possible from that status for anyone (409); a
pair in the table that the caller's role is not listed for is a 403. On a multi-record case
WITHDRAW and CORRECT keep the case's status while a named record is still outstanding; the
case service applies that rule after the table (`app.cases.decisions`).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.core.errors import ApiError
from app.models.enums import CaseActionKind, FlagStatus, UserRole

UPHOLD = CaseActionKind.UPHOLD
CORRECT = CaseActionKind.CORRECT
WITHDRAW = CaseActionKind.WITHDRAW
REQUEST_DOCS = CaseActionKind.REQUEST_DOCS
ESCALATE = CaseActionKind.ESCALATE
NOTE = CaseActionKind.NOTE
ASSIGN = CaseActionKind.ASSIGN
REOPEN = CaseActionKind.REOPEN
COLLEGE_RESPONSE = CaseActionKind.COLLEGE_RESPONSE
SYSTEM_NOTE = CaseActionKind.SYSTEM_NOTE

# the order of the action bar and of `allowed_actions`
OFFICER_ACTIONS: tuple[CaseActionKind, ...] = (
    UPHOLD,
    CORRECT,
    WITHDRAW,
    REQUEST_DOCS,
    ESCALATE,
    NOTE,
    ASSIGN,
    REOPEN,
)
# the three decisions (D43); each needs a reason code and a note
DECISIONS: frozenset[CaseActionKind] = frozenset({UPHOLD, CORRECT, WITHDRAW})
# the actions that carry a reason code (API_CONTRACT §A4.9)
REASONED: frozenset[CaseActionKind] = frozenset({UPHOLD, CORRECT, WITHDRAW, ESCALATE})
# notes the college reads; the rest stay with officers (ASSIGN has no note)
NOTE_SHOWN_TO_COLLEGE: frozenset[CaseActionKind] = frozenset(
    {UPHOLD, CORRECT, WITHDRAW, REQUEST_DOCS, COLLEGE_RESPONSE, SYSTEM_NOTE}
)
NOTE_INTERNAL: frozenset[CaseActionKind] = frozenset({ESCALATE, NOTE, REOPEN})

_A = frozenset({UserRole.AICTE_ADMIN})
_AR = frozenset({UserRole.AICTE_ADMIN, UserRole.RO_OFFICER})
_I = frozenset({UserRole.INSTITUTION})

_OPEN, _DOCS, _ESC, _UPHELD, _WITHDRAWN, _CORRECTED = (
    FlagStatus.OPEN,
    FlagStatus.DOCS_REQUESTED,
    FlagStatus.ESCALATED,
    FlagStatus.UPHELD,
    FlagStatus.WITHDRAWN,
    FlagStatus.CORRECTED,
)
DECIDED: tuple[FlagStatus, ...] = (_UPHELD, _CORRECTED, _WITHDRAWN)


Cell = tuple[FlagStatus, frozenset[UserRole]]


def _undecided(status: FlagStatus) -> dict[tuple[FlagStatus, CaseActionKind], Cell]:
    return {
        (status, UPHOLD): (_UPHELD, _AR),
        (status, CORRECT): (_CORRECTED, _AR),
        (status, WITHDRAW): (_WITHDRAWN, _AR),
        (status, REQUEST_DOCS): (_DOCS, _AR),
        (status, ESCALATE): (_ESC, _AR),
        (status, NOTE): (status, _AR),
        (status, ASSIGN): (status, _AR),
    }


def _decided(status: FlagStatus) -> dict[tuple[FlagStatus, CaseActionKind], Cell]:
    # a decided case is final; only AICTE reopens it, and anyone may add a note
    return {(status, NOTE): (status, _AR), (status, REOPEN): (_OPEN, _A)}


TABLE: Mapping[tuple[FlagStatus, CaseActionKind], Cell] = {
    **_undecided(_OPEN),
    **_undecided(_DOCS),
    (_DOCS, COLLEGE_RESPONSE): (_DOCS, _I),
    # an escalation means AICTE takes over; the regional office can still add notes
    (_ESC, UPHOLD): (_UPHELD, _A),
    (_ESC, CORRECT): (_CORRECTED, _A),
    (_ESC, WITHDRAW): (_WITHDRAWN, _A),
    (_ESC, REQUEST_DOCS): (_DOCS, _A),
    (_ESC, NOTE): (_ESC, _AR),
    (_ESC, ASSIGN): (_ESC, _A),
    **_decided(_UPHELD),
    **_decided(_CORRECTED),
    **_decided(_WITHDRAWN),
}

STATUS_WORDS = {
    _OPEN: "open",
    _DOCS: "waiting for documents",
    _ESC: "escalated",
    _UPHELD: "claim upheld",
    _WITHDRAWN: "claim withdrawn",
    _CORRECTED: "claim corrected",
}


def target(status: FlagStatus, action: CaseActionKind) -> FlagStatus | None:
    """The status after the action, or None when the table has no such cell."""
    cell = TABLE.get((status, action))
    return cell[0] if cell else None


def allowed_actions(role: UserRole, status: FlagStatus) -> tuple[CaseActionKind, ...]:
    """The officer actions the role may take from this status, in OFFICER_ACTIONS order."""
    return tuple(
        action
        for action in OFFICER_ACTIONS
        if (cell := TABLE.get((status, action))) is not None and role in cell[1]
    )


def check(role: UserRole, status: FlagStatus, action: CaseActionKind) -> FlagStatus:
    """The new status, or 409 when nobody may act so from this status, or 403 for the role."""
    cell = TABLE.get((status, action))
    if cell is None:
        raise ApiError(
            409,
            "FLAG_TRANSITION_INVALID",
            f"This action is not possible while the case is {STATUS_WORDS[status]}.",
            {
                "status": status.value,
                "action": action.value,
                "allowed_actions": [a.value for a in allowed_actions(role, status)],
            },
        )
    new_status, roles = cell
    if role not in roles:
        raise ApiError(
            403,
            "FORBIDDEN",
            "Your role cannot access this resource.",
            {"required_roles": sorted(r.value for r in roles)},
        )
    return new_status


def note_required(action: CaseActionKind) -> bool:
    """Every officer action needs a note except ASSIGN."""
    return action is not ASSIGN
