"""Chaos toggles: latency, random failure and hard-down per government source.

Defaults come from MOCKGOV_LATENCY_MS and MOCKGOV_FAIL_RATE. Per-source overrides are set
through /admin/chaos and written through to the `chaos` table so they survive a reload.
Admin and healthz routes never pass through the gate.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import SourceDown
from app.models import ChaosSetting

SOURCES: tuple[str, ...] = ("apaar", "counselling", "abc", "digilocker", "sii")

DOWN_MESSAGES = {
    "apaar": "APAAR registry unavailable.",
    "counselling": "Counselling allotment registry unavailable.",
    "abc": "Academic Bank of Credits unavailable.",
    "digilocker": "DigiLocker unavailable.",
    "sii": "Study in India registry unavailable.",
}


@dataclass
class SourceChaos:
    latency_ms: int = 0
    fail_rate: float = 0.0
    down: bool = False


class ChaosState:
    def __init__(self, default_latency_ms: int = 0, default_fail_rate: float = 0.0) -> None:
        self.default_latency_ms = default_latency_ms
        self.default_fail_rate = default_fail_rate
        self._sources: dict[str, SourceChaos] = {}
        self.reset()

    def _default(self) -> SourceChaos:
        return SourceChaos(latency_ms=self.default_latency_ms, fail_rate=self.default_fail_rate)

    def reset(self) -> None:
        self._sources = {source: self._default() for source in SOURCES}

    def get(self, source: str) -> SourceChaos:
        return self._sources[source]

    def snapshot(self) -> dict[str, dict]:
        return {source: asdict(self._sources[source]) for source in SOURCES}

    def set(self, source: str, latency_ms: int, fail_rate: float, down: bool) -> dict[str, dict]:
        targets = SOURCES if source == "all" else (source,)
        for target in targets:
            self._sources[target] = SourceChaos(latency_ms, fail_rate, down)
        return {target: asdict(self._sources[target]) for target in targets}

    async def apply(self, source: str) -> None:
        chaos = self._sources[source]
        if chaos.latency_ms > 0:
            await asyncio.sleep(chaos.latency_ms / 1000)
        if chaos.down or (chaos.fail_rate > 0 and random.random() < chaos.fail_rate):
            raise SourceDown(DOWN_MESSAGES[source])

    # Persistence -------------------------------------------------------------------

    async def load(self, session: AsyncSession) -> None:
        """Adopt rows from the chaos table; seed missing sources with the env defaults."""
        rows = {row.source: row for row in (await session.scalars(select(ChaosSetting))).all()}
        for source in SOURCES:
            row = rows.get(source)
            if row is None:
                continue
            self._sources[source] = SourceChaos(
                latency_ms=int(row.latency_ms), fail_rate=float(row.fail_rate), down=bool(row.down)
            )
        await self.save(session)

    async def save(self, session: AsyncSession) -> None:
        stmt = insert(ChaosSetting).values(
            [{"source": source, **asdict(chaos)} for source, chaos in self._sources.items()]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChaosSetting.source],
            set_={
                "latency_ms": stmt.excluded.latency_ms,
                "fail_rate": stmt.excluded.fail_rate,
                "down": stmt.excluded.down,
            },
        )
        await session.execute(stmt)
        await session.commit()


def chaos_gate(source: str) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency that applies the source's chaos settings before the handler runs."""

    async def gate(request: Request) -> None:
        chaos: ChaosState = request.app.state.chaos
        await chaos.apply(source)

    return gate
