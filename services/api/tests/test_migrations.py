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
from tests.conftest import API_ROOT

PREVIOUS = "0002"
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
