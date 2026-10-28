"""APAAR_LINK consent rows come from the college's upload: once when a student is created
or its consent changes, never again for an unchanged re-upload."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.session import session_factory
from app.engine.upload.parse import parse_rows
from app.engine.upload.types import upload_date
from app.engine.upload.upsert import upsert_rows
from app.engine.upload.validate import load_context, validate_rows
from app.models.audit import AuditLog
from app.models.credential import Consent
from app.models.enums import ConsentPurpose
from app.models.institution import Institution
from app.models.student import Student
from app.models.upload import UploadBatch
from app.privacy.notice import consent_text
from tests.pipeline.conftest import ROW, new_batch, student_row, world  # noqa: F401
from tests.pipeline.fakes import FakeEngines


async def upsert(rows: list[dict[str, Any]]) -> UploadBatch:
    batch = await new_batch()
    async with session_factory()() as session:
        batch = await session.get(UploadBatch, batch.id)
        institution = await session.get(Institution, batch.institution_id)
        ctx = await load_context(
            session, institution, batch.academic_year, upload_date(batch.created_at)
        )
        validated = validate_rows(parse_rows(rows), ctx)
        await upsert_rows(
            session, batch, validated.rows, engines=FakeEngines(), actor_id=batch.uploaded_by
        )
        await session.commit()
    return batch


async def consents() -> list[tuple[str, str, str, str]]:
    async with session_factory()() as session:
        rows = await session.execute(
            select(Student.name, Consent.status, Consent.channel, Consent.notice_text)
            .join(Student, Student.id == Consent.student_id)
            .where(Consent.purpose == ConsentPurpose.APAAR_LINK)
            .order_by(Consent.recorded_at)
        )
        return [(name, status.value, channel, text) for name, status, channel, text in rows]


async def test_upload_records_apaar_consent_once(world) -> None:  # noqa: F811
    refused = student_row(3, apaar_id="", consent_status="REFUSED")
    pending = student_row(4, apaar_id="", consent_status="PENDING")
    batch = await upsert([ROW, refused, pending])
    rows = await consents()
    assert [(name, status, channel) for name, status, channel, _ in rows] == [
        ("Ravi Kumar Sharma", "GIVEN", "COLLEGE_UPLOAD"),
        ("Student Number 0003", "REFUSED", "COLLEGE_UPLOAD"),
    ]
    async with session_factory()() as session:
        institution = await session.get(Institution, batch.institution_id)
        stored = (await session.execute(select(Consent))).scalars().all()
        entries = (
            (await session.execute(select(AuditLog).where(AuditLog.entity_type == "consent")))
            .scalars()
            .all()
        )
    assert rows[0][3] == consent_text(ConsentPurpose.APAAR_LINK, institution_name=institution.name)
    assert institution.name in rows[0][3] and "{" not in rows[0][3]
    assert all(c.notice_version == "v1" and c.enrolment_id is not None for c in stored)
    assert len(entries) == 2 and all(e.actor_id == batch.uploaded_by for e in entries)
    assert all(set(e.after) == {"purpose", "status", "channel"} for e in entries)

    # the same file again writes nothing
    await upsert([ROW, refused, pending])
    assert len(await consents()) == 2

    # the pending student's APAAR arrives with consent: one GIVEN row for that change
    await upsert([student_row(4, apaar_id="600000000004", consent_status="LINKED")])
    assert [(name, status) for name, status, *_ in await consents()][-1] == (
        "Student Number 0004",
        "GIVEN",
    )
    assert len(await consents()) == 3
