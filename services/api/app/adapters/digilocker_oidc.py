"""The DigiLocker sign-in client side: the authorize link and the id token (API_CONTRACT §A4.12).

Countersign is an OpenID Connect client of DigiLocker. In the demo the other side is
mockgov's labelled simulator (API_CONTRACT C.11, C.12), which signs the id token HS256 with
the client secret both sides hold. `read_id_token` is the one verification: signature,
`iss`, `aud` (the client id), `exp`, and the `nonce` this sign-in started with.
`mint_id_token` signs a token the same way, for the in-memory DigiLocker and tests.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlencode

import jwt

from app.adapters.base import DigiLockerIdentity, IdTokenInvalid
from app.core.config import Settings, get_settings

ALGORITHM = "HS256"
TOKEN_SECONDS = 600
LEEWAY_SECONDS = 30
_APAAR = re.compile(r"[0-9]{12}")


@dataclass(frozen=True, slots=True)
class OAuthClient:
    """What Countersign is registered as at DigiLocker."""

    client_id: str
    client_secret: str = field(repr=False)
    authorize_endpoint: str
    issuer: str

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> OAuthClient:
        settings = settings or get_settings()
        return cls(
            client_id=settings.digilocker_client_id,
            client_secret=settings.digilocker_client_secret,
            authorize_endpoint=settings.digilocker_authorize_url,
            issuer=settings.digilocker_issuer,
        )


def authorize_url(client: OAuthClient, *, state: str, nonce: str, redirect_uri: str) -> str:
    """`{authorize}?response_type=code&client_id&redirect_uri&scope=openid&state&nonce`."""
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid",
            "state": state,
            "nonce": nonce,
        }
    )
    joiner = "&" if "?" in client.authorize_endpoint else "?"
    return f"{client.authorize_endpoint}{joiner}{query}"


def _text(claims: dict[str, Any], key: str) -> str:
    value = claims.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IdTokenInvalid(f"no {key}")
    return value.strip()


def read_id_token(token: str, client: OAuthClient, *, nonce: str) -> DigiLockerIdentity:
    """The identity in a verified id token; IdTokenInvalid for anything that does not hold."""
    try:
        claims = jwt.decode(
            token,
            client.client_secret,
            algorithms=[ALGORITHM],
            audience=client.client_id,
            issuer=client.issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["iss", "sub", "aud", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise IdTokenInvalid(exc.__class__.__name__) from None
    sent = claims.get("nonce")
    if not isinstance(sent, str) or not nonce or not secrets.compare_digest(sent, nonce):
        raise IdTokenInvalid("nonce")
    try:
        birthdate = date.fromisoformat(_text(claims, "birthdate"))
    except ValueError:
        raise IdTokenInvalid("birthdate") from None
    apaar_id = claims.get("apaar_id")
    if apaar_id is not None and not (isinstance(apaar_id, str) and _APAAR.fullmatch(apaar_id)):
        raise IdTokenInvalid("apaar_id")
    gender = claims.get("gender")
    return DigiLockerIdentity(
        sub=_text(claims, "sub"),
        name=_text(claims, "name"),
        birthdate=birthdate,
        gender=gender if isinstance(gender, str) else None,
        apaar_id=apaar_id,
    )


def mint_id_token(
    client: OAuthClient,
    *,
    sub: str,
    name: str,
    birthdate: date,
    nonce: str | None,
    gender: str | None = None,
    apaar_id: str | None = None,
    issued_at: int | None = None,
    seconds: int = TOKEN_SECONDS,
) -> str:
    """An id token shaped and signed as mockgov's simulator signs it (API_CONTRACT C.12)."""
    now = int(time.time()) if issued_at is None else issued_at
    claims = {
        "iss": client.issuer,
        "sub": sub,
        "aud": client.client_id,
        "iat": now,
        "exp": now + seconds,
        "nonce": nonce,
        "name": name,
        "birthdate": birthdate.isoformat(),
        "gender": gender,
        "apaar_id": apaar_id,
    }
    return jwt.encode(claims, client.client_secret, algorithm=ALGORITHM, headers={"typ": "JWT"})
