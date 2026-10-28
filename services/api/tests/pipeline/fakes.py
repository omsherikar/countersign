"""Fake engine suites for pipeline tests (ENGINES.md §14)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from app.core import crypto
from app.engine.contracts import (
    ChecksResult,
    DuplicatesResult,
    FlagTally,
    LedgerResult,
    PoolRef,
)


class FakeEngines:
    """The minimal suite from ENGINES.md §14: names normalised, every engine a no-op."""

    def normalise_name(self, raw: str) -> str:
        return crypto.normalise_name(raw)

    def name_key(self, name: str, dob: date) -> str:
        tokens = crypto.normalise_name(name).split() or ["?"]
        return f"{dob.isoformat()}|{tokens[0][0]}|{tokens[-1].upper()}"

    async def assign_seats(self, session, enrolment_ids, *, actor_id):
        return LedgerResult()

    async def run_checks(self, session, enrolment_ids, adapters, *, concurrency=32, actor_id=None):
        return ChecksResult(enrolments=len(enrolment_ids))

    async def detect_duplicates(
        self, session, institution_id, academic_year, enrolment_ids, *, actor_id=None
    ):
        return DuplicatesResult()

    async def refresh_seat_flags(self, session, pools, *, actor_id=None):
        return FlagTally()


class RecordingEngines(FakeEngines):
    """Records every engine call; can raise in one stage and report seats, calls and flags."""

    def __init__(
        self,
        *,
        fail_in: str | None = None,
        fail_after_calls: int = 0,
        ledger: Any = None,
        checks: Any = None,
        pools: Sequence[PoolRef] = (),
    ) -> None:
        self.calls: dict[str, list[Any]] = {
            "assign_seats": [],
            "run_checks": [],
            "detect_duplicates": [],
            "refresh_seat_flags": [],
        }
        self.actors: dict[str, set[Any]] = {k: set() for k in self.calls}
        self.fail_in = fail_in
        self.fail_after_calls = fail_after_calls
        self.ledger = ledger
        self.checks = checks
        self.pools = list(pools)

    def _record(self, name: str, value: Any, actor_id: uuid.UUID | None) -> None:
        self.calls[name].append(value)
        self.actors[name].add(actor_id)
        if self.fail_in == name and len(self.calls[name]) > self.fail_after_calls:
            raise RuntimeError("engine exploded for Ravi Kumar Sharma 123456784417")

    async def assign_seats(self, session, enrolment_ids, *, actor_id):
        self._record("assign_seats", list(enrolment_ids), actor_id)
        if self.ledger is not None:
            return await self.ledger(session, list(enrolment_ids))
        return LedgerResult(touched_pools=set(self.pools))

    async def run_checks(self, session, enrolment_ids, adapters, *, concurrency=32, actor_id=None):
        self._record("run_checks", list(enrolment_ids), actor_id)
        if self.checks is not None:
            return await self.checks(session, list(enrolment_ids))
        return ChecksResult(enrolments=len(enrolment_ids))

    async def detect_duplicates(
        self, session, institution_id, academic_year, enrolment_ids, *, actor_id=None
    ):
        self._record("detect_duplicates", list(enrolment_ids), actor_id)
        return DuplicatesResult()

    async def refresh_seat_flags(self, session, pools, *, actor_id=None):
        self._record("refresh_seat_flags", list(pools), actor_id)
        return FlagTally(created=len(pools))
