"""PII at rest: HMAC for lookup, Fernet copy, masked wire shapes (ARCHITECTURE §6)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

Kind = Literal["apaar", "mobile", "address", "passport", "generic"]

_DIGITS = re.compile(r"\D+")
_SPACES = re.compile(r"\s+")


def normalise(value: str, kind: Kind = "generic") -> str:
    """Canonical form hashed for lookup: digits for ids/mobiles, folded text for addresses."""
    value = value.strip()
    if kind in ("apaar", "mobile"):
        return _DIGITS.sub("", value)
    if kind == "address":
        return _SPACES.sub(" ", value.lower())
    if kind == "passport":
        return _SPACES.sub("", value.upper())
    return value


def _hmac_key() -> bytes:
    raw = get_settings().pii_hmac_key
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode()


def hmac_id(value: str, kind: Kind = "generic") -> str:
    """Hex HMAC-SHA256 of the normalised value under PII_HMAC_KEY."""
    return hmac.new(_hmac_key(), normalise(value, kind).encode(), hashlib.sha256).hexdigest()


def hmac_bytes(value: str, kind: Kind = "generic") -> bytes:
    """Same digest as raw bytes, the shape the `*_hmac` bytea columns store."""
    return bytes.fromhex(hmac_id(value, kind))


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().pii_fernet_key.encode()
    try:
        return Fernet(key)
    except ValueError:
        # Not a 32-byte urlsafe-base64 key: derive one so any string in .env works.
        derived = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return Fernet(derived)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as exc:
        raise ValueError("ciphertext does not verify under PII_FERNET_KEY") from exc


def last4(value: str, kind: Kind = "apaar") -> str | None:
    digits = normalise(value, kind)
    return digits[-4:] if len(digits) >= 4 else (digits or None)


def mask_apaar(value: str | None) -> str | None:
    """Full APAAR or just its last four -> "XXXX XXXX 4417"; None stays None."""
    if not value:
        return None
    tail = last4(value, "apaar")
    if not tail:
        return None
    return f"XXXX XXXX {tail}"


def mask_mobile(value: str | None) -> str | None:
    """Full mobile or just its last four -> "XXXXXX1234"; None stays None."""
    if not value:
        return None
    tail = last4(value, "mobile")
    if not tail:
        return None
    return f"XXXXXX{tail}"


def mask_passport(value: str | None) -> str | None:
    if not value:
        return None
    clean = normalise(value, "passport")
    if not clean:
        return None
    return "X" + clean[1:]


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalise_name(name: str) -> str:
    """Week 1 name normalisation: lower-case, punctuation stripped, spaces collapsed."""
    return _SPACES.sub(" ", _PUNCT.sub(" ", name.lower())).strip()
