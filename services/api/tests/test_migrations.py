"""Migrations on a scratch database: the models match head, and the latest revision
downgrades to exactly the schema it started from and upgrades again."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings
from app.db.base import Base
from app.models import Check, Credential, Enrolment, Flag
from app.models.verification import CaseAction
from tests.conftest import API_ROOT

PREVIOUS = "0003"
SNAPSHOT_SQL = {
    "columns": (
        "SELECT table_name, column_name, udt_name, is_nullable, column_default, "
        "character_maximum_length FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY 1, 2"
    ),
    "enums": (
        "SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) "
        "FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid GROUP BY 1 ORDER BY 1"
    ),
    "indexes": "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1",
    "constraints": (
        "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2"
    ),
}


async def _admin(sql: str) -> None:
    engine = create_async_engine(get_settings().database_url(), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture
def scratch_url() -> Iterator[str]:
    name = f"{get_settings().api_db_name}_migrations"
    try:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        asyncio.run(_admin(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # no CREATEDB privilege: nothing to test against
        pytest.skip(f"cannot create a scratch database: {exc}")
    try:
        yield get_settings().database_url(name)
    finally:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"), cmd_opts=argparse.Namespace(x=[f"url={url}"]))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg


def _inspect(url: str) -> tuple[dict[str, list[tuple[Any, ...]]], list[Any]]:
    """Catalog snapshot plus the autogenerate diff between the database and the models."""

    def diff(sync_conn) -> list[Any]:
        context = MigrationContext.configure(
            sync_conn, opts={"compare_type": True, "compare_server_default": True}
        )
        return compare_metadata(context, Base.metadata)

    async def run() -> tuple[dict[str, list[tuple[Any, ...]]], list[Any]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                snapshot = {
                    key: [tuple(row) for row in (await conn.execute(text(sql))).all()]
                    for key, sql in SNAPSHOT_SQL.items()
                }
                return snapshot, await conn.run_sync(diff)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_head_matches_the_models_and_the_last_revision_round_trips(scratch_url):
    cfg = _config(scratch_url)
    command.upgrade(cfg, PREVIOUS)
    before, _ = _inspect(scratch_url)

    command.upgrade(cfg, "head")
    head, drift = _inspect(scratch_url)
    assert drift == []

    command.downgrade(cfg, PREVIOUS)
    after_down, _ = _inspect(scratch_url)
    for key in SNAPSHOT_SQL:
        assert after_down[key] == before[key], key

    command.upgrade(cfg, "head")
    again, drift = _inspect(scratch_url)
    assert drift == []
    for key in SNAPSHOT_SQL:
        assert again[key] == head[key], key


def _sql(url: str, *statements: str) -> list[list[tuple[Any, ...]]]:
    """Run each statement in one transaction; the rows of those that return any."""

    async def run() -> list[list[tuple[Any, ...]]]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                out = []
                for statement in statements:
                    result = await conn.execute(text(statement))
                    out.append([tuple(r) for r in result.all()] if result.returns_rows else [])
                return out
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _id(n: int) -> str:
    return f"00000000-0000-0000-0000-{n:012d}"


FIRST_YEAR = "First year, no result yet."
LATERAL = "Joined in year 2 as a lateral entrant; no completed year to check yet."
OUTAGE = '{"summary": "ABC credits did not respond.", "source_unavailable": true}'

SEED_0003 = (
    f"INSERT INTO regions (id, code, name, hq_city) VALUES ('{_id(1)}', 'SRO', 'Southern', 'B')",
    "INSERT INTO states (id, code, name, region_id) "
    f"VALUES ('{_id(2)}', 'KA', 'Karnataka', '{_id(1)}')",
    "INSERT INTO institutions (id, aicte_permanent_id, name, type, state_id, region_id) "
    f"VALUES ('{_id(3)}', '1-1', 'College', 'GOVERNMENT', '{_id(2)}', '{_id(1)}')",
    "INSERT INTO programmes (id, institution_id, code, name, level, discipline, shift, "
    f"duration_years) VALUES ('{_id(4)}', '{_id(3)}', 'CSE', 'CSE', 'UG', 'ENGINEERING', "
    "'FIRST', 4)",
    "INSERT INTO approvals (id, programme_id, academic_year, approved_intake) "
    f"VALUES ('{_id(5)}', '{_id(4)}', '2026-27', 60)",
    "INSERT INTO students (id, consent_status, name, name_normalized, dob, gender, nationality) "
    f"VALUES ('{_id(6)}', 'LINKED', 'Ravi', 'ravi', '2008-01-01', 'M', 'IN')",
    *(
        "INSERT INTO enrolments (id, student_id, institution_id, programme_id, academic_year, "
        "year_of_study, cohort_year, admission_route, category, status) "
        f"VALUES ('{_id(10 + k)}', '{_id(6)}', '{_id(3)}', '{_id(4)}', '{year}', 1, '{year}', "
        "'COUNSELLING', 'GENERAL', 'ACTIVE')"
        for k, year in enumerate(("2024-25", "2025-26", "2026-27"))
    ),
    *(
        "INSERT INTO checks (enrolment_id, type, status, detail, source, attempts) "
        f"VALUES ('{_id(enrolment)}', '{type_}', '{status}', '{detail}'::jsonb, 'X', 0)"
        for enrolment, type_, status, detail in (
            (10, "IDENTITY", "PASS", '{"summary": "Match."}'),
            (10, "ADMISSION", "FAIL", '{"summary": "Not found."}'),
            (10, "STUDYING", "NA", f'{{"summary": "{FIRST_YEAR}"}}'),
            (10, "SEAT", "PENDING", OUTAGE),
            (10, "STUDENT", "PENDING", '{"summary": "Notice not sent yet."}'),
            (11, "IDENTITY", "NA", '{"summary": "APAAR not linked."}'),
            (11, "STUDYING", "NA", f'{{"summary": "{LATERAL}"}}'),
            (12, "STUDYING", "NA", '{"summary": "APAAR not linked; ABC cannot be checked."}'),
        )
    ),
    *(
        "INSERT INTO flags (id, type, severity, status, institution_id, related_enrolment_ids, "
        f"evidence, dedupe_key) VALUES ('{_id(n)}', 'NAME_MISMATCH', 'LOW', '{status}', "
        f"'{_id(3)}', '{{}}', '{{}}'::jsonb, 'K{n}')"
        for n, status in ((20, "CLEARED"), (21, "CONFIRMED"), (22, "OPEN"))
    ),
    "INSERT INTO case_actions (flag_id, action, attachments, from_status, to_status) VALUES "
    f"('{_id(20)}', 'CLEAR', '[]', 'OPEN', 'CLEARED'), "
    f"('{_id(21)}', 'CONFIRM', '[]', 'OPEN', 'CONFIRMED')",
    *(
        "INSERT INTO credentials (student_id, enrolment_id, kind, sd_jwt, status_list_index, "
        f"revoked, issuer_key_id, vct, short_id) VALUES ('{_id(6)}', '{_id(12)}', '{kind}', "
        f"'x', {n}, false, 'k', 'v', 'S{n}')"
        for n, kind in ((1, "ENROLMENT"), (2, "DEGREE"))
    ),
)
CHECK_STATES = "SELECT enrolment_id::text, type::text, status::text FROM checks ORDER BY 1, 2"
FLAG_STATES = "SELECT dedupe_key, status::text, type::text FROM flags ORDER BY 1"
ACTIONS = (
    "SELECT flag_id::text, action::text, from_status::text, to_status::text "
    "FROM case_actions ORDER BY seq"
)
KINDS = "SELECT status_list_index, kind::text FROM credentials ORDER BY 1"


def test_0004_moves_every_old_value_to_its_new_name_and_back(scratch_url):
    cfg = _config(scratch_url)
    command.upgrade(cfg, PREVIOUS)
    _sql(scratch_url, *SEED_0003)
    before = _sql(scratch_url, CHECK_STATES, FLAG_STATES, ACTIONS, KINDS)

    command.upgrade(cfg, "head")
    checks, flags, actions, kinds, versions, records = _sql(
        scratch_url,
        CHECK_STATES,
        FLAG_STATES,
        ACTIONS,
        KINDS,
        "SELECT approval_id::text, version, approved_intake, effective_from::text, source "
        "FROM approval_versions",
        "SELECT DISTINCT record_status::text FROM enrolments",
    )
    e10, e11, e12 = _id(10), _id(11), _id(12)
    assert checks == [
        (e10, "ADMISSION", "CONTRADICTED"),
        (e10, "IDENTITY", "CONFIRMED"),
        (e10, "SEAT", "SOURCE_UNAVAILABLE"),
        (e10, "STUDENT", "PENDING"),
        (e10, "STUDYING", "NOT_YET_DUE"),
        (e11, "IDENTITY", "NOT_APPLICABLE"),
        (e11, "STUDYING", "NOT_YET_DUE"),
        (e12, "STUDYING", "NOT_APPLICABLE"),
    ]
    assert flags == [
        ("K20", "UPHELD", "NAME_MISMATCH"),
        ("K21", "WITHDRAWN", "NAME_MISMATCH"),
        ("K22", "OPEN", "NAME_MISMATCH"),
    ]
    assert actions == [
        (_id(20), "UPHOLD", "OPEN", "UPHELD"),
        (_id(21), "WITHDRAW", "OPEN", "WITHDRAWN"),
    ]
    assert kinds == [(1, "ENROLMENT"), (2, "COMPLETION")]
    assert versions == [(_id(5), 1, 60, "2026-07-01", "SEED")]
    assert records == [("AWAITING_EVIDENCE",)]

    # values only the new schema has: a correction and a case of a new type
    _sql(
        scratch_url,
        "INSERT INTO flags (id, type, severity, status, institution_id, related_enrolment_ids, "
        f"evidence, dedupe_key) VALUES ('{_id(23)}', 'NAME_MISMATCH', 'LOW', 'CORRECTED', "
        f"'{_id(3)}', '{{}}', '{{}}'::jsonb, 'K23'), ('{_id(24)}', 'NOT_IN_JOINING_RECORD', "
        f"'MEDIUM', 'OPEN', '{_id(3)}', '{{}}', '{{}}'::jsonb, 'K24')",
        "INSERT INTO case_actions (flag_id, action, attachments, from_status, to_status) VALUES "
        f"('{_id(23)}', 'CORRECT', '[]', 'OPEN', 'CORRECTED'), "
        f"('{_id(24)}', 'NOTE', '[]', 'OPEN', 'OPEN')",
    )
    command.downgrade(cfg, PREVIOUS)
    checks, flags, actions, kinds = _sql(scratch_url, CHECK_STATES, FLAG_STATES, ACTIONS, KINDS)
    old_checks, old_flags, old_actions, old_kinds = before
    # not yet due reads as n/a again and an unavailable source as pending
    assert checks == old_checks
    assert flags == [*old_flags, ("K23", "CONFIRMED", "NAME_MISMATCH")]
    assert actions == [*old_actions, (_id(23), "CONFIRM", "OPEN", "CONFIRMED")]
    assert kinds == old_kinds


def test_every_database_enum_has_exactly_the_python_values(scratch_url):
    command.upgrade(_config(scratch_url), "head")
    (rows,) = _sql(
        scratch_url,
        "SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) "
        "FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid GROUP BY 1",
    )
    in_database = dict(rows)
    in_models = {
        column.type.name: list(column.type.enums)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if getattr(column.type, "enum_class", None) is not None
    }
    assert in_database == in_models
    for model, column in (
        (Check, "status"),
        (Flag, "status"),
        (CaseAction, "action"),
        (Credential, "kind"),
        (Enrolment, "record_status"),
    ):
        enum_type = getattr(model, column).type
        assert list(enum_type.enums) == [m.value for m in enum_type.enum_class]
