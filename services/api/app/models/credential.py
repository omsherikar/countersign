"""Credentials, their keys and presentations, consents, data requests, institution scores."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    CHAR,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models._types import pg_enum
from app.models.enums import (
    ConsentPurpose,
    ConsentState,
    CredentialKind,
    DataRequestKind,
    DataRequestStatus,
)


class Credential(UUIDPk, Timestamps, Base):
    __tablename__ = "credentials"
    __table_args__ = (
        # one live credential per enrolment and kind; revoked ones stay as history
        Index(
            "uq_credentials_enrolment_id_kind",
            "enrolment_id",
            "kind",
            unique=True,
            postgresql_where=text("revoked = false"),
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    enrolment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrolments.id"), nullable=False)
    kind: Mapped[CredentialKind] = mapped_column(
        pg_enum(CredentialKind, "credentials_kind"), nullable=False
    )
    sd_jwt: Mapped[str] = mapped_column(String, nullable=False)
    status_list_index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issued_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None]
    issuer_key_id: Mapped[str] = mapped_column(String, nullable=False)
    # SD-JWT VC type, e.g. "countersign:enrolment:v1"
    vct: Mapped[str] = mapped_column(String, nullable=False)
    # short public reference printed with a degree proof
    short_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(String)
    # null when the system revoked it (enrolment withdrawn or transferred)
    revoked_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # claim names the holder may choose to disclose
    disclosable: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'::text[]")
    )


class SigningKey(Base):
    """An issuer key. The private JWK is Fernet-encrypted with PII_FERNET_KEY."""

    __tablename__ = "signing_keys"
    __table_args__ = (
        # one active key per purpose
        Index(
            "uq_signing_keys_purpose_active",
            "purpose",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    # RFC 7638 JWK thumbprint
    kid: Mapped[str] = mapped_column(String, primary_key=True)
    alg: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False, server_default="ISSUER")
    public_jwk: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    private_jwk_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class HolderKey(Base):
    """A student's wallet key, kept by the custodial demo wallet (Fernet-encrypted)."""

    __tablename__ = "holder_keys"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), primary_key=True)
    public_jwk: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    private_jwk_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class CredentialPresentation(UUIDPk, Base):
    """One share: the holder's SD-JWT presentation, found by the hash of its share code."""

    __tablename__ = "credential_presentations"

    credential_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credentials.id"), nullable=False, index=True
    )
    # hex sha256 of the share code; the code itself is never stored
    code_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    presentation: Mapped[str] = mapped_column(String, nullable=False)
    disclosed: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    first_verified_at: Mapped[datetime | None]
    last_verified_at: Mapped[datetime | None]
    verify_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class Consent(UUIDPk, Timestamps, Base):
    __tablename__ = "consents"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(
        pg_enum(ConsentPurpose, "consents_purpose"), nullable=False
    )
    status: Mapped[ConsentState] = mapped_column(
        pg_enum(ConsentState, "consents_status"), nullable=False
    )
    notice_text: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    channel: Mapped[str] = mapped_column(String, nullable=False)
    enrolment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enrolments.id"))
    notice_version: Mapped[str] = mapped_column(
        String, nullable=False, default="v1", server_default="v1"
    )
    withdrawn_at: Mapped[datetime | None]


class DataRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "data_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    kind: Mapped[DataRequestKind] = mapped_column(
        pg_enum(DataRequestKind, "data_requests_kind"), nullable=False
    )
    status: Mapped[DataRequestStatus] = mapped_column(
        pg_enum(DataRequestStatus, "data_requests_status"),
        nullable=False,
        default=DataRequestStatus.OPEN,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    # what the student wrote, and the answer AICTE gave on resolving it
    details: Mapped[str | None] = mapped_column(String)
    response: Mapped[str | None] = mapped_column(String)
    resolved_at: Mapped[datetime | None]
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class InstitutionScore(UUIDPk, Timestamps, Base):
    __tablename__ = "institution_scores"
    __table_args__ = (UniqueConstraint("institution_id", "academic_year"),)

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    # the completeness percentage, 100 * uploaded_and_joined / joined; null when nothing
    # joined (D40)
    completeness_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    components: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
