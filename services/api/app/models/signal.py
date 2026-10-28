"""Signals (D45): officer-only patterns that never set a record's status (R5)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import SignalStatus, SignalType


class Signal(UUIDPk, Timestamps, Base):
    __tablename__ = "signals"

    type: Mapped[SignalType] = mapped_column(pg_enum(SignalType, "signals_type"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    institution_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'::uuid[]")
    )
    enrolment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'::uuid[]")
    )
    # one plain sentence, the facts behind it, and the rule or model that produced it
    summary: Mapped[str] = mapped_column(String, nullable=False)
    facts: Mapped[Any] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    rule: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[SignalStatus] = mapped_column(
        pg_enum(SignalStatus, "signals_status"),
        nullable=False,
        default=SignalStatus.NEW,
        server_default=SignalStatus.NEW.value,
    )
    # the case an officer opened from this signal
    case_flag_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("flags.id"))
    dedupe_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
