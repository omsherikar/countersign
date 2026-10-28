"""Signing keys, authorisation codes and id tokens for the simulated DigiLocker sign-in.

The simulator speaks the OAuth 2.0 authorisation code flow with an OpenID Connect style id
token: the student picks a synthetic account and enters the demo OTP, the browser goes back to
the caller with a one-time `code` (valid for five minutes), and the caller exchanges it at
`POST /digilocker/oauth/token` for an id token signed with ES256. The public key is published
at `GET /digilocker/oauth/jwks` under its RFC 7638 thumbprint as `kid`.

Synthetic accounts only; not the real DigiLocker, and nothing here talks to it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import MockGovError
from app.models import DigiLockerAccount, DigiLockerAuthCode, DigiLockerSigningKey

DEMO_OTP = "123456"
ALGORITHM = "ES256"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SigningKey:
    kid: str
    private_key: ec.EllipticCurvePrivateKey

    @classmethod
    def from_pem(cls, pem: str) -> SigningKey:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise ValueError("the DigiLocker signing key must be an EC P-256 private key")
        return cls(kid=_thumbprint(key), private_key=key)

    def pem(self) -> str:
        return self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")

    def jwk(self) -> dict[str, str]:
        return {**_public_jwk(self.private_key), "kid": self.kid, "use": "sig", "alg": ALGORITHM}


def _public_jwk(key: ec.EllipticCurvePrivateKey) -> dict[str, str]:
    numbers = key.public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(numbers.x.to_bytes(32, "big")),
        "y": _b64url(numbers.y.to_bytes(32, "big")),
    }


def _thumbprint(key: ec.EllipticCurvePrivateKey) -> str:
    """RFC 7638: SHA-256 of the required members, sorted, without whitespace."""
    members = _public_jwk(key)
    canonical = json.dumps(members, sort_keys=True, separators=(",", ":"))
    return _b64url(hashlib.sha256(canonical.encode("ascii")).digest())


async def load_signing_key(session: AsyncSession, settings: Settings) -> SigningKey:
    """The configured key, else the oldest stored one, else a new key stored for next time."""
    if settings.mockgov_digilocker_signing_key.strip():
        return SigningKey.from_pem(settings.mockgov_digilocker_signing_key)
    stored = await session.scalar(
        select(DigiLockerSigningKey).order_by(DigiLockerSigningKey.created_at).limit(1)
    )
    if stored is None:
        generated = ec.generate_private_key(ec.SECP256R1())
        fresh = SigningKey(kid=_thumbprint(generated), private_key=generated)
        await session.execute(
            insert(DigiLockerSigningKey)
            .values(kid=fresh.kid, private_pem=fresh.pem(), created_at=datetime.now(UTC))
            .on_conflict_do_nothing()
        )
        await session.commit()
        # Another worker may have stored its key first: everyone uses the oldest.
        stored = await session.scalar(
            select(DigiLockerSigningKey).order_by(DigiLockerSigningKey.created_at).limit(1)
        )
    return SigningKey.from_pem(stored.private_pem)


# ------------------------------------------------------------------ redirects


def redirect_allowed(settings: Settings, redirect_uri: str) -> bool:
    """An http(s) URL without credentials or fragment, under one of the configured prefixes."""
    try:
        parts = urlsplit(redirect_uri)
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if parts.username or parts.password or parts.fragment:
        return False
    prefixes = settings.digilocker_redirect_prefixes()
    return any(redirect_uri.startswith(prefix) for prefix in prefixes)


def origin_of(redirect_uri: str) -> str:
    parts = urlsplit(redirect_uri)
    return f"{parts.scheme}://{parts.netloc}"


def with_query(url: str, **params: str) -> str:
    """`url` with `params` added to its query string."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, v) for k, v in params.items() if v]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


# ---------------------------------------------------------------------- codes


class InvalidClient(MockGovError):
    def __init__(self) -> None:
        super().__init__(401, "INVALID_CLIENT", "Unknown client or wrong client secret.")


class InvalidGrant(MockGovError):
    def __init__(self, message: str) -> None:
        super().__init__(400, "INVALID_GRANT", message)


def client_ok(settings: Settings, client_id: str, client_secret: str | None = None) -> bool:
    ok = secrets.compare_digest(client_id.encode(), settings.mockgov_digilocker_client_id.encode())
    if client_secret is not None:
        expected = settings.mockgov_digilocker_client_secret.encode()
        ok = secrets.compare_digest(client_secret.encode(), expected) and ok
    return ok


async def issue_code(
    session: AsyncSession,
    settings: Settings,
    *,
    account: DigiLockerAccount,
    client_id: str,
    redirect_uri: str,
    nonce: str | None,
) -> str:
    now = datetime.now(UTC)
    code = secrets.token_urlsafe(32)
    session.add(
        DigiLockerAuthCode(
            code=code,
            digilocker_id=account.digilocker_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            nonce=nonce or None,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.mockgov_digilocker_code_ttl_seconds),
        )
    )
    await session.commit()
    return code


async def redeem_code(
    session: AsyncSession, code: str, client_id: str, redirect_uri: str
) -> tuple[DigiLockerAuthCode, DigiLockerAccount]:
    """Spends the code (once, even when it turns out expired or misdirected) and returns it
    with its account."""
    row = await session.scalar(
        select(DigiLockerAuthCode).where(DigiLockerAuthCode.code == code).with_for_update()
    )
    if row is None:
        raise InvalidGrant("The code is not known.")
    if row.used_at is not None:
        raise InvalidGrant("The code was already used.")
    now = datetime.now(UTC)
    row.used_at = now
    await session.commit()
    if row.expires_at <= now:
        raise InvalidGrant("The code has expired.")
    if row.client_id != client_id or row.redirect_uri != redirect_uri:
        raise InvalidGrant("The code was issued to another client or redirect URI.")
    account = await session.get(DigiLockerAccount, row.digilocker_id)
    if account is None:
        raise InvalidGrant("The account behind this code no longer exists.")
    return row, account


def id_token(
    key: SigningKey,
    settings: Settings,
    account: DigiLockerAccount,
    client_id: str,
    nonce: str | None,
) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": settings.mockgov_digilocker_issuer,
        "sub": account.digilocker_id,
        "aud": client_id,
        "iat": now,
        "exp": now + settings.mockgov_digilocker_token_ttl_seconds,
        "name": account.name,
        "dob": account.dob.isoformat(),
    }
    if account.gender:
        claims["gender"] = account.gender
    if account.apaar_id:
        claims["apaar_id"] = account.apaar_id
    if nonce:
        claims["nonce"] = nonce
    return jwt.encode(
        claims, key.private_key, algorithm=ALGORITHM, headers={"kid": key.kid, "typ": "JWT"}
    )
