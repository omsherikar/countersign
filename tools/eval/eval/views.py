"""Plain views of what the engine produced, read once from the database by `snapshot.take`.

The scoring modules work on these only, so their tests need no database. Ids are strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

UNRESOLVED = frozenset({"OPEN", "DOCS_REQUESTED", "ESCALATED"})
REVIEW_STATUSES = frozenset({"UNDER_REVIEW", "DISPUTED"})


@dataclass(frozen=True, slots=True)
class CaseView:
    id: str
    type: str
    severity: str
    status: str
    institution: str  # AICTE permanent id
    enrolments: frozenset[str] = frozenset()  # the case's own record and the related ones
    programme_code: str | None = None
    academic_year: str | None = None
    pool: str | None = None  # the seat type of an EXCESS_ADMISSION or QUOTA_BREACH pool
    facts: int = 0

    @property
    def unresolved(self) -> bool:
        return self.status in UNRESOLVED


@dataclass(frozen=True, slots=True)
class RecordView:
    id: str
    institution: str
    status: str  # enrolment status: ACTIVE, WITHDRAWN, TRANSFERRED, GRADUATED
    record_status: str | None
    from_upload: bool = True
    rows: Mapping[str, str] = field(default_factory=dict)  # check type -> evidence state

    @property
    def active(self) -> bool:
        return self.status == "ACTIVE"


@dataclass(frozen=True, slots=True)
class SignalView:
    id: str
    type: str  # GHOST_RING or ANOMALY
    institutions: frozenset[str] = frozenset()
    enrolments: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class BatchView:
    filename: str
    institution: str
    rows: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None

    @property
    def millis(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds() * 1000
