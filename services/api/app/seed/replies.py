"""python -m app.seed.replies --from DIR: apply datagen's simulated notice replies (D31).

Reads DIR/notice_replies.jsonl (API_CONTRACT §A3.28). Each YES or NO line names a row of an
initial upload file; the enrolment is the one that row created (the SEED batch with that
file name, `enrolments.source_row_no` = `row_no`). The reply goes through
`notices.service.reply_for_enrolment`, the same `apply_reply` as the public reply, with no
actor and `via` "demo-seed" in the audit entry. NONE lines are skipped and
`reply_after_days` is not used. One transaction per 500 lines, whose replies are finished
together (one STUDENT refresh, then the proofs); a line that names nothing, or that the
service refuses, is reported and skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_factory
from app.models.enums import NoticeChannel, NoticeResponse, UploadSource
from app.models.student import Enrolment
from app.models.upload import UploadBatch
from app.notices.service import VIA_SEED, ReplyOutcome, finish_replies, reply_for_enrolment

log = logging.getLogger("countersign.seed")

REPLIES_FILE = "notice_replies.jsonl"
LINES_PER_TRANSACTION = 500
SHOWN_PROBLEMS = 20


@dataclass
class ReplyCounts:
    lines: int = 0
    yes: int = 0
    no: int = 0
    no_reply: int = 0
    not_found: int = 0
    refused: int = 0
    problems: list[str] = field(default_factory=list)

    def problem(self, text: str) -> None:
        if len(self.problems) < SHOWN_PROBLEMS:
            self.problems.append(text)

    def table(self) -> str:
        lines = [
            f"reply lines        {self.lines:>7}",
            f"  YES applied      {self.yes:>7}",
            f"  NO applied       {self.no:>7}",
            f"  no reply (NONE)  {self.no_reply:>7}",
            f"  row not found    {self.not_found:>7}",
            f"  refused          {self.refused:>7}",
        ]
        lines += [f"  - {p}" for p in self.problems]
        return "\n".join(lines)


def read_lines(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for number, raw in enumerate(fh, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} line {number}: not JSON ({exc.msg})") from None
    return out


async def seeded_rows(session: AsyncSession) -> dict[tuple[str, int], uuid.UUID]:
    """(file name, row_no) of every enrolment a SEED batch created or last updated."""
    rows = await session.execute(
        select(UploadBatch.filename, Enrolment.source_row_no, Enrolment.id)
        .join(Enrolment, Enrolment.upload_batch_id == UploadBatch.id)
        .where(UploadBatch.source == UploadSource.SEED, Enrolment.source_row_no.is_not(None))
        .order_by(UploadBatch.created_at)
    )
    return {(filename, row_no): enrolment_id for filename, row_no, enrolment_id in rows.all()}


def _parse(line: dict[str, Any]) -> tuple[str, int, NoticeResponse | None, NoticeChannel, Any]:
    reply = str(line.get("reply", "NONE")).upper()
    response = None if reply == "NONE" else NoticeResponse(reply)
    channel = NoticeChannel(str(line.get("channel") or "EMAIL").upper())
    return (
        PurePath(str(line["file"])).name,
        int(line["row_no"]),
        response,
        channel,
        line.get("comment"),
    )


async def apply_replies(
    factory: async_sessionmaker[AsyncSession], path: Path, *, via: str = VIA_SEED
) -> ReplyCounts:
    counts = ReplyCounts()
    lines = read_lines(path)
    counts.lines = len(lines)
    async with factory() as session:
        index = await seeded_rows(session)
    work: list[tuple[uuid.UUID, NoticeResponse, NoticeChannel, Any, str]] = []
    for line in lines:
        try:
            filename, row_no, response, channel, comment = _parse(line)
        except (KeyError, ValueError) as exc:
            counts.refused += 1
            counts.problem(f"line not understood: {exc}")
            continue
        if response is None:
            counts.no_reply += 1
            continue
        enrolment_id = index.get((filename, row_no))
        if enrolment_id is None:
            counts.not_found += 1
            counts.problem(f"{filename} row {row_no}: no seeded enrolment")
            continue
        work.append((enrolment_id, response, channel, comment, f"{filename} row {row_no}"))

    for start in range(0, len(work), LINES_PER_TRANSACTION):
        async with factory() as session:
            sink: list[AuditEntry] = []
            outcomes: list[ReplyOutcome] = []
            for enrolment_id, response, channel, comment, where in work[
                start : start + LINES_PER_TRANSACTION
            ]:
                try:
                    # a refusal is raised before anything is written, so the chunk goes on
                    outcome = await reply_for_enrolment(
                        session,
                        enrolment_id,
                        channel,
                        response,
                        comment,
                        via=via,
                        finish=False,
                        audit_sink=sink,
                    )
                except ApiError as exc:
                    counts.refused += 1
                    counts.problem(f"{where}: {exc.code} {exc.message}")
                    continue
                outcomes.append(outcome)
                if response is NoticeResponse.YES:
                    counts.yes += 1
                else:
                    counts.no += 1
            await audit.record_many(session, sink)
            await finish_replies(session, outcomes)
            await session.commit()
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed.replies",
        description="Apply datagen's simulated notice replies to the seeded notices.",
    )
    parser.add_argument(
        "--from", dest="source", required=True, help=f"directory holding {REPLIES_FILE}"
    )
    return parser


async def _run(path: Path) -> str:
    started = time.perf_counter()
    try:
        counts = await apply_replies(session_factory(), path)
    finally:
        await dispose_engine()
    return f"{counts.table()}\n\napplied replies in {time.perf_counter() - started:.1f} s"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(get_settings().log_level)
    path = Path(args.source) / REPLIES_FILE
    if not path.is_file():
        print(f"no {REPLIES_FILE} in {args.source}; no replies applied")
        return 0
    try:
        read_lines(path)
    except ValueError as exc:
        print(f"replies failed: {exc}", file=sys.stderr)
        return 2
    print(asyncio.run(_run(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
