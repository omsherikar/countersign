"""Test wiring: env before the app imports, fresh schema per session, clean tables on demand.

Postgres must be reachable (POSTGRES_HOST/POSTGRES_PORT; database API_TEST_DB_NAME).
Redis is never required: /healthz reports it as down and the test accepts either state.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import tempfile
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
# never reach a mail server from tests (a refused host sends nothing); tests that read mail
# use a memory mailer
os.environ["SMTP_HOST"] = "smtp.test.invalid"
os.environ.setdefault("CASE_FILES_DIR", tempfile.mkdtemp(prefix="countersign-case-files-"))
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-test-secret-key-test-secret")
os.environ.setdefault("PII_HMAC_KEY", "00" * 32)
os.environ.setdefault("PII_FERNET_KEY", "Zm9yLWRlbW8tb25seS1yZXBsYWNlLW1lLXBsZWFzZS0wMDA=")
os.environ.setdefault("RULES_PATH", str(REPO_ROOT / "rules.yaml"))
os.environ.setdefault("LOG_LEVEL", "WARNING")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import func, select, text, update  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import COOKIE_NAME, create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import dispose_engine, session_factory  # noqa: E402
from app.main import app, run_migrations  # noqa: E402
from app.models.enums import EnrolmentStatus, UserRole  # noqa: E402
from app.models.institution import Institution  # noqa: E402
from app.models.student import Enrolment  # noqa: E402
from app.models.user import User  # noqa: E402
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
    """A client holding the cs_access cookie for one of the demo users.

    A student has no password and signs in only through DigiLocker (D37): the client gets
    the session cookie that sign-in ends with. Everyone else signs in with the password.
    """
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    async with session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None and user.role is UserRole.STUDENT:
        c.cookies.set(COOKIE_NAME, create_access_token(user.id, user.role.value))
        return c
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


# ------------------------------------------------------------ three cohorts

# ABC CSE as datagen shapes it: one approval per cohort, and a single 2026-27 upload
# holding years 1 to 3. Year 2 includes lateral entrants, who join the 2025-26 batch.
THREE_COHORT_INTAKE = {"2024-25": 60, "2025-26": 90, "2026-27": 120}
THREE_COHORT_ROWS = [  # (year_of_study, admission_route, rows)
    (1, "COUNSELLING", 120),
    (1, "MANAGEMENT", 13),  # the last of these is withdrawn after import
    (2, "COUNSELLING", 80),
    (2, "LATERAL", 6),
    (3, "COUNSELLING", 50),
]
UPLOAD_COLUMNS = [
    "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality",
    "passport_no", "programme_code", "academic_year", "year_of_study", "admission_route",
    "counselling_ref", "category", "consent_status",
]  # fmt: skip


def write_three_cohorts(root: Path) -> int:
    """Write a datagen-shaped directory under root; returns the row_no to withdraw."""
    (root / "uploads").mkdir(parents=True)
    institutions = {
        "regions": [{"code": "WEST", "name": "Western", "hq_city": "Mumbai"}],
        "states": [{"code": "MH", "name": "Maharashtra", "region": "WEST"}],
        "universities": [
            {"code": "MSTU", "name": "Maharashtra State Technical University", "state_code": "MH"}
        ],
        "institutions": [
            {
                "aicte_permanent_id": "1-ABC-0001",
                "name": "ABC College of Engineering",
                "type": "PRIVATE_SELF_FINANCED",
                "state_code": "MH",
                "university_code": "MSTU",
                "address_city": "Pune",
                "established_year": 2004,
                "programmes": [
                    {
                        "code": "CSE",
                        "name": "B.Tech Computer Science and Engineering",
                        "level": "UG",
                        "discipline": "ENGINEERING",
                        "shift": "FIRST",
                        "approvals": [
                            {"academic_year": year, "approved_intake": intake}
                            for year, intake in THREE_COHORT_INTAKE.items()
                        ],
                    }
                ],
            }
        ],
    }
    (root / "institutions.json").write_text(json.dumps(institutions), encoding="utf-8")
    users = [
        {"email": "admin@aicte.demo", "password": PASSWORD, "role": "AICTE_ADMIN",
         "name": "AICTE Administrator"},
        {"email": "registrar@abc.edu.demo", "password": PASSWORD, "role": "INSTITUTION",
         "name": "Registrar, ABC College of Engineering", "institution_aicte_id": "1-ABC-0001"},
    ]  # fmt: skip
    (root / "users.json").write_text(json.dumps(users), encoding="utf-8")

    n = 0
    with (root / "uploads" / "1-ABC-0001_2026-27.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=UPLOAD_COLUMNS)
        writer.writeheader()
        for year_of_study, route, count in THREE_COHORT_ROWS:
            for _ in range(count):
                n += 1
                writer.writerow(
                    {
                        "apaar_id": f"7000{n:08d}",
                        "name": f"Cohort Student {n:04d}",
                        "dob": f"{2008 - year_of_study}-01-{1 + n % 28:02d}",
                        "gender": "F" if n % 2 else "M",
                        "mobile": f"98700{n:05d}",
                        "email": f"cohort.{n:04d}@example.demo",
                        "address": f"{n} Station Road, Pune",
                        "nationality": "IN",
                        "passport_no": "",
                        "programme_code": "CSE",
                        "academic_year": "2026-27",
                        "year_of_study": year_of_study,
                        "admission_route": route,
                        "counselling_ref": "",
                        "category": "GENERAL",
                        "consent_status": "LINKED",
                    }
                )
            if (year_of_study, route) == (1, "MANAGEMENT"):
                withdrawn_row_no = n + 1  # row 1 is the header
    return withdrawn_row_no


@pytest.fixture
async def three_cohorts(tmp_path) -> AsyncIterator[None]:
    """Replace the shared data with the three-cohort ABC CSE set, then clear it again."""
    await truncate_all()
    withdrawn_row_no = write_three_cohorts(tmp_path)
    await import_directory(session_factory(), tmp_path)
    async with session_factory()() as session:
        await session.execute(
            update(Enrolment)
            .where(Enrolment.source_row_no == withdrawn_row_no)
            .values(status=EnrolmentStatus.WITHDRAWN)
        )
        await session.commit()
    yield
    await truncate_all()
