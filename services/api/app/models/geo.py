"""Regions, states, universities."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk


class Region(UUIDPk, Timestamps, Base):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hq_city: Mapped[str] = mapped_column(String, nullable=False)

    states: Mapped[list[State]] = relationship(back_populates="region")


class State(UUIDPk, Timestamps, Base):
    __tablename__ = "states"

    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id"), nullable=False)

    region: Mapped[Region] = relationship(back_populates="states")


class University(UUIDPk, Timestamps, Base):
    __tablename__ = "universities"

    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("states.id"), nullable=False)

    state: Mapped[State] = relationship()
