"""CHECKS chunks spread over worker processes give the same rows, cases, statuses, counts and
audit chain as the same batch checked in one process.

The worker processes are spawned, so they read the test settings from the environment
(in-memory sources with empty registries, like the parent's here) and the test database.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app.core.audit import verify_chain
from app.core.rules import get_rules
from app.db.session import session_factory
from app.engine import pipeline
from app.models.enums import UploadStatus
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.verification import Check, Flag
from app.seed.importer import STAFF_ROLES, Summary, import_institutions, import_users
from tests.conftest import FIXTURE_DIR, truncate_all
from tests.pipeline.conftest import csv_bytes, new_batch, student_row


async def _fresh_world() -> None:
    await truncate_all()
    summary = Summary()
    async with session_factory()() as session:
        await import_institutions(session, FIXTURE_DIR / "institutions.json", get_rules(), summary)
        await import_users(session, FIXTURE_DIR / "users.json", summary, roles=STAFF_ROLES)
        await session.commit()


async def _run(path: Path, monkeypatch, *, spread: bool) -> dict:
    await _fresh_world()
    monkeypatch.setattr(pipeline, "CHUNK_SIZE", 4)
    monkeypatch.setattr(pipeline, "PARALLEL_CHECK_CHUNKS", 2)
    monkeypatch.setattr(pipeline, "CHECK_PROCESSES", 2)
    monkeypatch.setattr(pipeline, "can_spread", lambda *_: spread)
    batch = await new_batch()
    done = await pipeline.run_batch(batch.id, source=path)
    async with session_factory()() as session:
        rows = (
            await session.execute(
                select(Student.name, Check.type, Check.status, Check.detail)
                .join(Enrolment, Enrolment.student_id == Student.id)
                .join(Check, Check.enrolment_id == Enrolment.id)
            )
        ).all()
        statuses = (
            await session.execute(
                select(Student.name, Enrolment.record_status, Enrolment.status_reason).join(
                    Enrolment, Enrolment.student_id == Student.id
                )
            )
        ).all()
        cases = (
            await session.execute(
                select(Flag.type, Flag.severity, func.count()).group_by(Flag.type, Flag.severity)
            )
        ).all()
        progress = (
            await session.execute(
                select(UploadBatch.processed_rows, UploadBatch.stage_total).where(
                    UploadBatch.id == batch.id
                )
            )
        ).one()
        chain = await verify_chain(session)
    return {
        "batch": done,
        "rows": {(name, t.value): (s.value, detail) for name, t, s, detail in rows},
        "statuses": {name: (status.value, reason) for name, status, reason in statuses},
        "cases": sorted((t.value, sev.value, n) for t, sev, n in cases),
        "progress": progress,
        "chain": chain,
    }


async def test_spread_checks_match_one_process(tmp_path, monkeypatch):
    rows = [student_row(n) for n in range(1, 14)]
    rows.append(student_row(14, apaar_id="12345"))  # malformed: a case from the checks
    rows.append(student_row(15, year_of_study="2", admission_route="MANAGEMENT"))
    path = tmp_path / "upload.csv"
    path.write_bytes(csv_bytes(rows))

    one = await _run(path, monkeypatch, spread=False)
    spread = await _run(path, monkeypatch, spread=True)
    await truncate_all()

    for run in (one, spread):
        assert run["batch"].status is UploadStatus.DONE, run["batch"].error
        assert run["chain"][0] is True
        assert run["progress"] == (0, 0)
    assert len(spread["rows"]) == 5 * len(rows)
    assert spread["rows"] == one["rows"]
    assert spread["statuses"] == one["statuses"]
    assert spread["cases"] == one["cases"] and spread["cases"]
    for key in ("sources", "flags_raised", "flags_updated", "created", "seated"):
        assert spread["batch"].counts[key] == one["batch"].counts[key], key


def test_spreading_needs_the_settings_database_and_mockgov(monkeypatch):
    from app.adapters.base import AdapterSet
    from app.core.config import get_settings

    settings = get_settings()
    factory = session_factory()
    mockgov = AdapterSet("mockgov", None, None, None, None, None)
    inmemory = AdapterSet("inmemory", None, None, None, None, None)
    monkeypatch.setattr(settings, "gov_adapter", "mockgov")
    assert pipeline.can_spread(factory, mockgov, settings)
    assert not pipeline.can_spread(factory, inmemory, settings)
    monkeypatch.setattr(settings, "api_db_name", "another_database")
    assert not pipeline.can_spread(factory, mockgov, settings)
