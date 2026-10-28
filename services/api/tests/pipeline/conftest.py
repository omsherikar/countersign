"""Pipeline test wiring: an institutions-and-users world, batches, a temporary spool."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rules import get_rules
from app.db.session import session_factory
from app.engine.upload.batches import create_batch
from app.engine.upload.types import UPLOAD_COLUMNS
from app.models.enums import UploadSource, UserRole
from app.models.institution import Institution
from app.models.upload import UploadBatch
from app.models.user import User
from app.seed.importer import STAFF_ROLES, Summary, import_institutions, import_users
from tests.conftest import FIXTURE_DIR, truncate_all


@pytest.fixture
async def world() -> AsyncIterator[None]:
    """Institutions, programmes, approvals, seats and staff users; no students. Cleared after."""
    await truncate_all()
    summary = Summary()
    async with session_factory()() as session:
        await import_institutions(session, FIXTURE_DIR / "institutions.json", get_rules(), summary)
        await import_users(session, FIXTURE_DIR / "users.json", summary, roles=STAFF_ROLES)
        await session.commit()
    yield
    await truncate_all()


@pytest.fixture
def spool(tmp_path, monkeypatch):
    """A private spool directory for the test."""
    directory = tmp_path / "spool"
    monkeypatch.setattr(get_settings(), "upload_spool_dir", str(directory))
    return directory


async def institution(aicte_id: str = "1-ABC-0001") -> Institution:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(Institution).where(Institution.aicte_permanent_id == aicte_id)
            )
        ).scalar_one()


async def registrar(aicte_id: str = "1-ABC-0001") -> User:
    inst = await institution(aicte_id)
    async with session_factory()() as session:
        return (
            await session.execute(
                select(User).where(
                    User.institution_id == inst.id, User.role == UserRole.INSTITUTION
                )
            )
        ).scalar_one()


async def new_batch(
    aicte_id: str = "1-ABC-0001",
    *,
    source: UploadSource = UploadSource.FILE,
    filename: str = "upload.csv",
    academic_year: str = "2026-27",
) -> UploadBatch:
    inst = await institution(aicte_id)
    owner = await registrar(aicte_id)
    async with session_factory()() as session:
        batch = await create_batch(
            session,
            institution_id=inst.id,
            academic_year=academic_year,
            filename=filename,
            source=source,
            uploaded_by=owner.id,
            file_sha256=None,
            actor_id=owner.id,
        )
        await session.commit()
        return batch


ROW: dict[str, Any] = {
    "apaar_id": "123456784417",
    "name": "Ravi Kumar Sharma",
    "dob": "2007-03-21",
    "gender": "M",
    "mobile": "9876504521",
    "email": "ravi.sharma@example.demo",
    "address": "12 Shivaji Nagar, Pune",
    "nationality": "IN",
    "passport_no": "",
    "programme_code": "CSE",
    "academic_year": "2026-27",
    "year_of_study": "1",
    "admission_route": "COUNSELLING",
    "counselling_ref": "MHCET-2026-R1-004512",
    "category": "GENERAL",
    "consent_status": "LINKED",
    "status": "",
    "status_date": "",
    "admission_date": "2026-08-02",
}


def csv_bytes(rows: list[dict[str, Any]], columns: tuple[str, ...] = UPLOAD_COLUMNS) -> bytes:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buffer.getvalue().encode("utf-8")


def student_row(n: int, **changes: Any) -> dict[str, Any]:
    """A distinct, valid first-year CSE row."""
    row = dict(ROW)
    row.update(
        apaar_id=f"5000{n:08d}",
        name=f"Student Number {n:04d}",
        mobile=f"98{n:08d}",
        email=f"s{n}@example.demo",
        counselling_ref=f"MHCET-2026-R1-{n:06d}",
    )
    row.update(changes)
    return row


def uid() -> uuid.UUID:
    return uuid.uuid4()
