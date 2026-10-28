"""Checks, flags, case actions and their attachments, notifications."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    CHAR,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
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
    NoticeDelivery,
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
    # provenance (D34): who supplied the fact, when it answered, and whether that source is
    # independent of the college that made the claim; empty when no source answered
    supplied_by: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    observed_at: Mapped[datetime | None]
    independent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # set when an officer decided the case behind a CONTRADICTED row: {outcome, by, at} (R2)
    resolved: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


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
    # set by REQUEST_DOCS: the date the college's documents are due
    docs_due_on: Mapped[date | None]
    # the college has responded while DOCS_REQUESTED; the status itself does not change
    response_received: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    last_action_at: Mapped[datetime | None]


class CaseAction(Base):
    __tablename__ = "case_actions"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flags.id"), nullable=False, index=True)
    # null on rows the system writes (SYSTEM_NOTE)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[CaseActionKind] = mapped_column(
        pg_enum(CaseActionKind, "case_actions_action"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String)
    attachments: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    # the flag's status before and after this action; equal for NOTE, ASSIGN and SYSTEM_NOTE
    from_status: Mapped[FlagStatus | None] = mapped_column(pg_enum(FlagStatus, "flags_status"))
    to_status: Mapped[FlagStatus | None] = mapped_column(pg_enum(FlagStatus, "flags_status"))
    due_date: Mapped[date | None]
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # the reason code every outcome carries (D43), the fields a CORRECT changed, and the
    # enrolments a WITHDRAW took out of the active counts
    reason_code: Mapped[str | None] = mapped_column(String)
    correction: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    withdrawn_enrolment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'::uuid[]")
    )


class CaseAttachment(UUIDPk, Base):
    """A file a college sent with its response, stored on the case-files volume."""

    __tablename__ = "case_attachments"

    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flags.id"), nullable=False, index=True)
    case_action_seq: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("case_actions.seq"), nullable=False
    )
    # the name the college gave the file; shown, never used as a path
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    # file name under CASE_FILES_DIR, a uuid
    storage_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Notification(UUIDPk, Timestamps, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_enrolment_id_channel", "enrolment_id", "channel"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    channel: Mapped[NoticeChannel] = mapped_column(
        pg_enum(NoticeChannel, "notifications_channel"), nullable=False
    )
    # hex sha256 of the link token; the token itself is only ever in the message sent
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    delivery_status: Mapped[NoticeDelivery] = mapped_column(
        pg_enum(NoticeDelivery, "notifications_delivery"),
        nullable=False,
        default=NoticeDelivery.QUEUED,
        server_default=NoticeDelivery.QUEUED.value,
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # why the last delivery attempt failed, one plain sentence
    last_error: Mapped[str | None] = mapped_column(String)
    sent_at: Mapped[datetime | None]
    opened_at: Mapped[datetime | None]
    response: Mapped[NoticeResponse | None] = mapped_column(
        pg_enum(NoticeResponse, "notifications_response")
    )
    responded_at: Mapped[datetime | None]
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    # the student's free-text comment with the reply (officers only)
    comment: Mapped[str | None] = mapped_column(String)
    # the first answer, kept when the student changes it once within the change window
    previous_response: Mapped[NoticeResponse | None] = mapped_column(
        pg_enum(NoticeResponse, "notifications_response")
    )
    changed_at: Mapped[datetime | None]
    # the user who asked for this notice to be sent again; null for the automatic send
    resent_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
