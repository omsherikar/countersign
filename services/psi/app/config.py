"""Settings from the environment. The partner and the client each read only their own keys."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Role = Literal["partner", "client"]


@dataclass(frozen=True)
class Settings:
    role: Role
    # partner: where its registry comes from and how it is drawn (see app/partner.py)
    pii_hmac_key: str
    registry_path: str
    partner_seed: str
    partner_share: float
    partner_extras: int
    # client: where the partner answers
    partner_url: str
    timeout_seconds: float
    # both: the largest set either side accepts
    max_items: int


def get_settings() -> Settings:
    env = os.environ.get
    role = env("PSI_ROLE", "partner")
    if role not in ("partner", "client"):
        raise ValueError(f"PSI_ROLE must be partner or client, not {role!r}")
    return Settings(
        role=role,  # type: ignore[arg-type]
        pii_hmac_key=env("PII_HMAC_KEY", "00" * 32),
        registry_path=env("PSI_REGISTRY_PATH", "/data/generated/mockgov/apaar_registry.jsonl"),
        partner_seed=env("PSI_PARTNER_SEED", "ugc-mock-2026"),
        partner_share=float(env("PSI_PARTNER_SHARE", "0.04")),
        partner_extras=int(env("PSI_PARTNER_EXTRAS", "8000")),
        partner_url=env("PSI_PARTNER_URL", "http://psi:8002"),
        timeout_seconds=float(env("PSI_TIMEOUT_SECONDS", "120")),
        max_items=int(env("PSI_MAX_ITEMS", "500000")),
    )
