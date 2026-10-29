"""What the seed derives once every upload and reply is in (ENGINES §17.15).

    python -m app.seed.derived --from /data/generated [--academic-year 2026-27]

First the completeness of every institution for the year (the state admission authority's
joinings against the uploads, `completeness.reconcile_all`, one transaction per institution),
then the signals of the year (`signals.service.run`, one transaction). Each settles record
statuses before it commits. Signals change no record: the settle after them finds nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.adapters.factory import build_adapters
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_factory
from app.engine import status
from app.engine.completeness import reconcile_all
from app.signals import service as signals

MANIFEST = "manifest.json"


def year_from(source: Path, fallback: str) -> str:
    """The manifest's one reporting year, else the configured academic year."""
    try:
        manifest = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    years = list((manifest.get("reporting_deadline") or {}).keys())
    return years[0] if len(years) == 1 else fallback


async def reconcile(academic_year: str) -> dict[str, Any]:
    """Completeness for every institution with an approval for the year."""
    adapters = build_adapters(get_settings())
    try:
        return await reconcile_all(session_factory(), adapters, academic_year)
    finally:
        await adapters.aclose()


async def detect(academic_year: str) -> dict[str, Any]:
    async with session_factory()() as session:
        result = await signals.run(session, academic_year)
        await status.commit(session)
    return result


async def derive(academic_year: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        completeness = await reconcile(academic_year)
        found = await detect(academic_year)
    finally:
        await dispose_engine()
    return completeness, found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed.derived",
        description="Compute completeness and signals after the seed's uploads and replies.",
    )
    parser.add_argument("--from", dest="source", required=True, help="the generated directory")
    parser.add_argument("--academic-year", default=None, help="e.g. 2026-27")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    year = args.academic_year or year_from(Path(args.source), settings.academic_year)
    started = time.perf_counter()
    completeness, found = asyncio.run(derive(year))
    print(f"completeness {year}: " + ", ".join(f"{k} {v}" for k, v in completeness.items()))
    model = found["model"]
    print(
        f"signals {year}: {found['rings']} rings, {found['anomalies']} unusual colleges "
        f"({found['created']} new, {found['updated']} updated; Isolation Forest over "
        f"{model['institutions']} colleges, contamination {model['contamination']})"
    )
    print(f"derived in {time.perf_counter() - started:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
