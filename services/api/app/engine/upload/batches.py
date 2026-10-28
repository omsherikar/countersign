"""Creating upload batches: kind, the in-progress guard, empty counts, the CREATE audit entry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.engine.upload.types import DECLARATION_TEXT
from app.models.enums import AuditAction, UploadKind, UploadSource, UploadStatus
from app.models.upload import UploadBatch

IN_PROGRESS = (UploadStatus.QUEUED, UploadStatus.VALIDATING, UploadStatus.PROCESSING)
COUNT_KEYS: tuple[str, ...] = (
    "rows",
    "accepted",
    "errors",
    "warnings",
    "created",
    "updated",
    "unchanged",
    "withdrawn",
    "transferred",
    "seated",
    "released",
    "unseated",
    "flags_raised",
    "flags_updated",
)


def empty_counts() -> dict[str, Any]:
    return {**dict.fromkeys(COUNT_KEYS, 0), "sources": {}, "timings_ms": {}}


async def upload_kind(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str
) -> UploadKind:
    """INITIAL when the institution has no earlier DONE batch for the year, else UPDATE."""
    done = (
        await session.execute(
            select(UploadBatch.id)
            .where(
                UploadBatch.institution_id == institution_id,
                UploadBatch.academic_year == academic_year,
                UploadBatch.status == UploadStatus.DONE,
            )
            .limit(1)
        )
    ).first()
    return UploadKind.UPDATE if done else UploadKind.INITIAL


async def batch_in_progress(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str
) -> UploadBatch | None:
    stmt = (
        select(UploadBatch)
        .where(
            UploadBatch.institution_id == institution_id,
            UploadBatch.academic_year == academic_year,
            UploadBatch.status.in_(IN_PROGRESS),
        )
        .order_by(UploadBatch.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_batch(
    session: AsyncSession,
    *,
    institution_id: uuid.UUID,
    academic_year: str,
    filename: str,
    source: UploadSource,
    uploaded_by: uuid.UUID,
    file_sha256: str | None,
    actor_id: uuid.UUID | None,
    batch_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> UploadBatch:
    """A QUEUED batch with its CREATE audit entry; flushed, not committed."""
    declared = source is not UploadSource.SEED
    now = datetime.now(UTC)
    batch = UploadBatch(
        id=batch_id or uuid.uuid4(),
        institution_id=institution_id,
        academic_year=academic_year,
        filename=filename,
        source=source,
        kind=await upload_kind(session, institution_id, academic_year),
        status=UploadStatus.QUEUED,
        stage=None,
        total_rows=0,
        stage_total=0,
        processed_rows=0,
        counts=empty_counts(),
        ignored_columns=[],
        file_sha256=file_sha256,
        declared_at=now if declared else None,
        declaration_text=DECLARATION_TEXT if declared else None,
        uploaded_by=uploaded_by,
        created_at=now,
    )
    session.add(batch)
    await session.flush()
    await audit.record_many(
        session,
        [
            audit.AuditEntry(
                action=AuditAction.CREATE,
                entity_type="upload_batch",
                entity_id=batch.id,
                actor_id=actor_id,
                request_id=request_id,
                after={
                    "institution_id": str(institution_id),
                    "academic_year": academic_year,
                    "source": source.value,
                    "filename": filename,
                    "file_sha256": file_sha256,
                },
            )
        ],
    )
    return batch
