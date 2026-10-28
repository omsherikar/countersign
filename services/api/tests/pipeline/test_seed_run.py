"""make seed sends every datagen upload through run_batch, initial files first (D22, §A2.24)."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select

from app.db.session import session_factory
from app.models.student import Enrolment, Student
from app.seed.importer import SeedError, import_directory, upload_files
from tests.conftest import FIXTURE_DIR, truncate_all
from tests.pipeline.fakes import RecordingEngines


@pytest.fixture
async def empty() -> AsyncIterator[None]:
    await truncate_all()
    yield
    await truncate_all()


def test_upload_files_are_ordered_initial_first(tmp_path):
    for name in (
        "1-XYZ-0002_2026-27_update1.csv",
        "1-ABC-0001_2026-27_update10.csv",
        "1-XYZ-0002_2026-27.csv",
        "1-ABC-0001_2026-27_update2.csv",
        "1-ABC-0001_2026-27.csv",
        "1-ABC-0001_2026-27.xlsx",
    ):
        (tmp_path / name).write_text("x")
    assert [p.name for p in upload_files(tmp_path)] == [
        "1-ABC-0001_2026-27.csv",
        "1-XYZ-0002_2026-27.csv",
        "1-ABC-0001_2026-27_update2.csv",
        "1-ABC-0001_2026-27_update10.csv",
        "1-XYZ-0002_2026-27_update1.csv",
    ]
    (tmp_path / "notes.csv").write_text("x")
    with pytest.raises(SeedError):
        upload_files(tmp_path)


async def test_seed_runs_every_file_through_the_engines(empty):
    engines = RecordingEngines()
    summary = await import_directory(session_factory(), FIXTURE_DIR, engines=engines)
    assert [u.status for u in summary.uploads] == ["DONE"] * 4
    # one ledger call per file; the seed acts as the system
    assert len(engines.calls["assign_seats"]) == 4
    assert engines.actors["assign_seats"] == {None} and engines.actors["run_checks"] == {None}

    async with session_factory()() as session:
        rows = (
            await session.execute(
                select(Student.name, Enrolment.id).join(
                    Enrolment, Enrolment.student_id == Student.id
                )
            )
        ).all()
    ids = {name: eid for name, eid in rows}
    update_ledger = engines.calls["assign_seats"][-1]
    # releases reach the ledger before anything else in the update file
    assert update_ledger[:2] == [ids["Prajwal Shetty"], ids["Kiran Kumar"]]
    assert set(update_ledger[2:]) == {ids["Yashas Gowda"], ids["Nandini Rao"]}
    assert engines.calls["run_checks"][-1] == [ids["Yashas Gowda"], ids["Nandini Rao"]]


async def test_a_bad_seed_file_stops_the_seed(empty, tmp_path):
    import shutil

    shutil.copytree(FIXTURE_DIR, tmp_path / "data")
    (tmp_path / "data" / "uploads" / "1-ABC-0001_2026-27.csv").write_text("name,dob\nA,2007\n")
    with pytest.raises(SeedError, match="missing required columns"):
        await import_directory(session_factory(), tmp_path / "data")


async def test_in_memory_sources_get_the_generated_registries():
    from datetime import date

    from app.adapters.factory import build_adapters
    from app.core.config import get_settings
    from app.seed.importer import load_inmemory_registries

    adapters = build_adapters(get_settings())
    load_inmemory_registries(adapters, FIXTURE_DIR / "mockgov")
    ravi = await adapters.apaar.verify("123456784417", "ravi kumar sharma", date(2007, 3, 21))
    assert ravi.exists and ravi.dob_match and ravi.name_score == 100
    allotted = await adapters.counselling.verify(
        state="MH", year=2026, name="Ravi Kumar Sharma", dob=date(2007, 3, 21), programme="CSE"
    )
    assert allotted.found and allotted.allotment_ref == "MHCET-2026-R1-004512"
    credits = await adapters.abc.credits("202600000109", "2025-26")
    assert credits.apaar_id_known and [s.credits for s in credits.semesters] == [22, 24]
    assert (await adapters.sii.verify("N1234567", "aisha rahman", "BD")).admitted
