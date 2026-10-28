"""Test harness: a dedicated `mockgov_test` database, created on demand, wiped per test.

Connection details come from POSTGRES_HOST / POSTGRES_PORT / POSTGRES_USER / POSTGRES_PASSWORD;
the database name from MOCKGOV_TEST_DB_NAME (default `mockgov_test`). The live `mockgov`
database is never touched, so the suite is safe to run inside compose after seeding.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed
from app.config import Settings
from app.main import create_app, startup
from app.models import Base

FIXTURES = Path(__file__).parent / "fixtures" / "mockgov"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(mockgov_db_name=os.environ.get("MOCKGOV_TEST_DB_NAME", "mockgov_test"))


async def _create_database_if_missing(settings: Settings) -> None:
    conn = await asyncpg.connect(settings.asyncpg_dsn("postgres"))
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", settings.mockgov_db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{settings.mockgov_db_name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def test_database(settings: Settings) -> None:
    asyncio.run(_create_database_if_missing(settings))


async def truncate_all(app: FastAPI) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with app.state.db.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY"))


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    await application.state.db.create_all()
    await truncate_all(application)
    await startup(application)
    try:
        yield application
    finally:
        await application.state.db.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://mockgov") as client:
        yield client


@pytest.fixture
async def session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.db.sessions() as session:
        yield session


@pytest.fixture
async def seeded(app: FastAPI, settings: Settings) -> dict[str, dict]:
    """Registries loaded from tests/fixtures/mockgov through the real seeder."""
    return await seed.run(FIXTURES, reset=False, settings=settings)
