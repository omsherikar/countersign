"""run_batch: every upload, API call and seed file goes through these stages in order.

PARSE, VALIDATE, FILE_DUPLICATES (status VALIDATING), then UPSERT, LEDGER, CHECKS,
DUPLICATES, FLAGS (status PROCESSING), then DONE (D15, ENGINES.md §4). Work runs in chunks
of CHUNK_SIZE; each chunk's writes, its row errors, its audit entries and the batch's
progress commit together, so progress is never ahead of the data. A stage that raises
rolls back its chunk and marks the batch FAILED; committed chunks stay, and uploading
the file again finishes the job because every stage is idempotent.
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import AdapterSet
from app.adapters.factory import build_adapters
from app.core import audit
from app.core.config import get_settings
from app.db.session import session_factory
from app.engine.contracts import (
    CHUNK_SIZE,
    ChecksResult,
    EngineSuite,
    FlagTally,
    PoolRef,
)
from app.engine.upload.batches import empty_counts
from app.engine.upload.parse import UNREADABLE, parse_rows, parse_upload
from app.engine.upload.spool import delete_spool, find_spool, read_spool
from app.engine.upload.types import (
    CleanRow,
    ParsedUpload,
    RowIssue,
    RowOutcome,
    UploadFileError,
    upload_date,
)
from app.engine.upload.upsert import upsert_rows
from app.engine.upload.validate import file_duplicates, load_context, validate_rows
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    RowErrorLevel,
    UploadSource,
    UploadStage,
    UploadStatus,
)
from app.models.institution import Institution
from app.models.student import Enrolment
from app.models.upload import UploadBatch, UploadRowError
from app.models.verification import Check

log = logging.getLogger("countersign.pipeline")

STAGES: tuple[UploadStage, ...] = (
    UploadStage.PARSE,
    UploadStage.VALIDATE,
    UploadStage.FILE_DUPLICATES,
    UploadStage.UPSERT,
    UploadStage.LEDGER,
    UploadStage.CHECKS,
    UploadStage.DUPLICATES,
    UploadStage.FLAGS,
)
STAGE_WEIGHTS: dict[UploadStage, int] = {
    UploadStage.PARSE: 5,
    UploadStage.VALIDATE: 10,
    UploadStage.FILE_DUPLICATES: 5,
    UploadStage.UPSERT: 15,
    UploadStage.LEDGER: 10,
    UploadStage.CHECKS: 45,
    UploadStage.DUPLICATES: 5,
    UploadStage.FLAGS: 5,
}
STAGE_WORDS: dict[UploadStage, str] = {
    UploadStage.PARSE: "reading the file",
    UploadStage.VALIDATE: "checking rows",
    UploadStage.FILE_DUPLICATES: "looking for repeated rows",
    UploadStage.UPSERT: "saving students and enrolments",
    UploadStage.LEDGER: "assigning seats",
    UploadStage.CHECKS: "checking with sources",
    UploadStage.DUPLICATES: "looking for duplicates",
    UploadStage.FLAGS: "raising flags",
}
VALIDATING_STAGES = (UploadStage.PARSE, UploadStage.VALIDATE, UploadStage.FILE_DUPLICATES)
SOURCE_ORDER = ("APAAR", "COUNSELLING", "ABC", "SII")
ISSUE_INSERT_BATCH = 1000


def stopped_error(stage: UploadStage) -> str:
    return (
        f"Processing stopped while {STAGE_WORDS[stage]}. "
        "Upload the file again; rows already saved are kept."
    )


def progress_pct(
    status: UploadStatus, stage: UploadStage | None, processed_rows: int, stage_total: int
) -> int:
    """0 while QUEUED, 100 when DONE; else finished stage weights plus the current share."""
    if status is UploadStatus.DONE or stage is UploadStage.DONE:
        return 100
    if status is UploadStatus.QUEUED or stage is None:
        return 0
    finished = sum(STAGE_WEIGHTS[s] for s in STAGES[: STAGES.index(stage)])
    share = min(processed_rows, stage_total) / max(stage_total, 1)
    return math.floor(finished + STAGE_WEIGHTS[stage] * share)


def chunks[T](items: Sequence[T], size: int = CHUNK_SIZE) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


# ------------------------------------------------------------------ engine suite


def default_engines() -> EngineSuite:
    """The real engine modules, imported here and never at module import time."""
    from app.engine.suite import DefaultEngines

    return DefaultEngines()


# ---------------------------------------------------------------------- run_batch


class _Stop(Exception):
    """The batch has been marked FAILED for a file-level reason; stop quietly."""


class _BatchRun:
    def __init__(
        self,
        batch_id: uuid.UUID,
        factory: async_sessionmaker[AsyncSession],
        adapters: AdapterSet,
        engines: EngineSuite,
        source: Path | list[dict[str, Any]] | None,
    ) -> None:
        self.batch_id = batch_id
        self.factory = factory
        self.adapters = adapters
        self.engines = engines
        self.source = source
        self.settings = get_settings()
        self.counts: dict[str, Any] = empty_counts()
        self.stage: UploadStage = UploadStage.PARSE
        self.stage_started = time.perf_counter()
        self.actor_id: uuid.UUID | None = None
        self.parsed = ParsedUpload(rows=[])
        self.valid: list[CleanRow] = []
        self.accepted: list[CleanRow] = []
        self.rejected: set[int] = set()
        self.warned: set[int] = set()
        self.outcomes: list[RowOutcome] = []
        self.seated: list[uuid.UUID] = []
        self.pools: set[PoolRef] = set()
        self.checks = ChecksResult()

    # -- batch row helpers

    async def _set(self, session: AsyncSession, **values: Any) -> None:
        await session.execute(
            update(UploadBatch).where(UploadBatch.id == self.batch_id).values(**values)
        )

    async def _load(self) -> UploadBatch:
        async with self.factory() as session:
            batch = await session.get(UploadBatch, self.batch_id)
        if batch is None:
            raise LookupError(f"upload batch {self.batch_id} does not exist")
        return batch

    async def _begin(self, stage: UploadStage, total: int) -> None:
        self.stage = stage
        self.stage_started = time.perf_counter()
        status = UploadStatus.VALIDATING if stage in VALIDATING_STAGES else UploadStatus.PROCESSING
        async with self.factory() as session:
            await self._set(
                session,
                stage=stage,
                status=status,
                stage_total=total,
                processed_rows=0,
                counts=self.counts,
            )
            await session.commit()

    def _end(self) -> None:
        elapsed = int((time.perf_counter() - self.stage_started) * 1000)
        self.counts["timings_ms"][self.stage.value] = elapsed

    async def _chunk(self, work: Callable[[AsyncSession], Awaitable[None]], processed: int) -> None:
        async with self.factory() as session:
            await work(session)
            await self._set(session, processed_rows=processed)
            await session.commit()

    async def _write_issues(self, session: AsyncSession, issues: Sequence[RowIssue]) -> None:
        for issue in issues:
            if issue.level is RowErrorLevel.WARNING:
                self.warned.add(issue.row_no)
        values = [
            {
                "batch_id": self.batch_id,
                "row_no": issue.row_no,
                "level": issue.level,
                "field": issue.field,
                "code": issue.code,
                "message": issue.message,
                "value_masked": issue.value_masked,
                "raw": issue.raw,
            }
            for issue in issues
        ]
        for part in chunks(values, ISSUE_INSERT_BATCH):
            await session.execute(insert(UploadRowError).values(list(part)))

    def _tally(self, tally: FlagTally) -> None:
        self.counts["flags_raised"] += tally.created
        self.counts["flags_updated"] += tally.updated

    # -- the run

    async def execute(self) -> UploadBatch:
        batch = await self._load()
        if batch.status in (UploadStatus.DONE, UploadStatus.FAILED):
            return batch
        self.actor_id = None if batch.source is UploadSource.SEED else batch.uploaded_by
        self.batch = batch
        async with self.factory() as session:
            await session.execute(
                delete(UploadRowError).where(UploadRowError.batch_id == self.batch_id)
            )
            await self._set(
                session,
                status=UploadStatus.VALIDATING,
                stage=UploadStage.PARSE,
                stage_total=0,
                processed_rows=0,
                total_rows=0,
                counts=self.counts,
                error=None,
                ignored_columns=[],
                started_at=datetime.now(UTC),
                finished_at=None,
            )
            await session.commit()

        steps: list[tuple[UploadStage, Callable[[], Awaitable[None]]]] = [
            (UploadStage.PARSE, self._parse),
            (UploadStage.VALIDATE, self._validate),
            (UploadStage.FILE_DUPLICATES, self._file_duplicates),
            (UploadStage.UPSERT, self._upsert),
            (UploadStage.LEDGER, self._ledger),
            (UploadStage.CHECKS, self._checks),
            (UploadStage.DUPLICATES, self._duplicates),
            (UploadStage.FLAGS, self._flags),
        ]
        for stage, step in steps:
            try:
                await step()
            except _Stop:
                return await self._load()
            except Exception:
                log.exception(
                    "upload stage failed",
                    extra={"batch_id": str(self.batch_id), "stage": stage.value},
                )
                await self._finish(UploadStatus.FAILED, stage, error=stopped_error(stage))
                return await self._load()
        await self._finish(UploadStatus.DONE, UploadStage.DONE)
        return await self._load()

    async def _finish(
        self, status: UploadStatus, stage: UploadStage, *, error: str | None = None
    ) -> None:
        if status is UploadStatus.DONE:
            self._end()
        values: dict[str, Any] = {
            "status": status,
            "stage": stage,
            "counts": self.counts,
            "error": error,
            "finished_at": datetime.now(UTC),
        }
        if status is UploadStatus.DONE:
            values |= {"stage_total": 0, "processed_rows": 0}
        async with self.factory() as session:
            await self._set(session, **values)
            await audit.record_many(
                session,
                [
                    audit.AuditEntry(
                        action=AuditAction.UPDATE,
                        entity_type="upload_batch",
                        entity_id=self.batch_id,
                        actor_id=self.actor_id,
                        after={
                            "status": status.value,
                            "stage": stage.value,
                            "counts": {k: v for k, v in self.counts.items() if k != "sources"},
                        },
                    )
                ],
            )
            await session.commit()
        if self.source is None:
            delete_spool(self.batch_id)

    # -- stages

    async def _parse(self) -> None:
        self.stage = UploadStage.PARSE
        self.stage_started = time.perf_counter()
        try:
            self.parsed = self._read()
        except UploadFileError as exc:
            await self._finish(UploadStatus.FAILED, UploadStage.PARSE, error=exc.message)
            raise _Stop from None
        n = self.parsed.total_rows
        self.counts["rows"] = n
        self._end()
        async with self.factory() as session:
            await self._set(
                session,
                total_rows=n,
                ignored_columns=self.parsed.ignored_columns,
                stage_total=n,
                processed_rows=n,
                counts=self.counts,
            )
            await session.commit()

    def _read(self) -> ParsedUpload:
        if isinstance(self.source, Path):
            return parse_upload(self.source, self.source.name)
        if isinstance(self.source, list):
            return parse_rows(self.source)
        found = find_spool(self.batch_id)
        if found is None:
            raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE)
        kind, path = found
        data = read_spool(path)
        if kind == "json":
            return parse_rows(json.loads(data))
        return parse_upload(data, f"{self.batch_id}.{kind}")

    async def _validate(self) -> None:
        rows = self.parsed.rows
        await self._begin(UploadStage.VALIDATE, len(rows))
        async with self.factory() as session:
            institution = await session.get(Institution, self.batch.institution_id)
            assert institution is not None
            ctx = await load_context(
                session,
                institution,
                self.batch.academic_year,
                upload_date(self.batch.created_at),
            )
        done = 0
        for part in chunks(rows):
            result = validate_rows(ParsedUpload(rows=list(part)), ctx)
            self.valid.extend(result.rows)
            self.rejected.update(result.rejected)
            done += len(part)

            async def work(session: AsyncSession, issues=result.issues) -> None:
                await self._write_issues(session, issues)

            await self._chunk(work, done)
        self._end()

    async def _file_duplicates(self) -> None:
        await self._begin(UploadStage.FILE_DUPLICATES, len(self.valid))
        result = file_duplicates(self.valid, self.engines.normalise_name)
        self.accepted = result.rows
        self.rejected.update(result.rejected)
        by_row: dict[int, list[RowIssue]] = {}
        for issue in result.issues:
            by_row.setdefault(issue.row_no, []).append(issue)
        done = 0
        for part in chunks(self.valid):
            done += len(part)
            issues = [i for row in part for i in by_row.get(row.row_no, [])]

            async def work(session: AsyncSession, issues=issues) -> None:
                await self._write_issues(session, issues)

            await self._chunk(work, done)
        accepted_rows = {row.row_no for row in self.accepted}
        self.counts["accepted"] = len(self.accepted)
        self.counts["errors"] = len(self.rejected)
        self.counts["warnings"] = len(self.warned & accepted_rows)
        self._end()

    async def _upsert(self) -> None:
        await self._begin(UploadStage.UPSERT, len(self.accepted))
        done = 0
        for part in chunks(self.accepted):
            done += len(part)

            async def work(session: AsyncSession, part=part) -> None:
                batch = await session.get(UploadBatch, self.batch_id)
                assert batch is not None
                result = await upsert_rows(
                    session, batch, part, engines=self.engines, actor_id=self.actor_id
                )
                await self._write_issues(session, result.issues)
                self.outcomes.extend(result.outcomes)
                for key in ("created", "updated", "unchanged", "withdrawn", "transferred"):
                    self.counts[key] += getattr(result, key)

            await self._chunk(work, done)
        accepted_rows = {row.row_no for row in self.accepted}
        self.counts["warnings"] = len(self.warned & accepted_rows)
        self._end()

    def _batch_enrolments(self) -> list[uuid.UUID]:
        return list(dict.fromkeys(o.enrolment_id for o in self.outcomes))

    async def _ledger(self) -> None:
        released = [o.enrolment_id for o in self.outcomes if o.released]
        ordered = list(dict.fromkeys(released + self._batch_enrolments()))
        await self._begin(UploadStage.LEDGER, len(ordered))
        done = 0
        for part in chunks(ordered):
            done += len(part)

            async def work(session: AsyncSession, part=part) -> None:
                result = await self.engines.assign_seats(session, part, actor_id=self.actor_id)
                self.counts["seated"] += len(result.seated)
                self.counts["released"] += len(result.released)
                self.seated.extend(result.seated)
                self.pools |= result.touched_pools
                self._tally(result.flags)

            await self._chunk(work, done)
        unseated = 0
        async with self.factory() as session:
            for part in chunks(ordered):
                unseated += (
                    await session.execute(
                        select(func.count()).where(
                            Enrolment.id.in_(part),
                            Enrolment.status == EnrolmentStatus.ACTIVE,
                            Enrolment.seat_id.is_(None),
                        )
                    )
                ).scalar_one()
        self.counts["unseated"] = unseated
        self._end()

    async def _check_set(self) -> list[uuid.UUID]:
        """Created and updated ACTIVE, newly seated, never checked, or still PENDING (§4.4)."""
        batch_ids = self._batch_enrolments()
        active = [o.enrolment_id for o in self.outcomes if o.status is EnrolmentStatus.ACTIVE]
        wanted = {
            o.enrolment_id
            for o in self.outcomes
            if o.outcome != "unchanged" and o.status is EnrolmentStatus.ACTIVE
        }
        wanted.update(self.seated)
        async with self.factory() as session:
            for part in chunks(list(dict.fromkeys(active))):
                unchecked = select(Enrolment.id).where(
                    Enrolment.id.in_(part),
                    ~exists().where(Check.enrolment_id == Enrolment.id),
                )
                pending = select(Check.enrolment_id).where(
                    Check.enrolment_id.in_(part),
                    Check.status == CheckStatus.PENDING,
                    Check.type != CheckType.STUDENT,
                )
                wanted.update((await session.execute(unchecked)).scalars())
                wanted.update((await session.execute(pending)).scalars())
        in_batch = set(batch_ids)
        ordered = [e for e in batch_ids if e in wanted]
        ordered += [e for e in dict.fromkeys(self.seated) if e not in in_batch]
        return ordered

    async def _checks(self) -> None:
        targets = await self._check_set()
        await self._begin(UploadStage.CHECKS, len(targets))
        done = 0
        for part in chunks(targets):
            done += len(part)

            async def work(session: AsyncSession, part=part) -> None:
                result = await self.engines.run_checks(
                    session,
                    part,
                    self.adapters,
                    concurrency=self.settings.checks_concurrency,
                    actor_id=self.actor_id,
                )
                self.checks.merge(result)
                self._tally(result.flags)

            await self._chunk(work, done)
        sources = set(self.checks.calls) | set(self.checks.unavailable)
        ordered = [s for s in SOURCE_ORDER if s in sources] + sorted(sources - set(SOURCE_ORDER))
        self.counts["sources"] = {
            s: {
                "calls": self.checks.calls.get(s, 0),
                "unavailable": self.checks.unavailable.get(s, 0),
            }
            for s in ordered
        }
        self._end()

    async def _duplicates(self) -> None:
        targets = list(
            dict.fromkeys(
                o.enrolment_id
                for o in self.outcomes
                if o.outcome != "unchanged" and o.status is EnrolmentStatus.ACTIVE
            )
        )
        await self._begin(UploadStage.DUPLICATES, len(targets))
        done = 0
        for part in chunks(targets):
            done += len(part)

            async def work(session: AsyncSession, part=part) -> None:
                result = await self.engines.detect_duplicates(
                    session,
                    self.batch.institution_id,
                    self.batch.academic_year,
                    part,
                    actor_id=self.actor_id,
                )
                self._tally(result.flags)

            await self._chunk(work, done)
        self._end()

    async def _flags(self) -> None:
        pools = sorted(self.pools, key=lambda p: (p.approval_id, p.seat_type.value))
        await self._begin(UploadStage.FLAGS, len(pools))
        if pools:

            async def work(session: AsyncSession) -> None:
                tally = await self.engines.refresh_seat_flags(
                    session, pools, actor_id=self.actor_id
                )
                self._tally(tally)

            await self._chunk(work, len(pools))


async def run_batch(
    batch_id: uuid.UUID,
    *,
    factory: async_sessionmaker[AsyncSession] | None = None,
    adapters: AdapterSet | None = None,
    engines: EngineSuite | None = None,
    source: Path | list[dict[str, Any]] | None = None,
) -> UploadBatch:
    """Run every stage for one batch and return it DONE or FAILED. Never raises for data."""
    own_adapters = adapters is None
    adapters = adapters if adapters is not None else build_adapters()
    try:
        run = _BatchRun(
            batch_id,
            factory or session_factory(),
            adapters,
            engines if engines is not None else default_engines(),
            source,
        )
        return await run.execute()
    finally:
        if own_adapters:
            await adapters.aclose()
