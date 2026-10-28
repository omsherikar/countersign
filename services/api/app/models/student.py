"""Students and enrolments."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import (
    AdmissionRoute,
    Category,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
    RecordStatus,
)


class Student(UUIDPk, Timestamps, Base):
    __tablename__ = "students"
    __table_args__ = (
        Index("ix_students_dob_name_normalized", "dob", "name_normalized"),
        Index("ix_students_mobile_hmac", "mobile_hmac"),
        Index("ix_students_email", "email"),
        Index("ix_students_address_hmac", "address_hmac"),
        Index("ix_students_name_key", "name_key"),
        Index("ix_students_passport_hmac", "passport_hmac"),
    )

    apaar_hmac: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    apaar_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    apaar_last4: Mapped[str | None] = mapped_column(String(4))
    consent_status: Mapped[ConsentStatus] = mapped_column(
        pg_enum(ConsentStatus, "students_consent_status"), nullable=False
    )
    provisional_id: Mapped[str | None] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_normalized: Mapped[str] = mapped_column(String, nullable=False)
    # duplicate blocking key "<dob ISO>|<first initial>|<metaphone of surname>"
    name_key: Mapped[str | None] = mapped_column(String)
    dob: Mapped[date] = mapped_column(nullable=False)
    gender: Mapped[Gender] = mapped_column(
        pg_enum(Gender, "students_gender"), nullable=False, default=Gender.U
    )
    mobile_hmac: Mapped[bytes | None] = mapped_column(LargeBinary)
    mobile_last4: Mapped[str | None] = mapped_column(String(4))
    email: Mapped[str | None] = mapped_column(String)
    address_hmac: Mapped[bytes | None] = mapped_column(LargeBinary)
    nationality: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")
    passport_hmac: Mapped[bytes | None] = mapped_column(LargeBinary)
    passport_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)

    enrolments: Mapped[list[Enrolment]] = relationship(back_populates="student")


class Enrolment(UUIDPk, Timestamps, Base):
    __tablename__ = "enrolments"
    __table_args__ = (
        UniqueConstraint("student_id", "institution_id", "programme_id", "academic_year"),
        Index("ix_enrolments_institution_year_status", "institution_id", "academic_year", "status"),
        Index("ix_enrolments_programme_year", "programme_id", "academic_year"),
        Index("ix_enrolments_student_id", "student_id"),
        Index("ix_enrolments_programme_cohort_status", "programme_id", "cohort_year", "status"),
        Index(
            "uq_enrolments_seat_id",
            "seat_id",
            unique=True,
            postgresql_where=text("seat_id IS NOT NULL"),
        ),
        Index(
            "ix_enrolments_institution_year_record_status",
            "institution_id",
            "academic_year",
            "record_status",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    programme_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programmes.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    year_of_study: Mapped[int] = mapped_column(Integer, nullable=False)
    # the approval year this row belongs to (app.core.cohort.cohort_year)
    cohort_year: Mapped[str] = mapped_column(String, nullable=False)
    admission_route: Mapped[AdmissionRoute] = mapped_column(
        pg_enum(AdmissionRoute, "enrolments_admission_route"), nullable=False
    )
    counselling_ref: Mapped[str | None] = mapped_column(String)
    category: Mapped[Category] = mapped_column(
        pg_enum(Category, "enrolments_category"), nullable=False
    )
    seat_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seats.id"))
    status: Mapped[EnrolmentStatus] = mapped_column(
        pg_enum(EnrolmentStatus, "enrolments_status"),
        nullable=False,
        default=EnrolmentStatus.ACTIVE,
    )
    upload_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))
    source_row_no: Mapped[int | None] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    admission_date: Mapped[date] = mapped_column(
        nullable=False, server_default=text("CURRENT_DATE")
    )
    status_date: Mapped[date] = mapped_column(nullable=False, server_default=text("CURRENT_DATE"))
    # why the uploaded APAAR was unusable, e.g. "has 11 digits, expected 12"; never the digits
    apaar_problem: Mapped[str | None] = mapped_column(String)
    # the record's status (D35), kept current by app.engine.status.refresh_record_status
    record_status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "enrolments_record_status"),
        nullable=False,
        default=RecordStatus.AWAITING_EVIDENCE,
        server_default=RecordStatus.AWAITING_EVIDENCE.value,
    )
    # one sentence each: the row or case that decided the status, and what happens next
    status_reason: Mapped[str | None] = mapped_column(String)
    next_step: Mapped[str | None] = mapped_column(String)
    # when record_status last changed
    record_status_at: Mapped[datetime | None]
    # markers the college reported for category eligibility (D41): tfw_income_certified,
    # nri_sponsored, ciwg
    eligibility: Mapped[dict[str, Any]] = mapped_column(
        nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    student: Mapped[Student] = relationship(back_populates="enrolments")
    institution: Mapped[Institution] = relationship()  # noqa: F821
    programme: Mapped[Programme] = relationship()  # noqa: F821
    seat: Mapped[Seat | None] = relationship(foreign_keys=[seat_id])  # noqa: F821


class EnrolmentVersion(UUIDPk, Base):
    """One change to an enrolment (D42): {field: [before, after]}, what made it and who."""

    __tablename__ = "enrolment_versions"
    __table_args__ = (UniqueConstraint("enrolment_id", "version"),)

    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    # UPLOAD, DECISION or SEED (app.models.enums.VersionSource)
    source: Mapped[str] = mapped_column(String, nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))
    case_action_seq: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("case_actions.seq"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
