"""institutions.json approval versions -> approval_versions (migration 0004).

The table arrives with migration 0004. Until the models declare it the importer leaves the
versions alone; the helper is exercised now against a stand-in table of the planned shape,
and the end-to-end test runs once the real table exists.
"""

import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.rules import get_rules
from app.db.base import Base
from app.db.session import session_factory
from app.models.institution import Approval, Institution, Programme
from app.seed.importer import Summary, _import_approval_versions, import_directory
from tests.conftest import FIXTURE_DIR

HAS_TABLE = "approval_versions" in Base.metadata.tables
VERSIONS = [
    {
        "version": 1,
        "approved_intake": 120,
        "effective_from": "2026-05-15",
        "source": "AICTE approval 2026-27 (sample approval data)",
    },
    {
        "version": 2,
        "approved_intake": 150,
        "effective_from": "2026-10-21",
        "source": "AICTE revised approval 2026-27, intake 120 to 150 (sample approval data)",
    },
]


def institutions_with_versions(tmp_path: Path) -> Path:
    """The mini fixture's institutions.json only, ABC CSE 2026-27 raised by a version 2."""
    folder = tmp_path / "generated"
    folder.mkdir()
    data = json.loads((FIXTURE_DIR / "institutions.json").read_text(encoding="utf-8"))
    for inst in data["institutions"]:
        for prog in inst["programmes"]:
            for approval in prog["approvals"]:
                year = approval["academic_year"]
                approval["versions"] = [
                    {
                        "version": 1,
                        "approved_intake": approval["approved_intake"],
                        "effective_from": f"{year[:4]}-05-15",
                        "source": f"AICTE approval {year} (sample approval data)",
                    }
                ]
                if (inst["aicte_permanent_id"], prog["code"], year) == (
                    "1-ABC-0001",
                    "CSE",
                    "2026-27",
                ):
                    approval["versions"] = VERSIONS
                    approval["approved_intake"] = 150
    (folder / "institutions.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


async def abc_cse_2026(session) -> Approval:
    return (
        await session.execute(
            select(Approval)
            .join(Programme, Approval.programme_id == Programme.id)
            .join(Institution, Programme.institution_id == Institution.id)
            .where(
                Institution.aicte_permanent_id == "1-ABC-0001",
                Programme.code == "CSE",
                Approval.academic_year == "2026-27",
            )
        )
    ).scalar_one()


def stand_in() -> Table:
    """approval_versions as migration 0004 plans it, in a metadata of its own."""
    return Table(
        "approval_versions",
        MetaData(),
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("approval_id", UUID(as_uuid=True), nullable=False),
        Column("version", Integer, nullable=False),
        Column("approved_intake", Integer, nullable=False),
        Column("effective_from", Date, nullable=False),
        Column("source", Text, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("approval_id", "version"),
    )


@pytest.mark.skipif(HAS_TABLE, reason="the real approval_versions table is covered below")
async def test_versions_are_upserted_into_the_planned_table(clean_db, tmp_path: Path):
    folder = institutions_with_versions(tmp_path)
    table = stand_in()
    engine = session_factory().kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(table.metadata.create_all)
    try:
        await import_directory(session_factory(), folder)
        summary = Summary()
        async with session_factory()() as session:
            approval = await abc_cse_2026(session)
            assert approval.approved_intake == 150
            await _import_approval_versions(session, approval, VERSIONS, summary, table=table)
            await session.commit()
            rows = (
                await session.execute(
                    select(table).where(table.c.approval_id == approval.id).order_by("version")
                )
            ).all()
        assert [(r.version, r.approved_intake, r.effective_from) for r in rows] == [
            (1, 120, date(2026, 5, 15)),
            (2, 150, date(2026, 10, 21)),
        ]
        assert all(isinstance(r.id, uuid.UUID) and r.created_at for r in rows)
        assert summary.counts["approval_versions"].created == 2

        # A second run updates in place: one row per version, nothing new.
        again = Summary()
        changed = [VERSIONS[0], {**VERSIONS[1], "approved_intake": 180}]
        async with session_factory()() as session:
            approval = await abc_cse_2026(session)
            await _import_approval_versions(session, approval, changed, again, table=table)
            await session.commit()
            count = await session.scalar(select(func.count()).select_from(table))
            intake = await session.scalar(
                select(table.c.approved_intake).where(table.c.version == 2)
            )
        assert (count, intake) == (2, 180)
        assert again.counts["approval_versions"].existing == 2
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.drop_all)


@pytest.mark.skipif(HAS_TABLE, reason="the table exists; versions are imported")
async def test_versions_wait_for_the_table(clean_db, tmp_path: Path):
    summary = await import_directory(session_factory(), institutions_with_versions(tmp_path))
    assert "approval_versions" not in summary.counts
    assert summary.counts["approvals"].created == 8
    async with session_factory()() as session:
        assert (await abc_cse_2026(session)).approved_intake == 150


@pytest.mark.skipif(not HAS_TABLE, reason="approval_versions arrives with migration 0004")
async def test_versions_are_imported_with_the_current_version(clean_db, tmp_path: Path):
    folder = institutions_with_versions(tmp_path)
    summary = await import_directory(session_factory(), folder)
    table = Base.metadata.tables["approval_versions"]
    assert summary.counts["approval_versions"].created == 9  # 8 approvals, one with v2
    async with session_factory()() as session:
        approval = await abc_cse_2026(session)
        rows = (
            await session.execute(
                select(table.c.version, table.c.approved_intake)
                .where(table.c.approval_id == approval.id)
                .order_by(table.c.version)
            )
        ).all()
        assert [tuple(r) for r in rows] == [(1, 120), (2, 150)]
        assert approval.approved_intake == 150
        if "current_version" in Approval.__table__.c:
            assert approval.current_version == 2
    again = await import_directory(session_factory(), folder)
    assert again.counts["approval_versions"].created == 0
    get_rules()  # the rules the seat pools were built from are still loadable
