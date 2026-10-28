"""The engines `run_batch` calls, behind the EngineSuite protocol (docs/ENGINES.md section 3).

`pipeline.default_engines()` returns `DefaultEngines()`; tests pass their own fakes.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterSet
from app.engine import checks, duplicates, flags, ledger, matching
from app.engine.contracts import (
    DEFAULT_CHECK_CONCURRENCY,
    ChecksResult,
    DuplicatesResult,
    EngineSuite,
    FlagTally,
    LedgerResult,
    PoolRef,
)


class DefaultEngines:
    """The real engine modules, one method per stage."""

    def normalise_name(self, raw: str) -> str:
        return matching.normalise_name(raw)

    def name_key(self, name: str, dob: date) -> str:
        return matching.name_key(name, dob)

    async def assign_seats(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None,
    ) -> LedgerResult:
        return await ledger.assign_seats(session, enrolment_ids, actor_id=actor_id)

    async def run_checks(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        adapters: AdapterSet,
        *,
        concurrency: int = DEFAULT_CHECK_CONCURRENCY,
        actor_id: uuid.UUID | None = None,
    ) -> ChecksResult:
        return await checks.run_checks(
            session, enrolment_ids, adapters, concurrency=concurrency, actor_id=actor_id
        )

    async def detect_duplicates(
        self,
        session: AsyncSession,
        institution_id: uuid.UUID,
        academic_year: str,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> DuplicatesResult:
        return await duplicates.detect_duplicates(
            session, institution_id, academic_year, enrolment_ids, actor_id=actor_id
        )

    async def refresh_seat_flags(
        self,
        session: AsyncSession,
        pools: Sequence[PoolRef],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> FlagTally:
        return await flags.refresh_seat_flags(session, pools, actor_id=actor_id)


def default_engines() -> EngineSuite:
    return DefaultEngines()
