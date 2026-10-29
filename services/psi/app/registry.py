"""The partner's set, drawn the same way every time from datagen's APAAR registry.

Pure functions, no PSI library: see app/partner.py for what the set stands for.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
from pathlib import Path

_DIGITS = re.compile(r"\D+")


def apaar_hmac(key: str, apaar: str) -> str:
    """Hex HMAC-SHA256 of the APAAR's digits; the api's `hmac_id(apaar, "apaar")`."""
    try:
        raw_key = bytes.fromhex(key)
    except ValueError:
        raw_key = key.encode()
    digits = _DIGITS.sub("", apaar.strip())
    return hmac.new(raw_key, digits.encode(), hashlib.sha256).hexdigest()


def _chosen(seed: str, apaar: str, share: float) -> bool:
    digest = hashlib.sha256(f"{seed}|registry|{apaar}".encode()).digest()
    return int.from_bytes(digest[:8], "big") < share * 2**64


def partner_apaars(registry: list[str], seed: str, share: float, extras: int) -> list[str]:
    """The partner's APAAR numbers: a seeded share of the registry plus seeded extras."""
    known = set(registry)
    chosen = sorted({a for a in registry if _chosen(seed, a, share)})
    rng = random.Random(f"{seed}|extras")
    drawn: set[str] = set()
    while len(drawn) < extras:
        candidate = str(rng.randrange(10**11, 10**12))
        if candidate not in known:
            drawn.add(candidate)
    return chosen + sorted(drawn)


def read_registry(path: Path) -> list[str]:
    apaars = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                apaar = json.loads(line).get("apaar_id")
                if apaar:
                    apaars.append(str(apaar))
    return apaars
