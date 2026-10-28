"""mockgov tables (docs/DATA_MODEL.md, "mockgov database").

Plaintext on purpose: this simulates the government's own registries and lives in its own
database that the Countersign API never queries directly.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApaarRecord(Base):
    __tablename__ = "apaar_registry"

    apaar_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)


class CounsellingAllotment(Base):
    __tablename__ = "counselling_allotments"
    __table_args__ = (
        UniqueConstraint("roll_no", name="uq_counselling_roll_no"),
        Index("ix_counselling_lookup", "state", "year", "programme", "dob"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    roll_no: Mapped[str] = mapped_column(Text, nullable=False)
    programme: Mapped[str] = mapped_column(Text, nullable=False)
    institution_aicte_id: Mapped[str] = mapped_column(Text, nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    allotment_ref: Mapped[str] = mapped_column(Text, nullable=False)


class AbcCredit(Base):
    __tablename__ = "abc_credits"
    __table_args__ = (UniqueConstraint("apaar_id", "academic_year", "sem", name="uq_abc_credit"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apaar_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(7), nullable=False)
    sem: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    # The body that issued the credits: the affiliating UNIVERSITY, or the INSTITUTION itself
    # for an autonomous college or a deemed university. Null for records loaded without one.
    issuer_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    issuer_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    issuer_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class DigiLockerMessage(Base):
    __tablename__ = "digilocker_inbox"

    inbox_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    apaar_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    callback_url: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DigiLockerAccount(Base):
    """A synthetic DigiLocker account for the sign-in simulator. `apaar_id` is null when the
    student has not linked an APAAR (consent refused or pending)."""

    __tablename__ = "digilocker_accounts"

    digilocker_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    apaar_id: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    apaar_last4: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)


class DigiLockerAuthCode(Base):
    """A one-time authorisation code of the sign-in simulator."""

    __tablename__ = "digilocker_auth_codes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    digilocker_id: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DigiLockerSigningKey(Base):
    """The simulator's id-token signing key (EC P-256), kept so restarts keep it."""

    __tablename__ = "digilocker_signing_keys"

    kid: Mapped[str] = mapped_column(String(64), primary_key=True)
    private_pem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SiiAdmission(Base):
    __tablename__ = "sii_admissions"
    __table_args__ = (UniqueConstraint("passport_no", name="uq_sii_passport_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    passport_no: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    nationality: Mapped[str] = mapped_column(String(2), nullable=False)
    institution_aicte_id: Mapped[str] = mapped_column(Text, nullable=False)
    programme: Mapped[str] = mapped_column(Text, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(7), nullable=False)


class AdmissionJoining(Base):
    """One joining in the state admission authority's approved-admissions list.

    One state's record format, simulated, served for every state: the student reported and
    joined at this college in this programme. Counselling, TFW and lateral admissions carry the
    entrance exam's roll number; management, NRI and spot admissions the authority's own
    approval number. International admissions are not here (they are in Study in India).
    """

    __tablename__ = "admission_joinings"
    __table_args__ = (
        UniqueConstraint("roll_no", name="uq_admission_joining_roll_no"),
        Index(
            "ix_admission_joining_lookup",
            "state",
            "academic_year",
            "institution_code",
            "programme",
            "dob",
        ),
        Index("ix_admission_joining_institution", "institution_code", "academic_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(7), nullable=False)
    roll_no: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    institution_code: Mapped[str] = mapped_column(Text, nullable=False)
    programme: Mapped[str] = mapped_column(Text, nullable=False)
    joined_on: Mapped[date] = mapped_column(Date, nullable=False)
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)


class ChaosSetting(Base):
    __tablename__ = "chaos"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_rate: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    down: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


SEED_TABLES = (
    ApaarRecord.__table__,
    CounsellingAllotment.__table__,
    AbcCredit.__table__,
    SiiAdmission.__table__,
    AdmissionJoining.__table__,
    DigiLockerAccount.__table__,
    DigiLockerMessage.__table__,
)
