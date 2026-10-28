"""Seat ledger: pools, seats, seat events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import SeatEventKind, SeatStatus, SeatType


class SeatPool(UUIDPk, Timestamps, Base):
    __tablename__ = "seat_pools"
    __table_args__ = (UniqueConstraint("approval_id", "seat_type"),)

    approval_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("approvals.id"), nullable=False)
    seat_type: Mapped[SeatType] = mapped_column(
        pg_enum(SeatType, "seat_pools_seat_type"), nullable=False
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_supernumerary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rule_source: Mapped[str] = mapped_column(String, nullable=False)

    approval: Mapped[Approval] = relationship(back_populates="pools")  # noqa: F821
    seats: Mapped[list[Seat]] = relationship(back_populates="pool")


class Seat(UUIDPk, Timestamps, Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("pool_id", "seat_code"),
        Index(
            "ix_seats_pool_id_free",
            "pool_id",
            postgresql_where=text("status = 'FREE'"),
        ),
        Index("ix_seats_enrolment_id", "enrolment_id"),
    )

    pool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seat_pools.id"), nullable=False)
    seat_code: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        pg_enum(SeatStatus, "seats_status"), nullable=False, default=SeatStatus.FREE
    )
    reserved_for: Mapped[str | None] = mapped_column(String)
    enrolment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enrolments.id", use_alter=True, name="fk_seats_enrolment_id_enrolments")
    )

    pool: Mapped[SeatPool] = relationship(back_populates="seats")


class SeatEvent(Base):
    __tablename__ = "seat_events"
    __table_args__ = (
        Index("ix_seat_events_seat_id_seq", "seat_id", "seq"),
        Index("ix_seat_events_enrolment_id", "enrolment_id"),
    )

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seats.id"), nullable=False)
    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    kind: Mapped[SeatEventKind] = mapped_column(
        pg_enum(SeatEventKind, "seat_events_kind"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String)
