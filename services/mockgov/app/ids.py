"""ULID-style identifiers (time-sortable, Crockford base32) for inbox messages."""

import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def ulid() -> str:
    timestamp_ms = int(time.time() * 1000)
    randomness = secrets.randbits(80)
    return _encode(timestamp_ms, 10) + _encode(randomness, 16)


def inbox_id() -> str:
    return f"ib_{ulid()}"
