"""Processing time per upload (from the seed's batches) and the 50,000-row run."""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path
from typing import Any

from .truth import PERF_INSTITUTION
from .views import BatchView

TARGET_SECONDS = 120


def percentile(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def upload_timing(batches: Iterable[BatchView], exclude: Collection[str] = ()) -> dict[str, Any]:
    """finished_at - started_at of every DONE batch outside the excluded institutions."""
    done = [
        b
        for b in batches
        if b.status == "DONE" and b.millis is not None and b.institution not in exclude
    ]
    millis = [b.millis for b in done if b.millis is not None]
    rows = sum(b.rows for b in done)
    total = sum(millis)
    return {
        "count": len(done),
        "rows": rows,
        "median_ms": _round(percentile(millis, 0.5)),
        "p95_ms": _round(percentile(millis, 0.95)),
        "max_ms": _round(max(millis) if millis else None),
        "rows_per_second": round(rows / (total / 1000), 1) if total else None,
    }


def _round(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def perf_result(
    *,
    file: str,
    rows: int,
    seconds: float,
    stages_ms: dict[str, int],
    status: str,
    fresh: bool,
    concurrency: int | None = None,
    sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "file": file,
        "rows": rows,
        "seconds": round(seconds, 1),
        "rows_per_second": round(rows / seconds, 1) if seconds else None,
        "ms_per_row": round(1000 * seconds / rows, 2) if rows else None,
        "stages_ms": dict(stages_ms),
        "status": status,
        "fresh": fresh,
        "checks_concurrency": concurrency,
        "sources": sources or {},
    }


def throughput_met(perf: dict[str, Any] | None) -> bool | None:
    """None when the 50,000-row run was skipped; a re-run over loaded rows never counts."""
    if perf is None:
        return None
    return bool(perf["status"] == "DONE" and perf["fresh"] and perf["seconds"] < TARGET_SECONDS)


async def run_perf(factory: Any, generated: Path, perf: dict[str, Any], adapters: Any = None):
    """Import the throughput college and time `run_batch` on its file, as a SEED batch."""
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.core.rules import get_rules
    from app.engine.pipeline import run_batch
    from app.engine.upload.batches import create_batch
    from app.models.enums import UploadSource, UserRole
    from app.models.institution import Institution
    from app.models.student import Enrolment
    from app.models.user import User
    from app.seed.importer import Summary, import_institutions

    path = Path(generated) / perf["file"]
    async with factory() as session:
        await import_institutions(
            session, Path(generated) / perf["institutions_file"], get_rules(), Summary()
        )
        await session.commit()
    async with factory() as session:
        institution = (
            await session.execute(
                select(Institution).where(Institution.aicte_permanent_id == PERF_INSTITUTION)
            )
        ).scalar_one()
        loaded = (
            await session.execute(
                select(func.count())
                .select_from(Enrolment)
                .where(Enrolment.institution_id == institution.id)
            )
        ).scalar_one()
        owner = (
            await session.execute(
                select(User.id)
                .where(User.role == UserRole.AICTE_ADMIN, User.is_active.is_(True))
                .order_by(User.created_at)
                .limit(1)
            )
        ).scalar_one()
        batch = await create_batch(
            session,
            institution_id=institution.id,
            academic_year=path.stem.rsplit("_", 1)[-1],
            filename=path.name,
            source=UploadSource.SEED,
            uploaded_by=owner,
            file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            actor_id=None,
        )
        await session.commit()
    started = time.perf_counter()
    batch = await run_batch(batch.id, factory=factory, adapters=adapters, source=path)
    seconds = time.perf_counter() - started
    counts = batch.counts or {}
    return perf_result(
        file=perf["file"],
        rows=int(counts.get("rows", 0)),
        seconds=seconds,
        stages_ms=counts.get("timings_ms", {}),
        status=batch.status.value,
        fresh=loaded == 0,
        concurrency=get_settings().checks_concurrency,
        sources=counts.get("sources"),
    )
