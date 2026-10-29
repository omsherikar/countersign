"""The dashboard's check-based percentages, kept until the dashboard counts record statuses.

There is no per-record score any more: a record has one status from the evidence rule
(D35, `app.engine.status`). `countersign_state_sq` is the old per-enrolment aggregate the
dashboard's `countersigned_pct` and `clear_pct` still read (API_CONTRACT §A4.20 replaces
them with status counts).
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.sql import Subquery

from app.models.enums import CheckStatus
from app.models.verification import Check

_NOT_COUNTED = (CheckStatus.NOT_APPLICABLE, CheckStatus.NOT_YET_DUE)


def countersign_state_sq(name: str = "countersign_state") -> Subquery:
    """Per enrolment with at least one check: `countersigned` and `clear` booleans."""
    applicable = func.count().filter(Check.status.not_in(_NOT_COUNTED))
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
