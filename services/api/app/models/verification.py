"""Checks, flags, case actions, notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import (
    CaseActionKind,
    CheckStatus,
    CheckType,
    FlagStatus,
    FlagType,
    NoticeChannel,
    NoticeResponse,
    Severity,
)


class Check(UUIDPk, Timestamps, Base):
    __tablename__ = "checks"
    __table_args__ = (
        UniqueConstraint("enrolment_id", "type"),
        Index("ix_checks_type_status", "type", "status"),
    )

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrolments.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[CheckType] = mapped_column(pg_enum(CheckType, "checks_type"), nullable=False)
    status: Mapped[CheckStatus] = mapped_column(
        pg_enum(CheckStatus, "checks_status"), nullable=False
    )
    detail: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String, nullable=False)
    checked_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Flag(UUIDPk, Timestamps, Base):
    __tablename__ = "flags"
    __table_args__ = (
        Index("ix_flags_institution_id_status", "institution_id", "status"),
        Index("ix_flags_type_status", "type", "status"),
        Index("ix_flags_enrolment_id", "enrolment_id"),
        Index("ix_flags_academic_year_status", "academic_year", "status"),
        Index(
            "ix_flags_related_enrolment_ids",
            "related_enrolment_ids",
            postgresql_using="gin",
        ),
    )

    type: Mapped[FlagType] = mapped_column(pg_enum(FlagType, "flags_type"), nullable=False)
    severity: Mapped[Severity] = mapped_column(pg_enum(Severity, "flags_severity"), nullable=False)
    status: Mapped[FlagStatus] = mapped_column(
        pg_enum(FlagStatus, "flags_status"), nullable=False, default=FlagStatus.OPEN
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    programme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("programmes.id"))
    enrolment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enrolments.id"))
    # roll year of the enrolments that raised it
    academic_year: Mapped[str | None] = mapped_column(String)
    related_enrolment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    resolved_at: Mapped[datetime | None]
    dedupe_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class CaseAction(Base):
    __tablename__ = "case_actions"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flags.id"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[CaseActionKind] = mapped_column(
        pg_enum(CaseActionKind, "case_actions_action"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String)
    attachments: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Notification(UUIDPk, Timestamps, Base):
    __tablename__ = "notifications"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    channel: Mapped[NoticeChannel] = mapped_column(
        pg_enum(NoticeChannel, "notifications_channel"), nullable=False
    )
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[datetime | None]
    opened_at: Mapped[datetime | None]
    response: Mapped[NoticeResponse | None] = mapped_column(
        pg_enum(NoticeResponse, "notifications_response")
    )
    responded_at: Mapped[datetime | None]
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
