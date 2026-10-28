"""Credentials, consents, data requests, institution scores."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import (
    ConsentPurpose,
    ConsentState,
    CredentialKind,
    DataRequestKind,
    DataRequestStatus,
)


class Credential(UUIDPk, Timestamps, Base):
    __tablename__ = "credentials"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    kind: Mapped[CredentialKind] = mapped_column(
        pg_enum(CredentialKind, "credentials_kind"), nullable=False
    )
    sd_jwt: Mapped[str] = mapped_column(String, nullable=False)
    status_list_index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issued_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None]
    issuer_key_id: Mapped[str] = mapped_column(String, nullable=False)


class Consent(UUIDPk, Timestamps, Base):
    __tablename__ = "consents"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(
        pg_enum(ConsentPurpose, "consents_purpose"), nullable=False
    )
    status: Mapped[ConsentState] = mapped_column(
        pg_enum(ConsentState, "consents_status"), nullable=False
    )
    notice_text: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    channel: Mapped[str] = mapped_column(String, nullable=False)


class DataRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "data_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    kind: Mapped[DataRequestKind] = mapped_column(
        pg_enum(DataRequestKind, "data_requests_kind"), nullable=False
    )
    status: Mapped[DataRequestStatus] = mapped_column(
        pg_enum(DataRequestStatus, "data_requests_status"),
        nullable=False,
        default=DataRequestStatus.OPEN,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)


class InstitutionScore(UUIDPk, Timestamps, Base):
    __tablename__ = "institution_scores"
    __table_args__ = (UniqueConstraint("institution_id", "academic_year"),)

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    integrity_index: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
