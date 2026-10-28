"""The seed importer (API_CONTRACT §A4.25): a college's column mapping is saved before its
first upload, and each SEED batch and its versions carry the manifest's `submitted_at`."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.session import session_factory
from app.engine.upload import mapping as column_mapping
from app.models.audit import AuditLog
from app.models.institution import Institution
from app.models.student import EnrolmentVersion
from app.models.upload import UploadBatch
from app.seed.importer import SeedError, import_directory
from tests.conftest import FIXTURE_DIR, truncate_all
from tests.decisions.test_column_mapping import HEADERS, THEIRS, row

SUBMITTED = "2026-09-22T06:30:00Z"


def write_generated(root: Path, *, with_mapping: bool) -> None:
    (root / "uploads").mkdir(parents=True)
    (root / "institutions.json").write_text(
        (FIXTURE_DIR / "institutions.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    staff = [
        u
        for u in json.loads((FIXTURE_DIR / "users.json").read_text(encoding="utf-8"))
        if u["role"] != "STUDENT"
    ]
    (root / "users.json").write_text(json.dumps(staff), encoding="utf-8")
    with (root / "uploads" / "1-ABC-0001_2026-27.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writeheader()
        for n in range(1, 4):
            writer.writerow(row(n))
    manifest = {
        "uploads": [
            {
                "file": "uploads/1-ABC-0001_2026-27.csv",
                "aicte_id": "1-ABC-0001",
                "academic_year": "2026-27",
                "submitted_at": SUBMITTED,
            }
        ]
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if with_mapping:
        (root / "column_mappings.json").write_text(
            json.dumps({"1-ABC-0001": THEIRS}), encoding="utf-8"
        )


async def test_the_seed_maps_columns_first_and_dates_its_batches(tmp_path) -> None:
    await truncate_all()
    try:
        write_generated(tmp_path, with_mapping=True)
        summary = await import_directory(session_factory(), tmp_path)
        assert [u.status for u in summary.uploads] == ["DONE"]
        assert summary.counts["column_mappings"].created == 1
        submitted = datetime(2026, 9, 22, 6, 30, tzinfo=UTC)
        async with session_factory()() as session:
            abc = (
                await session.execute(
                    select(Institution).where(Institution.aicte_permanent_id == "1-ABC-0001")
                )
            ).scalar_one()
            assert await column_mapping.load(session, abc.id) == THEIRS
            batch = (await session.execute(select(UploadBatch))).scalar_one()
            stored = (await session.execute(select(EnrolmentVersion))).scalars().all()
            seeded = (
                await session.execute(
                    select(AuditLog).where(AuditLog.entity_type == "institution_column_mapping")
                )
            ).scalar_one()
        assert batch.created_at == submitted
        assert batch.counts["versions"] == 3 and batch.counts["column_mapping"]
        assert {(v.source, v.at, v.actor_id) for v in stored} == {("SEED", submitted, None)}
        assert (seeded.action.value, seeded.actor_id) == ("SEED", None)

        # a second run finds the mapping and the file already in place
        again = await import_directory(session_factory(), tmp_path)
        assert again.counts["column_mappings"].existing == 1
        assert [u.status for u in again.uploads] == ["SKIPPED"]
    finally:
        await truncate_all()


async def test_without_the_mapping_the_college_file_is_refused(tmp_path) -> None:
    await truncate_all()
    try:
        write_generated(tmp_path, with_mapping=False)
        with pytest.raises(SeedError) as caught:
            await import_directory(session_factory(), tmp_path)
        assert "Map them to the template once" in str(caught.value)
    finally:
        await truncate_all()
