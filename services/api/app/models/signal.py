"""Signals (D45): officer-only patterns that never set a record's status (R5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.models._types import pg_enum
from app.models.enums import SignalStatus, SignalType


class Signal(UUIDPk, Base):
    __tablename__ = "signals"

    type: Mapped[SignalType] = mapped_column(pg_enum(SignalType, "signals_type"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    # every institution the signal touches (one for ANOMALY)
    institution_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    # GHOST_RING: the members' ACTIVE enrolments; empty for ANOMALY
    enrolment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'::uuid[]")
    )
    # one plain sentence, the facts behind it (an object), and the rule or model behind it
    summary: Mapped[str] = mapped_column(String, nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(
        nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    rule: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[SignalStatus] = mapped_column(
        pg_enum(SignalStatus, "signals_status"),
        nullable=False,
        default=SignalStatus.NEW,
        server_default=SignalStatus.NEW.value,
    )
    # the first case an officer opened from this signal
    case_flag_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("flags.id"))
    dedupe_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # the officer's decision on the signal: the note given when opening a case or dismissing,
    # who decided and when
    note: Mapped[str | None] = mapped_column(String)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    # moves when a later run refreshes it
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
