"""Users: one row per login, role plus exactly one matching scope column."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import UserRole
from app.models.geo import Region, University
from app.models.institution import Institution
from app.models.student import Student

SCOPE_CHECK = (
    "(role = 'AICTE_ADMIN' AND institution_id IS NULL AND region_id IS NULL "
    "AND student_id IS NULL AND university_id IS NULL) OR "
    "(role = 'RO_OFFICER' AND region_id IS NOT NULL AND institution_id IS NULL "
    "AND student_id IS NULL AND university_id IS NULL) OR "
    "(role = 'INSTITUTION' AND institution_id IS NOT NULL AND region_id IS NULL "
    "AND student_id IS NULL AND university_id IS NULL) OR "
    "(role = 'STUDENT' AND student_id IS NOT NULL AND institution_id IS NULL "
    "AND region_id IS NULL AND university_id IS NULL) OR "
    "(role = 'UNIVERSITY' AND university_id IS NOT NULL AND institution_id IS NULL "
    "AND region_id IS NULL AND student_id IS NULL)"
)


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(SCOPE_CHECK, name="role_scope"),)

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "users_role"), nullable=False)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutions.id"))
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"))
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"))
    university_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("universities.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None]
    # the DigiLocker subject of a STUDENT who signed in through DigiLocker (D37)
    digilocker_sub: Mapped[str | None] = mapped_column(String, unique=True)

    institution: Mapped[Institution | None] = relationship(lazy="joined")
    region: Mapped[Region | None] = relationship(lazy="joined")
    student: Mapped[Student | None] = relationship(lazy="joined")
    university: Mapped[University | None] = relationship(lazy="joined")
