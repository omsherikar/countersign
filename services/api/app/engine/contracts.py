"""Shared engine contract (docs/ENGINES.md section 3).

Both api branches add this file with identical bytes. Change docs/ENGINES.md first,
then copy the new text into this file on every branch.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterSet
from app.models.enums import CheckStatus, CheckType, FlagStatus, FlagType, SeatType, Severity
from app.models.verification import Flag

CHUNK_SIZE = 500
DEFAULT_CHECK_CONCURRENCY = 32

CHECK_ORDER: tuple[CheckType, ...] = (
    CheckType.IDENTITY,
    CheckType.ADMISSION,
    CheckType.SEAT,
    CheckType.STUDYING,
    CheckType.STUDENT,
)
UNRESOLVED_FLAG_STATUSES: tuple[FlagStatus, ...] = (
    FlagStatus.OPEN,
    FlagStatus.DOCS_REQUESTED,
    FlagStatus.ESCALATED,
)

NameVerdict = Literal["MATCH", "REVIEW", "NO_MATCH"]
NameMethod = Literal["EXACT", "INITIALS", "FUZZY"]


@dataclass(frozen=True, slots=True)
class NameMatch:
    """Result of matching.match_names(a, b). `a` and `b` are the normalised inputs."""

    score: int
    verdict: NameVerdict
    method: NameMethod
    a: str
    b: str


@dataclass(frozen=True, slots=True)
class PoolRef:
    """One seat pool: the approval it belongs to and its seat type."""

    approval_id: uuid.UUID
    seat_type: SeatType


@dataclass(frozen=True, slots=True)
class FlagIntent:
    """A flag an engine wants raised; flags.raise_flag(**intent fields) writes it."""

    type: FlagType
    severity: Severity
    institution_id: uuid.UUID
    academic_year: str
    dedupe_key: str
    evidence: dict[str, Any]
    programme_id: uuid.UUID | None = None
    enrolment_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class RaisedFlag:
    """What flags.raise_flag returns: the row, and whether it was created or changed."""

    flag: Flag
    created: bool
    changed: bool


@dataclass(slots=True)
class FlagTally:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    flag_ids: list[uuid.UUID] = field(default_factory=list)

    def count(self, raised: RaisedFlag) -> None:
        if raised.created:
            self.created += 1
        elif raised.changed:
            self.updated += 1
        else:
            self.unchanged += 1
        self.flag_ids.append(raised.flag.id)

    def merge(self, other: FlagTally) -> None:
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged
        self.flag_ids.extend(other.flag_ids)


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """One check's verdict for one enrolment. `detail` always carries a `summary`."""

    type: CheckType
    status: CheckStatus
    source: str
    detail: dict[str, Any]
    flags: tuple[FlagIntent, ...] = ()
    calls: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()


@dataclass(slots=True)
class LedgerResult:
    seated: list[uuid.UUID] = field(default_factory=list)
    released: list[uuid.UUID] = field(default_factory=list)
    unseated: list[uuid.UUID] = field(default_factory=list)
    late_refills: list[uuid.UUID] = field(default_factory=list)
    touched_pools: set[PoolRef] = field(default_factory=set)
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: LedgerResult) -> None:
        self.seated.extend(other.seated)
        self.released.extend(other.released)
        self.unseated.extend(other.unseated)
        self.late_refills.extend(other.late_refills)
        self.touched_pools |= other.touched_pools
        self.flags.merge(other.flags)


@dataclass(slots=True)
class ChecksResult:
    enrolments: int = 0
    changed: int = 0
    statuses: dict[str, dict[str, int]] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    unavailable: dict[str, int] = field(default_factory=dict)
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: ChecksResult) -> None:
        self.enrolments += other.enrolments
        self.changed += other.changed
        for check_type, by_status in other.statuses.items():
            mine = self.statuses.setdefault(check_type, {})
            for status, n in by_status.items():
                mine[status] = mine.get(status, 0) + n
        for source, n in other.calls.items():
            self.calls[source] = self.calls.get(source, 0) + n
        for source, n in other.unavailable.items():
            self.unavailable[source] = self.unavailable.get(source, 0) + n
        self.flags.merge(other.flags)


@dataclass(slots=True)
class DuplicatesResult:
    within: int = 0
    cross: int = 0
    dual: int = 0
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: DuplicatesResult) -> None:
        self.within += other.within
        self.cross += other.cross
        self.dual += other.dual
        self.flags.merge(other.flags)


@dataclass(slots=True)
class RecheckResult:
    enrolments: int = 0
    rechecked: int = 0
    now_pass: int = 0
    now_fail: int = 0
    now_na: int = 0
    still_pending: int = 0
    flags: FlagTally = field(default_factory=FlagTally)


class EngineSuite(Protocol):
    """What run_batch needs from the engine modules. Tests pass a fake."""

    def normalise_name(self, raw: str) -> str: ...

    def name_key(self, name: str, dob: date) -> str: ...

    async def assign_seats(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None,
    ) -> LedgerResult: ...

    async def run_checks(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        adapters: AdapterSet,
        *,
        concurrency: int = DEFAULT_CHECK_CONCURRENCY,
        actor_id: uuid.UUID | None = None,
    ) -> ChecksResult: ...

    async def detect_duplicates(
        self,
        session: AsyncSession,
        institution_id: uuid.UUID,
        academic_year: str,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> DuplicatesResult: ...

    async def refresh_seat_flags(
        self,
        session: AsyncSession,
        pools: Sequence[PoolRef],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> FlagTally: ...
