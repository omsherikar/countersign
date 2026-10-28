"""slowapi limiter shared by the routers (public routes 60/min, login 10/min per IP)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

PUBLIC_LIMIT = "60/minute"
LOGIN_LIMIT = "10/minute"

limiter = Limiter(
    key_func=get_remote_address,
    enabled=get_settings().rate_limits_enabled,
    headers_enabled=False,
)
