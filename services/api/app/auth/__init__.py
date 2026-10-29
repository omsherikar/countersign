"""Student sign-in (D37): students sign in only through DigiLocker; see `digilocker`."""

from __future__ import annotations

import secrets

# a password hash nobody can match: a STUDENT account has no password (DATA_MODEL users)
UNUSABLE_PREFIX = "!"


def unusable_password_hash() -> str:
    """32 random bytes that nobody keeps, marked so they never parse as a real hash."""
    return UNUSABLE_PREFIX + secrets.token_hex(32)
