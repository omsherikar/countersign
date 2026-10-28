"""Countersign score (docs/ENGINES.md section 11, DECISIONS D18, D21).

applicable = checks that are neither NOT_APPLICABLE nor NOT_YET_DUE; passes = CONFIRMED.
PENDING and SOURCE_UNAVAILABLE count as applicable and not as a pass, shown as "n of m".
An enrolment with no check rows has no score and is left out of both dashboard percentages.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from sqlalchemy import and_, func, select
from sqlalchemy.sql import Subquery

from app.engine.contracts import CHECK_ORDER, NOT_COUNTED_STATES
from app.models.enums import CheckStatus, CheckType
from app.models.verification import Check

_ORDER = {t.value: i for i, t in enumerate(CHECK_ORDER)}
_NOT_COUNTED = {s.value for s in NOT_COUNTED_STATES}


class _CheckLike(Protocol):
    type: CheckType | str
    status: CheckStatus | str


def _value(value: CheckStatus | CheckType | str) -> str:
    return value.value if isinstance(value, CheckStatus | CheckType) else str(value)


def score(statuses: Iterable[CheckStatus | str]) -> tuple[int, int] | None:
    """(passes, applicable), or None when there are no checks."""
    values = [_value(s) for s in statuses]
    if not values:
        return None
    applicable = sum(1 for v in values if v not in _NOT_COUNTED)
    passes = sum(1 for v in values if v == CheckStatus.CONFIRMED.value)
    return passes, applicable


def is_countersigned(statuses: Iterable[CheckStatus | str]) -> bool:
    result = score(statuses)
    return result is not None and result[1] >= 1 and result[0] == result[1]


def is_clear(statuses: Iterable[CheckStatus | str]) -> bool:
    values = [_value(s) for s in statuses]
    return bool(values) and CheckStatus.CONTRADICTED.value not in values


def countersign_from_pairs(
    pairs: Iterable[tuple[CheckType | str, CheckStatus | str]],
) -> dict[str, Any]:
    """The compact wire block {"score", "checks": [{type, status}]} in CHECK_ORDER."""
    by_type = {_value(t): _value(s) for t, s in pairs}
    if not by_type:
        return {"score": None, "checks": []}
    ordered = sorted(by_type.items(), key=lambda item: _ORDER.get(item[0], len(_ORDER)))
    passes, applicable = score(s for _, s in ordered) or (0, 0)
    return {
        "score": {"passes": passes, "applicable": applicable},
        "checks": [{"type": t, "status": s} for t, s in ordered],
    }


def countersign(checks: Iterable[_CheckLike]) -> dict[str, Any]:
    return countersign_from_pairs((c.type, c.status) for c in checks)


def countersign_state_sq(name: str = "countersign_state") -> Subquery:
    """Per enrolment with at least one check: `countersigned` and `clear` booleans."""
    applicable = func.count().filter(Check.status.not_in(NOT_COUNTED_STATES))
    passes = func.count().filter(Check.status == CheckStatus.CONFIRMED)
    fails = func.count().filter(Check.status == CheckStatus.CONTRADICTED)
    return (
        select(
            Check.enrolment_id.label("enrolment_id"),
            and_(applicable >= 1, passes == applicable).label("countersigned"),
            (fails == 0).label("clear"),
        )
        .group_by(Check.enrolment_id)
        .subquery(name)
    )
