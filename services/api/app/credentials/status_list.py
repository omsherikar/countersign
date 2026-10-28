"""The IETF Token Status List of every credential (D26, API_CONTRACT A3.15).

One bit per credential at its `status_list_index`, 1 meaning revoked: 131,072 entries,
16,384 bytes, least significant bit first (index 48213 is bit 5 of byte 6026), compressed
with zlib and base64url-encoded into `lst`. The signed token is rebuilt at most every 60
seconds per process and at once after a revocation made in this process; the verifier
reads its bits from the same token anyone can fetch at /status-lists/1.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jwcrypto.jws import JWS
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.credentials import keys
from app.models.credential import Credential

SIZE = 131_072
LIST_ID = 1
TTL_SECONDS = 60
TOKEN_LIFETIME = timedelta(days=1)
TYP = "statuslist+jwt"


@dataclass(frozen=True, slots=True)
class StatusListToken:
    jwt: str
    iat: datetime
    bits: bytes  # the 16,384 uncompressed bytes


_cached: StatusListToken | None = None
_built_at = 0.0


def uri() -> str:
    return f"{get_settings().issuer_url}/status-lists/{LIST_ID}"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def pack(revoked_indexes: Iterable[int]) -> bytes:
    bits = bytearray(SIZE // 8)
    for index in revoked_indexes:
        if not 0 <= index < SIZE:
            raise ValueError(f"status list index {index} is outside 0 to {SIZE - 1}")
        bits[index // 8] |= 1 << (index % 8)
    return bytes(bits)


def encode(revoked_indexes: Iterable[int]) -> str:
    """The `lst` value: zlib-compressed bits, base64url without padding, LSB first."""
    return b64url(zlib.compress(pack(revoked_indexes), 9))


def decode(lst: str) -> bytes:
    return zlib.decompress(b64url_decode(lst))


def bit(bits: bytes, index: int) -> int:
    return (bits[index // 8] >> (index % 8)) & 1


async def _build(session: AsyncSession) -> StatusListToken:
    revoked = (
        (
            await session.execute(
                select(Credential.status_list_index).where(Credential.revoked.is_(True))
            )
        )
        .scalars()
        .all()
    )
    bits = pack(revoked)
    key = await keys.active_issuer_key(session)
    iat = datetime.now(UTC).replace(microsecond=0)
    payload = {
        "iss": get_settings().issuer_url,
        "sub": uri(),
        "iat": int(iat.timestamp()),
        "exp": int((iat + TOKEN_LIFETIME).timestamp()),
        "ttl": TTL_SECONDS,
        "status_list": {"bits": 1, "lst": b64url(zlib.compress(bits, 9))},
    }
    token = JWS(payload=json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    header = {"alg": keys.ALG, "kid": key.kid, "typ": TYP}
    token.add_signature(key.jwk, alg=keys.ALG, protected=json.dumps(header))
    return StatusListToken(jwt=token.serialize(compact=True), iat=iat, bits=bits)


async def current(session: AsyncSession) -> StatusListToken:
    """The signed token, rebuilt when older than TTL_SECONDS or invalidated."""
    global _cached, _built_at
    if _cached is not None and time.monotonic() - _built_at < TTL_SECONDS:
        return _cached
    built = await _build(session)
    _cached, _built_at = built, time.monotonic()
    return built


def invalidate() -> None:
    """Drop this process's token so the next read rebuilds it."""
    global _cached
    _cached = None


def invalidate_after_commit(session: AsyncSession) -> None:
    """Invalidate now and again once the session commits, so a token rebuilt in between
    from the uncommitted state is not served for the rest of its minute."""
    invalidate()
    event.listen(session.sync_session, "after_commit", lambda _s: invalidate(), once=True)


async def allocate_index(session: AsyncSession) -> int:
    """A random index no credential holds. Two issuers can still pick the same one at once;
    the unique constraint catches that and the caller draws again."""
    for _ in range(64):
        index = secrets.randbelow(SIZE)
        taken = (
            await session.execute(
                select(Credential.id).where(Credential.status_list_index == index).limit(1)
            )
        ).first()
        if taken is None:
            return index
    raise RuntimeError("status list is too full to allocate an index")
