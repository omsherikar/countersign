"""Issuer and holder keys (D26).

The issuer key signs every credential, the degree QR and the status list. Its private JWK
is kept Fernet-encrypted under PII_FERNET_KEY in `signing_keys`, its kid is the RFC 7638
thumbprint, and it is created on first use; retired keys stay in the JWKS so what they
signed still verifies. Each student has a holder key in `holder_keys` (the demo wallet is
custodial; a real deployment keeps it on the student's device).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from jwcrypto.jwk import JWK
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models.credential import HolderKey, SigningKey

ALG = "ES256"
PURPOSE = "ISSUER"


@dataclass(frozen=True, slots=True)
class IssuerKey:
    kid: str
    jwk: JWK  # private; never logged


def thumbprint(key: JWK) -> str:
    """RFC 7638 JWK thumbprint, SHA-256, base64url without padding."""
    return key.thumbprint()


def generate() -> JWK:
    """A fresh P-256 key whose kid is its thumbprint."""
    key = JWK.generate(kty="EC", crv="P-256")
    return JWK(**key.export_private(as_dict=True), kid=thumbprint(key))


def published(key: JWK) -> dict[str, Any]:
    """The public JWK as the JWKS serves it."""
    return {**key.export_public(as_dict=True), "use": "sig", "alg": ALG}


def _seal(key: JWK) -> str:
    return crypto.encrypt(key.export_private()).decode("ascii")


def _open(sealed: str) -> JWK:
    return JWK.from_json(crypto.decrypt(sealed.encode("ascii")))


async def _active_row(session: AsyncSession) -> SigningKey | None:
    return (
        await session.execute(
            select(SigningKey).where(SigningKey.purpose == PURPOSE, SigningKey.active.is_(True))
        )
    ).scalar_one_or_none()


async def active_issuer_key(session: AsyncSession) -> IssuerKey:
    """The one active issuer key, created on first use.

    Two first uses can race: the partial unique index on (purpose) WHERE active lets one
    insert win and the other does nothing (or fails inside its savepoint), then both read
    the winner.
    """
    row = await _active_row(session)
    if row is None:
        key = generate()
        stmt = (
            insert(SigningKey)
            .values(
                kid=key["kid"],
                alg=ALG,
                purpose=PURPOSE,
                public_jwk=published(key),
                private_jwk_encrypted=_seal(key),
                active=True,
            )
            .on_conflict_do_nothing(index_elements=["purpose"], index_where=text("active"))
        )
        try:
            async with session.begin_nested():
                await session.execute(stmt)
        except IntegrityError:
            pass
        row = await _active_row(session)
        if row is None:  # pragma: no cover - the insert above or its rival left one
            raise RuntimeError("no active issuer key after creating one")
    return IssuerKey(kid=row.kid, jwk=_open(row.private_jwk_encrypted))


async def jwks(session: AsyncSession) -> dict[str, Any]:
    """{"keys": [...]}: every issuer key, active first, then the retired ones."""
    await active_issuer_key(session)
    rows = (
        (
            await session.execute(
                select(SigningKey)
                .where(SigningKey.purpose == PURPOSE)
                .order_by(SigningKey.active.desc(), SigningKey.created_at, SigningKey.kid)
            )
        )
        .scalars()
        .all()
    )
    return {"keys": [dict(row.public_jwk) for row in rows]}


def key_in(document: dict[str, Any], kid: str | None) -> JWK | None:
    """The public key with this kid in a JWKS document, or None."""
    if not kid:
        return None
    for entry in document.get("keys", []):
        if isinstance(entry, dict) and entry.get("kid") == kid:
            return JWK(**entry)
    return None


async def public_key(session: AsyncSession, kid: str) -> JWK | None:
    """The public key for kid, read from the JWKS document exactly as a third party would."""
    return key_in(await jwks(session), kid)


async def holder_key(session: AsyncSession, student_id: uuid.UUID, *, create: bool) -> JWK | None:
    """The student's private holder key; created when missing and `create` is true."""
    row = await session.get(HolderKey, student_id)
    if row is None and create:
        key = generate()
        stmt = (
            insert(HolderKey)
            .values(
                student_id=student_id,
                public_jwk=key.export_public(as_dict=True),
                private_jwk_encrypted=_seal(key),
            )
            .on_conflict_do_nothing(index_elements=["student_id"])
        )
        await session.execute(stmt)
        row = await session.get(HolderKey, student_id, populate_existing=True)
    return _open(row.private_jwk_encrypted) if row is not None else None
