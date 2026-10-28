"""python -m app.seed.cli --from DIR [--reset]: load datagen output into the api database.

After every upload has gone through run_batch, the student notices of each batch are sent
in upload order (D31): emails to SMTP_HOST (Mailpit in the demo) and DigiLocker messages to
mockgov. The last step computes the status of every ACTIVE record (D35); that is also how a
database migrated to revision 0004, whose records all start AWAITING_EVIDENCE, gets its
statuses. `python -m app.seed.replies` then applies the simulated replies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import AdapterSet
from app.adapters.factory import build_adapters
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_factory
from app.engine.status import refresh_record_status
from app.models.enums import EnrolmentStatus
from app.models.student import Enrolment
from app.notices.dispatch import send_notices_for_batch
from app.notices.mailer import Mailer, SmtpMailer, build_mailer
from app.seed.importer import SeedError, Summary, import_directory, load_inmemory_registries

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


def _link_digilocker(adapters: AdapterSet, directory: Path) -> None:
    """In-memory DigiLocker: every APAAR in the registry has an account, as in mockgov."""
    registry = directory / "apaar_registry.jsonl"
    if adapters.name != "inmemory" or not registry.is_file():
        return
    digilocker: Any = adapters.digilocker
    with registry.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                digilocker.linked.add(json.loads(line)["apaar_id"])


async def send_seed_notices(
    factory: async_sessionmaker[AsyncSession],
    summary: Summary,
    source: Path,
    *,
    adapters: AdapterSet | None = None,
    mailer: Mailer | None = None,
) -> int:
    """The notices of every seeded batch, in upload order; returns how many were created.

    A batch skipped as already seeded is sent again too: nothing is created for notices
    that already exist, so a re-run only fills what an interrupted run left out.
    """
    own_adapters = adapters is None
    if adapters is None:
        adapters = build_adapters()
        load_inmemory_registries(adapters, source / "mockgov")
        _link_digilocker(adapters, source / "mockgov")
    mailer = mailer or build_mailer()
    created = 0
    try:
        for upload in summary.uploads:
            if upload.batch_id is not None and upload.status in ("DONE", "SKIPPED"):
                created += await send_notices_for_batch(
                    upload.batch_id, factory=factory, adapters=adapters, mailer=mailer
                )
    finally:
        if own_adapters:
            await adapters.aclose()
    return created


async def refresh_every_record_status(factory: async_sessionmaker[AsyncSession]) -> int:
    """Every ACTIVE record's status from its final rows and cases; returns how many changed."""
    async with factory() as session:
        ids = (
            await session.execute(
                select(Enrolment.id)
                .where(Enrolment.status == EnrolmentStatus.ACTIVE)
                .order_by(Enrolment.id)
            )
        ).scalars()
        changed = await refresh_record_status(session, list(ids))
        await session.commit()
    return changed


async def _run(source: Path, reset: bool) -> str:
    started = time.perf_counter()
    try:
        factory = session_factory()
        summary = await import_directory(factory, source, reset=reset)
        uploaded = time.perf_counter()
        mailer = build_mailer()
        # With the mail server down every email would wait out its three tries per batch
        # and fail; sending nothing lets a re-run send everything once it is back.
        problem = mailer.ping() if isinstance(mailer, SmtpMailer) else None
        server = (
            f"{mailer.settings.smtp_host}:{mailer.settings.smtp_port}"
            if isinstance(mailer, SmtpMailer)
            else ""
        )
        if problem is None:
            notices = await send_seed_notices(factory, summary, source, mailer=mailer)
        statuses = await refresh_every_record_status(factory)
    finally:
        await dispose_engine()
    done = time.perf_counter()
    rows = sum(int(u.counts.get("rows", 0)) for u in summary.uploads)
    files = sum(1 for u in summary.uploads if u.status != "SKIPPED")
    if problem is None:
        sent = f"sent {notices} student notices in {done - uploaded:.1f} s"
    else:
        sent = (
            f"no student notices sent: {server} says "
            f'"{problem}" Start the mail server and run this again; it sends only what is '
            "missing."
        )
    return (
        f"{summary.table()}\n\nseeded {files} upload files, {rows} rows, in "
        f"{uploaded - started:.1f} s\nrecord statuses updated on {statuses} records\n{sent}"
    )


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
