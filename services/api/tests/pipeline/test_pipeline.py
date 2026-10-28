"""run_batch: stage order, counts, chunked progress, failures and idempotency (ENGINES.md §4)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.factory import build_adapters
from app.db.session import get_engine, session_factory
from app.engine import pipeline
from app.engine.contracts import ChecksResult, FlagTally, LedgerResult, PoolRef
from app.engine.pipeline import progress_pct, run_batch
from app.engine.upload.spool import canonical_rows, find_spool, write_spool
from app.models.audit import AuditLog
from app.models.enums import (
    CheckStatus,
    CheckType,
    SeatType,
    UploadKind,
    UploadSource,
    UploadStage,
    UploadStatus,
)
from app.models.student import Enrolment
from app.models.upload import UploadBatch, UploadRowError
from app.models.verification import Check
from tests.pipeline.conftest import ROW, csv_bytes, new_batch, student_row
from tests.pipeline.fakes import FakeEngines, RecordingEngines

POOL_A = PoolRef(uuid.UUID("00000000-0000-4000-8000-00000000000a"), SeatType.REGULAR)
POOL_B = PoolRef(uuid.UUID("00000000-0000-4000-8000-00000000000a"), SeatType.NRI)
POOL_C = PoolRef(uuid.UUID("00000000-0000-4000-8000-000000000001"), SeatType.TFW)


async def run(
    rows: list[dict[str, Any]],
    tmp_path: Path,
    *,
    engines=None,
    batch=None,
    factory=None,
    name: str = "upload.csv",
    source: UploadSource = UploadSource.FILE,
    aicte_id: str = "1-ABC-0001",
) -> UploadBatch:
    batch = batch or await new_batch(aicte_id, source=source, filename=name)
    path = tmp_path / f"{uuid.uuid4().hex}-{name}"
    path.write_bytes(csv_bytes(rows))
    return await run_batch(
        batch.id,
        factory=factory,
        adapters=build_adapters(),
        engines=engines or FakeEngines(),
        source=path,
    )


async def scalar(stmt):
    async with session_factory()() as session:
        return (await session.execute(stmt)).scalar_one()


async def enrolment_ids(*where) -> list[uuid.UUID]:
    async with session_factory()() as session:
        stmt = select(Enrolment.id, Enrolment.source_row_no).where(*where)
        return [eid for eid, _ in sorted((await session.execute(stmt)).all(), key=lambda r: r[1])]


def test_progress_pct():
    pct = progress_pct
    assert pct(UploadStatus.QUEUED, None, 0, 0) == 0
    assert pct(UploadStatus.VALIDATING, UploadStage.PARSE, 0, 0) == 0
    assert pct(UploadStatus.VALIDATING, UploadStage.PARSE, 10, 10) == 5
    assert pct(UploadStatus.VALIDATING, UploadStage.VALIDATE, 500, 1000) == 10
    assert pct(UploadStatus.PROCESSING, UploadStage.UPSERT, 0, 0) == 20
    assert pct(UploadStatus.PROCESSING, UploadStage.CHECKS, 1, 3) == 45 + 15
    assert pct(UploadStatus.PROCESSING, UploadStage.FLAGS, 2, 2) == 100
    assert pct(UploadStatus.FAILED, UploadStage.LEDGER, 500, 1000) == 40
    assert pct(UploadStatus.DONE, UploadStage.DONE, 0, 0) == 100


async def test_stages_counts_and_engine_calls(world, tmp_path):
    engines = RecordingEngines(pools=[POOL_A, POOL_C, POOL_B])
    rows = [
        ROW,
        student_row(1, mobile="123"),  # accepted with a warning
        student_row(2, programme_code="ME"),  # rejected
        student_row(3, apaar_id=ROW["apaar_id"]),  # same APAAR as row 2: rejected
        student_row(4, status="WITHDRAWN"),  # new and withdrawn: no seat, a warning
        dict(student_row(5), Remarks="x"),
    ]
    batch = await run(rows, tmp_path, engines=engines)
    assert batch.status is UploadStatus.DONE and batch.stage is UploadStage.DONE
    assert (batch.total_rows, batch.stage_total, batch.processed_rows) == (6, 0, 0)
    assert batch.error is None and batch.finished_at is not None and batch.started_at is not None
    counts = batch.counts
    assert {k: counts[k] for k in ("rows", "accepted", "errors", "warnings")} == {
        "rows": 6,
        "accepted": 4,
        "errors": 2,
        "warnings": 2,
    }
    assert (counts["created"], counts["updated"], counts["unchanged"]) == (4, 0, 0)
    assert (counts["withdrawn"], counts["transferred"]) == (1, 0)
    assert (counts["seated"], counts["released"], counts["unseated"]) == (0, 0, 3)
    assert (counts["flags_raised"], counts["flags_updated"]) == (3, 0)  # one per refreshed pool
    assert counts["sources"] == {}
    assert set(counts["timings_ms"]) == {s.value for s in pipeline.STAGES}

    ids = await enrolment_ids(Enrolment.upload_batch_id == batch.id)
    assert len(ids) == 4
    active = [ids[0], ids[1], ids[3]]
    assert engines.calls["assign_seats"] == [ids]
    assert engines.calls["run_checks"] == [active]
    assert engines.calls["detect_duplicates"] == [active]
    assert engines.calls["refresh_seat_flags"] == [[POOL_C, POOL_B, POOL_A]]
    assert all(actors == {batch.uploaded_by} for actors in engines.actors.values())

    async with session_factory()() as session:
        errors = (
            await session.execute(
                select(UploadRowError).where(UploadRowError.batch_id == batch.id)
                .order_by(UploadRowError.row_no, UploadRowError.field)
            )
        ).scalars().all()  # fmt: skip
        entry = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "upload_batch", AuditLog.action == "UPDATE"
                )
            )
        ).scalar_one()
    assert [(e.row_no, e.level.value, e.code) for e in errors] == [
        (3, "WARNING", "MOBILE_FORMAT"),
        (4, "ERROR", "UNKNOWN_PROGRAMME"),
        (5, "ERROR", "DUPLICATE_IN_FILE"),
        (6, "WARNING", "NOT_PREVIOUSLY_ENROLLED"),
    ]
    assert errors[0].value_masked == "<3 characters>" and errors[2].value_masked.endswith("4417")
    assert entry.actor_id == batch.uploaded_by
    assert entry.after["status"] == "DONE" and "sources" not in entry.after["counts"]
    assert batch.ignored_columns == []


async def test_reupload_is_idempotent_and_rechecks_only_pending(world, tmp_path):
    rows = [student_row(n) for n in range(1, 6)]
    first = await run(rows, tmp_path)
    ids = await enrolment_ids(Enrolment.upload_batch_id == first.id)
    async with session_factory()() as session:
        for index, eid in enumerate(ids[:4]):
            for check_type in CheckType:
                status = CheckStatus.PASS
                if index == 1 and check_type is CheckType.IDENTITY:
                    status = CheckStatus.PENDING  # a source was down: retried
                if check_type is CheckType.STUDENT:
                    status = CheckStatus.PENDING  # only the student loop changes it
                session.add(
                    Check(enrolment_id=eid, type=check_type, status=status, source="X", detail={})
                )
        await session.commit()
    audit_before = await scalar(select(func.count()).select_from(AuditLog))

    engines = RecordingEngines()
    again = await run(rows, tmp_path, engines=engines)
    assert again.status is UploadStatus.DONE
    c = again.counts
    assert (c["created"], c["updated"], c["unchanged"], c["seated"], c["flags_raised"]) == (
        0,
        0,
        5,
        0,
        0,
    )
    assert engines.calls["assign_seats"] == [ids]
    assert engines.calls["run_checks"] == [[ids[1], ids[4]]]  # PENDING identity, never checked
    assert engines.calls["detect_duplicates"] == []
    assert engines.calls["refresh_seat_flags"] == []
    # no student or enrolment writes: only the new batch's CREATE and UPDATE entries
    assert await scalar(select(func.count()).select_from(AuditLog)) == audit_before + 2
    assert again.kind is UploadKind.UPDATE and first.kind is UploadKind.INITIAL


async def test_releases_go_to_the_ledger_first(world, tmp_path):
    rows = [student_row(n) for n in range(1, 5)]
    first = await run(rows, tmp_path)
    ids = await enrolment_ids(Enrolment.upload_batch_id == first.id)
    seated_elsewhere = uuid.uuid4()

    async def ledger(session, chunk):
        return LedgerResult(seated=[seated_elsewhere], released=[chunk[0]])

    engines = RecordingEngines(ledger=ledger)
    update = [student_row(1), student_row(2), student_row(4, status="WITHDRAWN")]
    batch = await run(update, tmp_path, engines=engines)
    assert engines.calls["assign_seats"] == [[ids[3], ids[0], ids[1]]]
    assert (batch.counts["withdrawn"], batch.counts["released"]) == (1, 1)
    assert batch.counts["seated"] == 1
    # the backlog enrolment that got a seat is re-checked after the batch's own rows
    assert engines.calls["run_checks"] == [[ids[0], ids[1], seated_elsewhere]]
    assert engines.calls["detect_duplicates"] == []  # the withdrawn one is not ACTIVE


async def test_checks_report_sources_and_flags(world, tmp_path):
    async def checks(session, chunk):
        return ChecksResult(
            enrolments=len(chunk),
            calls={"SII": 1, "APAAR": len(chunk), "ABC": 2},
            unavailable={"APAAR": 1},
            flags=FlagTally(created=2, updated=1),
        )

    batch = await run([ROW, student_row(1)], tmp_path, engines=RecordingEngines(checks=checks))
    assert batch.counts["sources"] == {
        "APAAR": {"calls": 2, "unavailable": 1},
        "ABC": {"calls": 2, "unavailable": 0},
        "SII": {"calls": 1, "unavailable": 0},
    }
    assert (batch.counts["flags_raised"], batch.counts["flags_updated"]) == (2, 1)


class _Observed(AsyncSession):
    """Records the batch's progress, read on another connection, after every commit."""

    seen: list[tuple[str, str | None, int, int, int, int]] = []

    async def commit(self) -> None:
        await super().commit()
        async with session_factory()() as other:
            batch = (await other.execute(select(UploadBatch))).scalars().first()
            enrolments = (
                await other.execute(select(func.count()).select_from(Enrolment))
            ).scalar_one()
        if batch is not None:
            _Observed.seen.append(
                (
                    batch.status.value,
                    batch.stage.value if batch.stage else None,
                    batch.processed_rows,
                    batch.stage_total,
                    progress_pct(
                        batch.status, batch.stage, batch.processed_rows, batch.stage_total
                    ),
                    enrolments,
                )
            )


async def test_progress_is_committed_per_chunk_and_never_goes_back(world, tmp_path):
    _Observed.seen = []
    factory = async_sessionmaker(get_engine(), class_=_Observed, expire_on_commit=False)
    rows = [student_row(n) for n in range(1, 1201)]
    batch = await run(rows, tmp_path, factory=factory)
    assert batch.status is UploadStatus.DONE and batch.counts["created"] == 1200
    seen = _Observed.seen
    percents = [p for *_, p, _ in seen]
    assert percents == sorted(percents) and percents[-1] == 100
    upserts = [(done, total, n) for _, stage, done, total, _, n in seen if stage == "UPSERT"]
    assert [done for done, _, _ in upserts] == [0, 500, 1000, 1200]
    assert all(total == 1200 and n == done for done, total, n in upserts)  # never ahead
    validating = [done for status, stage, done, *_ in seen if stage == "VALIDATE"]
    assert validating == [0, 500, 1000, 1200]
    assert {status for status, stage, *_ in seen if stage == "VALIDATE"} == {"VALIDATING"}
    assert {status for status, stage, *_ in seen if stage == "LEDGER"} == {"PROCESSING"}


async def test_a_stage_exception_fails_the_batch_and_keeps_saved_chunks(world, tmp_path, caplog):
    rows = [student_row(n) for n in range(1, 1201)]
    engines = RecordingEngines(fail_in="assign_seats", fail_after_calls=1)
    batch = await run(rows, tmp_path, engines=engines)
    assert batch.status is UploadStatus.FAILED and batch.stage is UploadStage.LEDGER
    assert batch.error == (
        "Processing stopped while assigning seats. Upload the file again; rows already saved "
        "are kept."
    )
    assert batch.processed_rows == 500 and batch.stage_total == 1200
    assert progress_pct(batch.status, batch.stage, batch.processed_rows, batch.stage_total) == 39
    assert batch.finished_at is not None and batch.counts["created"] == 1200
    assert len(engines.calls["assign_seats"]) == 2 and engines.calls["run_checks"] == []
    assert await scalar(select(func.count()).select_from(Enrolment)) == 1200
    assert "upload stage failed" in caplog.text
    async with session_factory()() as session:
        entry = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "upload_batch", AuditLog.action == "UPDATE"
                )
            )
        ).scalar_one()
    assert entry.after["status"] == "FAILED" and entry.after["stage"] == "LEDGER"
    assert "Ravi" not in str(entry.after) and "123456784417" not in str(entry.after)

    # uploading the file again finishes the job
    retry = RecordingEngines()
    again = await run(rows, tmp_path, engines=retry)
    assert again.status is UploadStatus.DONE and again.counts["unchanged"] == 1200
    assert sum(len(c) for c in retry.calls["run_checks"]) == 1200  # none were checked yet


class _BreaksInUpsert(FakeEngines):
    def name_key(self, name: str, dob: date) -> str:
        if name == "Student Number 0700":
            raise ValueError("cannot key Student Number 0700")
        return super().name_key(name, dob)


async def test_an_upsert_chunk_failure_keeps_earlier_chunks(world, tmp_path):
    rows = [student_row(n) for n in range(1, 1001)]
    batch = await run(rows, tmp_path, engines=_BreaksInUpsert())
    assert batch.status is UploadStatus.FAILED and batch.stage is UploadStage.UPSERT
    assert batch.error.startswith("Processing stopped while saving students and enrolments.")
    assert batch.processed_rows == 500
    assert await scalar(select(func.count()).select_from(Enrolment)) == 500


async def test_file_level_failures_in_parse(world, tmp_path):
    bad = await new_batch()
    path = tmp_path / "bad.csv"
    path.write_text("name,dob\nRavi,2007-03-21\n")
    batch = await run_batch(bad.id, engines=FakeEngines(), source=path)
    assert batch.status is UploadStatus.FAILED and batch.stage is UploadStage.PARSE
    assert batch.error == (
        "The file is missing required columns: programme_code, year_of_study, admission_route, "
        "category."
    )
    missing = await new_batch()
    batch = await run_batch(missing.id, engines=FakeEngines())  # no spool file
    assert batch.error == "The file could not be read as CSV or XLSX."
    # a finished batch is returned as it is
    assert (await run_batch(missing.id, engines=FakeEngines())).status is UploadStatus.FAILED


async def test_spooled_file_and_rows(world, spool):
    batch = await new_batch()
    write_spool(batch.id, "csv", csv_bytes([ROW]))
    assert find_spool(batch.id) is not None
    assert b"Ravi" not in next(spool.iterdir()).read_bytes()  # encrypted at rest
    done = await run_batch(batch.id, engines=FakeEngines())
    assert done.status is UploadStatus.DONE and done.counts["created"] == 1
    assert find_spool(batch.id) is None

    api = await new_batch(source=UploadSource.API, filename="rows.json")
    rows = [dict(student_row(9), year_of_study=1, sis_id="A1")]
    write_spool(api.id, "json", canonical_rows(rows))
    done = await run_batch(api.id, engines=FakeEngines())
    assert done.status is UploadStatus.DONE and done.counts["created"] == 1
    assert done.ignored_columns == ["sis_id"] and find_spool(api.id) is None


async def test_seed_batches_run_as_the_system(world, tmp_path):
    engines = RecordingEngines(pools=[POOL_A])
    batch = await run([ROW], tmp_path, engines=engines, source=UploadSource.SEED)
    assert batch.status is UploadStatus.DONE
    assert all(actors == {None} for actors in engines.actors.values())


def test_default_engines_fall_back_until_the_engine_modules_exist(monkeypatch):
    real_import = pipeline.importlib.import_module

    def missing(name: str):
        if name == "app.engine.ledger":
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import(name)

    monkeypatch.setattr(pipeline.importlib, "import_module", missing)
    fallback = pipeline.default_engines()
    assert isinstance(fallback, pipeline.UploadOnlyEngines)
    assert fallback.normalise_name("Shri. R. K. Sharma") == "shri r k sharma"
    assert fallback.name_key("R. K. Sharma", date(2007, 3, 21)) == "2007-03-21|r|XRM"

    def broken(name: str):
        raise ModuleNotFoundError("No module named 'numpy'", name="numpy")

    monkeypatch.setattr(pipeline.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        pipeline.default_engines()
