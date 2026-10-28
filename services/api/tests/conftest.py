"""Test wiring: env before the app imports, fresh schema per session, clean tables on demand.

Postgres must be reachable (POSTGRES_HOST/POSTGRES_PORT; database API_TEST_DB_NAME).
Redis is never required: /healthz reports it as down and the test accepts either state.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_ROOT = HERE.parent
REPO_ROOT = API_ROOT.parent.parent
FIXTURE_DIR = HERE / "fixtures" / "mini_generated"
PASSWORD = "Countersign!2026"

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ["API_DB_NAME"] = os.environ.get("API_TEST_DB_NAME", "countersign_test")
os.environ["AUTO_MIGRATE"] = "false"
os.environ["RATE_LIMITS_ENABLED"] = "false"
os.environ["GOV_ADAPTER"] = "inmemory"
os.environ["MOCKGOV_BASE_URL"] = "http://mockgov.test"
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-test-secret-key-test-secret")
os.environ.setdefault("PII_HMAC_KEY", "00" * 32)
os.environ.setdefault("PII_FERNET_KEY", "Zm9yLWRlbW8tb25seS1yZXBsYWNlLW1lLXBsZWFzZS0wMDA=")
os.environ.setdefault("RULES_PATH", str(REPO_ROOT / "rules.yaml"))
os.environ.setdefault("LOG_LEVEL", "WARNING")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import dispose_engine, session_factory  # noqa: E402
from app.main import app, run_migrations  # noqa: E402
from app.models.institution import Institution  # noqa: E402
from app.seed.importer import Summary, import_directory  # noqa: E402


async def _reset_schema() -> None:
    engine = create_async_engine(get_settings().database_url(), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def fresh_schema() -> None:
    """Drop everything and apply migration 0001 once per test session."""
    asyncio.run(_reset_schema())
    run_migrations()


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine_at_end() -> AsyncIterator[None]:
    yield
    await dispose_engine()


async def truncate_all() -> None:
    async with session_factory()() as session:
        tables = ", ".join(f'"{t}"' for t in Base.metadata.tables)
        await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture
async def clean_db() -> None:
    """Empty every table before a test that needs isolation."""
    await truncate_all()


@pytest.fixture
async def seeded() -> Summary | None:
    """The mini datagen fixture, imported once and reused until a test truncates."""
    async with session_factory()() as session:
        present = (
            await session.execute(select(func.count()).select_from(Institution))
        ).scalar_one()
    if present:
        return None
    return await import_directory(session_factory(), FIXTURE_DIR)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def login_as(email: str) -> httpx.AsyncClient:
    """A client holding the cs_access cookie for one of the demo users."""
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = await c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return c


@pytest.fixture
async def admin(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("admin@aicte.demo")
    yield c
    await c.aclose()


@pytest.fixture
async def ro_west(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("ro.west@aicte.demo")
    yield c
    await c.aclose()


@pytest.fixture
async def ro_south(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("ro.south@aicte.demo")
    yield c
    await c.aclose()


@pytest.fixture
async def registrar_abc(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("registrar@abc.edu.demo")
    yield c
    await c.aclose()


@pytest.fixture
async def registrar_xyz(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("registrar@xyz.edu.demo")
    yield c
    await c.aclose()


@pytest.fixture
async def student(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("student@demo")
    yield c
    await c.aclose()


@pytest.fixture
async def university(seeded) -> AsyncIterator[httpx.AsyncClient]:
    c = await login_as("coe@univ.demo")
    yield c
    await c.aclose()


async def institution_id(aicte_id: str) -> str:
    async with session_factory()() as session:
        row = (
            await session.execute(
                select(Institution.id).where(Institution.aicte_permanent_id == aicte_id)
            )
        ).scalar_one()
    return str(row)
