"""slowapi limiter shared by the routers (public routes 60/min, login LOGIN_RATE_LIMIT per IP)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

PUBLIC_LIMIT = "60/minute"


def login_limit() -> str:
    """Sign-in attempts per IP, from LOGIN_RATE_LIMIT (default 10/minute)."""
    return get_settings().login_rate_limit


limiter = Limiter(
    key_func=get_remote_address,
    enabled=get_settings().rate_limits_enabled,
    headers_enabled=False,
)
