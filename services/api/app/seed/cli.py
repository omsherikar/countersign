"""python -m app.seed.cli --from DIR [--reset]: load datagen output into the api database."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_factory
from app.seed.importer import SeedError, import_directory

log = logging.getLogger("countersign.seed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed.cli", description="Import datagen output into the api database."
    )
    parser.add_argument(
        "--from",
        dest="source",
        required=True,
        help="directory written by datagen (API_CONTRACT §E)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="truncate every table before importing"
    )
    return parser


async def _run(source: Path, reset: bool) -> str:
    started = time.perf_counter()
    try:
        summary = await import_directory(session_factory(), source, reset=reset)
    finally:
        await dispose_engine()
    elapsed = time.perf_counter() - started
    rows = sum(int(u.counts.get("rows", 0)) for u in summary.uploads)
    files = sum(1 for u in summary.uploads if u.status != "SKIPPED")
    return f"{summary.table()}\n\nseeded {files} upload files, {rows} rows, in {elapsed:.1f} s"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.auto_migrate:
        from app.main import run_migrations

        run_migrations()
    try:
        table = asyncio.run(_run(Path(args.source), args.reset))
    except SeedError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 2
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
