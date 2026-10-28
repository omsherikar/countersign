"""Upload pipeline tables: one batch per file or API call, and its row errors."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import RowErrorLevel, UploadKind, UploadSource, UploadStage, UploadStatus


class UploadBatch(UUIDPk, Timestamps, Base):
    __tablename__ = "upload_batches"
    __table_args__ = (
        Index(
            "ix_upload_batches_institution_year_created",
            "institution_id",
            "academic_year",
            "created_at",
        ),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id"), nullable=False, index=True
    )
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[UploadKind] = mapped_column(
        pg_enum(UploadKind, "upload_batches_kind"), nullable=False
    )
    status: Mapped[UploadStatus] = mapped_column(
        pg_enum(UploadStatus, "upload_batches_status"), nullable=False, default=UploadStatus.QUEUED
    )
    source: Mapped[UploadSource] = mapped_column(
        pg_enum(UploadSource, "upload_batches_source"),
        nullable=False,
        default=UploadSource.FILE,
        server_default=UploadSource.FILE.value,
    )
    # null while QUEUED; a FAILED batch keeps the stage that failed
    stage: Mapped[UploadStage | None] = mapped_column(pg_enum(UploadStage, "upload_batches_stage"))
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # work items in the current stage, and how many of them are finished
    stage_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    processed_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    counts: Mapped[dict[str, Any]] = mapped_column(
        nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(String)
    ignored_columns: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'::text[]")
    )
    file_sha256: Mapped[str | None] = mapped_column(String)
    declared_at: Mapped[datetime | None]
    declaration_text: Mapped[str | None] = mapped_column(String)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class UploadRowError(UUIDPk, Timestamps, Base):
    __tablename__ = "upload_row_errors"
    __table_args__ = (Index("ix_upload_row_errors_batch_id_row_no", "batch_id", "row_no"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[RowErrorLevel] = mapped_column(
        pg_enum(RowErrorLevel, "upload_row_errors_level"),
        nullable=False,
        default=RowErrorLevel.ERROR,
        server_default=RowErrorLevel.ERROR.value,
    )
    field: Mapped[str | None] = mapped_column(String)
    code: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    value_masked: Mapped[str | None] = mapped_column(String)
    raw: Mapped[dict[str, Any]] = mapped_column(nullable=False)
