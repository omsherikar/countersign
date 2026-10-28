"""Credential test fixtures.

Tests that touch the database start from the mini datagen fixture imported fresh and end
with empty tables, so the shared `seeded` data other packages read is never left holding
proofs, keys or changed checks. The status-list token is cached per process, so it is
dropped around every such test too.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.credentials import status_list
from app.db.session import session_factory
from app.models.enums import CheckStatus, CheckType, EnrolmentStatus
from app.models.institution import Institution
from app.models.student import Enrolment, Student
from app.models.verification import Check
from app.seed.importer import import_directory
from tests.conftest import FIXTURE_DIR, truncate_all

RAVI_APAAR_LAST4 = "4417"


@pytest.fixture
async def world() -> AsyncIterator[None]:
    """The mini fixture, imported fresh; emptied again afterwards."""
    await truncate_all()
    status_list.invalidate()
    await import_directory(session_factory(), FIXTURE_DIR)
    yield
    await truncate_all()
    status_list.invalidate()


@pytest.fixture
async def empty() -> AsyncIterator[None]:
    await truncate_all()
    status_list.invalidate()
    yield
    await truncate_all()
    status_list.invalidate()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as s:
        yield s


async def ravi_enrolment(session: AsyncSession) -> Enrolment:
    """Ravi Kumar Sharma's ACTIVE enrolment at ABC CSE (the student@demo login)."""
    return (
        await session.execute(
            select(Enrolment)
            .join(Student, Student.id == Enrolment.student_id)
            .where(Student.apaar_last4 == RAVI_APAAR_LAST4, Student.name == "Ravi Kumar Sharma")
        )
    ).scalar_one()


async def active_enrolments(session: AsyncSession, aicte_id: str, n: int) -> list[Enrolment]:
    """n ACTIVE enrolments of one institution with a linked APAAR, in a stable order."""
    return list(
        (
            await session.execute(
                select(Enrolment)
                .join(Institution, Institution.id == Enrolment.institution_id)
                .join(Student, Student.id == Enrolment.student_id)
                .where(
                    Institution.aicte_permanent_id == aicte_id,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                    Student.apaar_last4.is_not(None),
                )
                .order_by(Enrolment.source_row_no)
                .limit(n)
            )
        )
        .scalars()
        .all()
    )


async def set_check(
    session: AsyncSession, enrolment_id: uuid.UUID, check: CheckType, status: CheckStatus
) -> None:
    """Write one check's status as the engines would, creating the row if needed."""
    row = (
        await session.execute(
            select(Check).where(Check.enrolment_id == enrolment_id, Check.type == check)
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(
            Check(
                enrolment_id=enrolment_id,
                type=check,
                status=status,
                detail={"summary": "set by a test"},
                source="TEST",
                checked_at=datetime.now(UTC),
            )
        )
    else:
        row.status = status
    await session.flush()


async def make_countersigned(session: AsyncSession, enrolment_id: uuid.UUID) -> None:
    """The student said Yes and no source disagrees: every FAIL becomes PASS too."""
    await session.execute(
        update(Check)
        .where(Check.enrolment_id == enrolment_id, Check.status == CheckStatus.CONTRADICTED)
        .values(status=CheckStatus.CONFIRMED)
    )
    await set_check(session, enrolment_id, CheckType.STUDENT, CheckStatus.CONFIRMED)
