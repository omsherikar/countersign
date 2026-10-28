"""Upload pipeline tables (filled from Week 2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import UploadKind, UploadStatus


class UploadBatch(UUIDPk, Timestamps, Base):
    __tablename__ = "upload_batches"

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
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class UploadRowError(UUIDPk, Timestamps, Base):
    __tablename__ = "upload_row_errors"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str | None] = mapped_column(String)
    code: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(nullable=False)
