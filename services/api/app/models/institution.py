"""Institutions, programmes, approvals."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import Discipline, InstitutionType, ProgrammeLevel, Shift
from app.models.geo import Region, State, University


class Institution(UUIDPk, Timestamps, Base):
    __tablename__ = "institutions"
    __table_args__ = (
        Index("ix_institutions_region_id", "region_id"),
        Index("ix_institutions_state_id", "state_id"),
        Index("ix_institutions_university_id", "university_id"),
        Index("ix_institutions_lower_name", text("lower(name)")),
    )

    aicte_permanent_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[InstitutionType] = mapped_column(
        pg_enum(InstitutionType, "institutions_type"), nullable=False
    )
    state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("states.id"), nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id"), nullable=False)
    university_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("universities.id"))
    address_city: Mapped[str | None] = mapped_column(String)
    established_year: Mapped[int | None] = mapped_column(Integer)

    state: Mapped[State] = relationship()
    region: Mapped[Region] = relationship()
    university: Mapped[University | None] = relationship()
    programmes: Mapped[list[Programme]] = relationship(back_populates="institution")


class Programme(UUIDPk, Timestamps, Base):
    __tablename__ = "programmes"
    __table_args__ = (UniqueConstraint("institution_id", "code", "shift"),)

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[ProgrammeLevel] = mapped_column(
        pg_enum(ProgrammeLevel, "programmes_level"), nullable=False
    )
    discipline: Mapped[Discipline] = mapped_column(
        pg_enum(Discipline, "programmes_discipline"), nullable=False
    )
    shift: Mapped[Shift] = mapped_column(pg_enum(Shift, "programmes_shift"), nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False)

    institution: Mapped[Institution] = relationship(back_populates="programmes")
    approvals: Mapped[list[Approval]] = relationship(back_populates="programme")


class Approval(UUIDPk, Timestamps, Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("programme_id", "academic_year"),)

    programme_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programmes.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    approved_intake: Mapped[int] = mapped_column(Integer, nullable=False)
    cutoff_date: Mapped[date | None]

    programme: Mapped[Programme] = relationship(back_populates="approvals")
    pools: Mapped[list[SeatPool]] = relationship(back_populates="approval")  # noqa: F821
