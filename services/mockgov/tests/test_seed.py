import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed
from app.config import Settings
from app.models import (
    AbcCredit,
    ApaarRecord,
    CounsellingAllotment,
    DigiLockerAccount,
    DigiLockerMessage,
    SiiAdmission,
)
from tests.conftest import FIXTURES

EXPECTED = {
    "apaar_registry": 4,
    "counselling_allotments": 3,
    "abc_credits": 3,
    "sii_admissions": 2,
    "admission_joinings": 5,
    "digilocker_accounts": 4,
}


async def count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_seed_loads_every_registry(app: FastAPI, settings: Settings) -> None:
    summary = await seed.run(FIXTURES, reset=False, settings=settings)
    assert summary == {table: {"read": n, "total": n} for table, n in EXPECTED.items()}


async def test_seed_normalises_names_and_parses_types(
    app: FastAPI, settings: Settings, session: AsyncSession
) -> None:
    await seed.run(FIXTURES, reset=False, settings=settings)
    record = await session.get(ApaarRecord, "123456780004")
    assert record is not None
    assert record.name == "Dr. Anil S. Deshmukh"
    assert record.name_normalized == "anil s deshmukh"
    assert record.dob.isoformat() == "2005-08-30"
    assert record.gender is None

    credit = await session.scalar(select(AbcCredit).where(AbcCredit.apaar_id == "123456780003"))
    assert credit.uploaded_at.isoformat() == "2026-01-20T00:00:00+00:00"


async def test_seed_is_idempotent(app: FastAPI, settings: Settings, session: AsyncSession) -> None:
    first = await seed.run(FIXTURES, reset=False, settings=settings)
    second = await seed.run(FIXTURES, reset=False, settings=settings)
    assert second == first
    assert await count(session, CounsellingAllotment) == EXPECTED["counselling_allotments"]


async def test_seed_upserts_changed_rows(
    app: FastAPI, settings: Settings, session: AsyncSession, tmp_path: Path
) -> None:
    await seed.run(FIXTURES, reset=False, settings=settings)

    changed = tmp_path / "mockgov"
    shutil.copytree(FIXTURES, changed)
    registry = changed / "apaar_registry.jsonl"
    rows = [json.loads(line) for line in registry.read_text().splitlines()]
    rows[0]["name"] = "Ravi K. Sharma"
    rows.append({"apaar_id": "123456780005", "name": "New Person", "dob": "2008-02-02"})
    registry.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    summary = await seed.run(changed, reset=False, settings=settings)
    assert summary["apaar_registry"] == {"read": 5, "total": 5}
    session.expire_all()
    ravi = await session.get(ApaarRecord, "123456784417")
    assert ravi.name_normalized == "ravi k sharma"


async def test_duplicate_key_within_a_file_keeps_the_last_row(
    app: FastAPI, settings: Settings, session: AsyncSession, tmp_path: Path
) -> None:
    folder = tmp_path / "mockgov"
    folder.mkdir()
    base = {"nationality": "NP", "institution_aicte_id": "1-A-1", "academic_year": "2026-27"}
    lines = [
        {**base, "passport_no": "P1", "name": "First", "programme": "CSE"},
        {**base, "passport_no": "P1", "name": "Second", "programme": "ECE"},
    ]
    (folder / "sii.jsonl").write_text("\n".join(json.dumps(r) for r in lines) + "\n")

    summary = await seed.run(folder, reset=False, settings=settings)
    assert summary["sii_admissions"] == {"read": 2, "total": 1}
    assert summary["apaar_registry"] == {"read": None, "total": 0}
    row = await session.scalar(select(SiiAdmission).where(SiiAdmission.passport_no == "P1"))
    assert row.programme == "ECE"


async def test_reset_rebuilds_the_tables_and_empties_the_inbox(
    app: FastAPI, settings: Settings, session: AsyncSession, tmp_path: Path
) -> None:
    await seed.run(FIXTURES, reset=False, settings=settings)
    session.add(
        DigiLockerMessage(
            inbox_id="ib_TEST",
            apaar_id="123456784417",
            message="m",
            callback_url="u",
            received_at=datetime.now(UTC),
        )
    )
    await session.commit()

    only_sii = tmp_path / "mockgov"
    only_sii.mkdir()
    shutil.copy(FIXTURES / "sii.jsonl", only_sii / "sii.jsonl")
    summary = await seed.run(only_sii, reset=True, settings=settings)

    assert summary["apaar_registry"] == {"read": None, "total": 0}
    assert summary["sii_admissions"] == {"read": 2, "total": 2}
    assert await count(session, DigiLockerMessage) == 0


async def test_missing_directory_fails(settings: Settings, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await seed.run(tmp_path / "nope", reset=False, settings=settings)


async def test_invalid_json_fails_with_line_number(
    app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    folder = tmp_path / "mockgov"
    folder.mkdir()
    good = '{"apaar_id": "123456780009", "name": "Ok Person", "dob": "2007-01-01"}\n'
    (folder / "apaar_registry.jsonl").write_text(good + "not json\n")
    with pytest.raises(ValueError, match="apaar_registry.jsonl:2: invalid JSON"):
        await seed.run(folder, reset=False, settings=settings)


async def test_missing_field_fails_with_line_number(
    app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    folder = tmp_path / "mockgov"
    folder.mkdir()
    (folder / "sii.jsonl").write_text('{"passport_no": "P1", "name": "No Nationality"}\n')
    with pytest.raises(ValueError, match="sii.jsonl:1: missing field 'nationality'"):
        await seed.run(folder, reset=False, settings=settings)


def test_cli_prints_counts(app: FastAPI, settings: Settings, capsys, monkeypatch) -> None:
    monkeypatch.setenv("MOCKGOV_DB_NAME", settings.mockgov_db_name)
    seed.get_settings.cache_clear()
    try:
        assert seed.main(["--from", str(FIXTURES), "--reset"]) == 0
    finally:
        seed.get_settings.cache_clear()
    out = capsys.readouterr().out
    assert "apaar_registry" in out and "4" in out
    assert "done in" in out


def test_cli_reports_a_missing_directory(settings: Settings, tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("MOCKGOV_DB_NAME", settings.mockgov_db_name)
    seed.get_settings.cache_clear()
    try:
        assert seed.main(["--from", str(tmp_path / "nope")]) == 1
    finally:
        seed.get_settings.cache_clear()
    assert "seed failed" in capsys.readouterr().err


async def test_an_older_abc_table_answers_until_the_reset_rebuilds_it(
    app: FastAPI, settings: Settings, session: AsyncSession
) -> None:
    from sqlalchemy import text

    async with app.state.db.engine.begin() as conn:
        for column in ("issuer", "issuer_name"):
            await conn.execute(text(f"ALTER TABLE abc_credits DROP COLUMN {column}"))
    await app.state.db.create_all()
    await seed.run(FIXTURES, reset=False, settings=settings)
    credit = await session.scalar(select(AbcCredit).where(AbcCredit.apaar_id == "123456780004"))
    assert credit.issuer == "1-XYZ-0002"


async def test_reset_drops_a_table_of_an_older_shape(
    app: FastAPI, settings: Settings, session: AsyncSession
) -> None:
    from sqlalchemy import text

    async with app.state.db.engine.begin() as conn:
        await conn.execute(text("ALTER TABLE admission_joinings DROP COLUMN apaar_id"))
    summary = await seed.run(FIXTURES, reset=True, settings=settings)
    assert summary["admission_joinings"] == {"read": 5, "total": 5}
    async with app.state.db.engine.begin() as conn:
        columns = await conn.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'admission_joinings' AND column_name = 'apaar_id'"
            )
        )
    assert columns == 1


async def test_digilocker_accounts_keep_the_last_four_for_search(
    app: FastAPI, settings: Settings, session: AsyncSession
) -> None:
    await seed.run(FIXTURES, reset=False, settings=settings)
    ravi = await session.get(DigiLockerAccount, "DL-RAVI-4417")
    assert (ravi.apaar_id, ravi.apaar_last4, ravi.position) == ("123456784417", "4417", 1)
    meena = await session.get(DigiLockerAccount, "DL-4HXP-2WZA")
    assert (meena.apaar_id, meena.apaar_last4, meena.name_normalized) == (None, None, "meena iyer")
