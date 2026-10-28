"""Authorisation codes and id tokens for the simulated DigiLocker sign-in.

The simulator speaks the OAuth 2.0 authorisation code flow with an OpenID Connect style id
token (API_CONTRACT C.11, C.12): the student picks a synthetic account and enters the demo
OTP, the browser goes back to the caller with a one-time `code` (valid for 60 seconds), and
the caller exchanges it at `POST /digilocker/oauth/token` for an id token signed HS256 with
the client secret, which the api also holds.

Synthetic accounts only; not the real DigiLocker, and nothing here talks to it.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import DigiLockerAccount, DigiLockerAuthCode

DEMO_OTP = "123456"
ALGORITHM = "HS256"


class OAuthError(Exception):
    """An OAuth error answered as {"error", "error_description"}, not the mockgov envelope."""

    def __init__(self, status_code: int, error: str, description: str) -> None:
        super().__init__(description)
        self.status_code = status_code
        self.error = error
        self.description = description


INVALID_CLIENT = (401, "invalid_client", "Unknown client or wrong secret.")
INVALID_GRANT = (400, "invalid_grant", "The code is unknown, expired or used.")


def client_ok(settings: Settings, client_id: str, client_secret: str | None = None) -> bool:
    ok = secrets.compare_digest(client_id.encode(), settings.digilocker_client_id.encode())
    if client_secret is not None:
        expected = settings.digilocker_client_secret.encode()
        ok = secrets.compare_digest(client_secret.encode(), expected) and ok
    return ok


def redirect_allowed(settings: Settings, redirect_uri: str) -> bool:
    """Exactly one of DIGILOCKER_REDIRECT_URIS."""
    return redirect_uri in settings.digilocker_redirects()


def with_query(url: str, **params: str | None) -> str:
    """`url` with `params` added to its query string (empty values left out)."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, v) for k, v in params.items() if v]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


async def issue_code(
    session: AsyncSession,
    settings: Settings,
    *,
    account: DigiLockerAccount,
    client_id: str,
    redirect_uri: str,
    nonce: str | None,
) -> str:
    code = secrets.token_urlsafe(32)
    ttl = timedelta(seconds=settings.digilocker_code_ttl_seconds)
    session.add(
        DigiLockerAuthCode(
            code=code,
            digilocker_id=account.digilocker_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            nonce=nonce or None,
            expires_at=datetime.now(UTC) + ttl,
            used=False,
        )
    )
    await session.commit()
    return code


async def redeem_code(
    session: AsyncSession, code: str, client_id: str, redirect_uri: str
) -> tuple[DigiLockerAuthCode, DigiLockerAccount]:
    """Spends the code (once, even when it turns out expired or misdirected) and returns it
    with its account; every problem is the same invalid_grant."""
    row = await session.scalar(
        select(DigiLockerAuthCode).where(DigiLockerAuthCode.code == code).with_for_update()
    )
    if row is None or row.used:
        raise OAuthError(*INVALID_GRANT)
    row.used = True
    await session.commit()
    if row.expires_at <= datetime.now(UTC):
        raise OAuthError(*INVALID_GRANT)
    if row.client_id != client_id or row.redirect_uri != redirect_uri:
        raise OAuthError(*INVALID_GRANT)
    account = await session.get(DigiLockerAccount, row.digilocker_id)
    if account is None:
        raise OAuthError(*INVALID_GRANT)
    return row, account


def id_token(
    settings: Settings, account: DigiLockerAccount, client_id: str, nonce: str | None
) -> str:
    """HS256 with the client secret; `apaar_id` is null when the account has none."""
    now = int(time.time())
    claims = {
        "iss": settings.digilocker_issuer,
        "sub": account.digilocker_id,
        "aud": client_id,
        "iat": now,
        "exp": now + settings.digilocker_token_ttl_seconds,
        "nonce": nonce,
        "name": account.name,
        "birthdate": account.dob.isoformat(),
        "gender": account.gender,
        "apaar_id": account.apaar_id,
    }
    return jwt.encode(
        claims, settings.digilocker_client_secret, algorithm=ALGORITHM, headers={"typ": "JWT"}
    )
