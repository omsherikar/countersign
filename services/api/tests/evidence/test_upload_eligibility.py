"""The three eligibility columns of the upload (API_CONTRACT §A4.16, D41)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select

from app.core.rules import get_rules
from app.db.session import session_factory
from app.engine.status import STATUS_DIRTY
from app.engine.upload.parse import parse_rows
from app.engine.upload.types import UPLOAD_COLUMNS, upload_date
from app.engine.upload.upsert import upsert_rows
from app.engine.upload.validate import load_context, validate_row, validate_rows
from app.models.enums import RowErrorLevel
from app.models.institution import Institution
from app.models.student import Enrolment
from app.models.upload import UploadBatch
from app.seed.importer import STAFF_ROLES, Summary, import_institutions, import_users
from tests.conftest import FIXTURE_DIR, truncate_all
from tests.pipeline.conftest import ROW, new_batch
from tests.pipeline.fakes import FakeEngines
from tests.pipeline.test_validate import CTX, issues, row

ENGINES = FakeEngines()


@pytest.fixture
async def colleges() -> AsyncIterator[None]:
    await truncate_all()
    summary = Summary()
    async with session_factory()() as session:
        await import_institutions(session, FIXTURE_DIR / "institutions.json", get_rules(), summary)
        await import_users(session, FIXTURE_DIR / "users.json", summary, roles=STAFF_ROLES)
        await session.commit()
    yield
    await truncate_all()


def test_the_template_ends_with_the_three_markers() -> None:
    assert len(UPLOAD_COLUMNS) == 22
    assert UPLOAD_COLUMNS[-4:] == (
        "admission_date",
        "tfw_income_certified",
        "nri_sponsored",
        "ciwg",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", True),
        ("Y", True),
        ("TRUE", True),
        ("1", True),
        ("no", False),
        ("n", False),
        ("False", False),
        ("0", False),
        ("", None),
    ],
)
def test_a_marker_reads_yes_no_or_not_reported(raw: str, expected: bool | None) -> None:
    clean, found = validate_row(row(tfw_income_certified=raw, nri_sponsored=raw, ciwg=raw), CTX)
    assert clean is not None and found == []
    assert clean.eligibility == dict.fromkeys(
        ("tfw_income_certified", "nri_sponsored", "ciwg"), expected
    )


def test_any_other_marker_is_a_warning_and_the_row_is_kept() -> None:
    assert issues(nri_sponsored="maybe") == [
        (
            RowErrorLevel.WARNING,
            "nri_sponsored",
            "BAD_ENUM",
            "NRI sponsored must be yes or no; recorded as not reported",
            "maybe",
        )
    ]
    clean, _ = validate_row(row(tfw_income_certified="perhaps", ciwg="yes"), CTX)
    assert clean is not None
    assert clean.eligibility == {"tfw_income_certified": None, "nri_sponsored": None, "ciwg": True}


async def _upsert(rows: list[dict[str, Any]], batch=None):
    batch = batch or await new_batch("1-ABC-0001")
    async with session_factory()() as session:
        batch = await session.get(UploadBatch, batch.id)
        inst = await session.get(Institution, batch.institution_id)
        ctx = await load_context(session, inst, batch.academic_year, upload_date(batch.created_at))
        validated = validate_rows(parse_rows(rows), ctx)
        result = await upsert_rows(
            session, batch, validated.rows, engines=ENGINES, actor_id=batch.uploaded_by
        )
        await session.commit()
    return result


async def _eligibility() -> dict[str, Any]:
    async with session_factory()() as session:
        return (await session.execute(select(Enrolment.eligibility))).scalar_one()


async def test_markers_are_stored_and_compared_on_re_upload(colleges) -> None:
    marked = {**ROW, "admission_route": "NRI", "nri_sponsored": "yes"}
    first = await _upsert([marked])
    assert first.created == 1
    assert await _eligibility() == {
        "tfw_income_certified": None,
        "nri_sponsored": True,
        "ciwg": None,
    }
    again = await _upsert([marked])
    assert (again.unchanged, again.updated) == (1, 0)
    changed = await _upsert([{**marked, "nri_sponsored": "no"}])
    assert changed.updated == 1
    assert (await _eligibility())["nri_sponsored"] is False


async def test_a_record_stored_before_the_markers_is_unchanged_by_blank_ones(colleges) -> None:
    await _upsert([ROW])
    async with session_factory()() as session:
        enrolment = (await session.execute(select(Enrolment))).scalar_one()
        enrolment.eligibility = {}
        await session.commit()
    assert (await _upsert([ROW])).unchanged == 1


async def test_the_upsert_marks_the_records_it_wrote(colleges) -> None:
    batch = await new_batch("1-ABC-0001")
    async with session_factory()() as session:
        batch = await session.get(UploadBatch, batch.id)
        inst = await session.get(Institution, batch.institution_id)
        ctx = await load_context(session, inst, batch.academic_year, upload_date(batch.created_at))
        validated = validate_rows(parse_rows([ROW]), ctx)
        result = await upsert_rows(
            session, batch, validated.rows, engines=ENGINES, actor_id=batch.uploaded_by
        )
        assert session.info[STATUS_DIRTY] == {result.outcomes[0].enrolment_id}
        await session.rollback()
