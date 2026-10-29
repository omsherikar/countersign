"""The partner regulator (a mock UGC) and the set it holds.

The partner's set is synthetic and built the same way every time from datagen's APAAR
registry (`mockgov/apaar_registry.jsonl`, the synthetic national registry):

- a fixed share of the registry (PSI_PARTNER_SHARE, default 4%), chosen by a keyed hash of
  each APAAR under PSI_PARTNER_SEED, stands for students the partner also counts (enrolled
  in a programme it regulates as well);
- PSI_PARTNER_EXTRAS (default 8,000) more APAAR-shaped numbers, drawn from a generator
  seeded with PSI_PARTNER_SEED and never in the registry, stand for students only the
  partner holds.

Each APAAR is held as HMAC-SHA256 of its digits under PII_HMAC_KEY, the form the api
stores (`students.apaar_hmac`), so the two sets are comparable. In the demo the partner
shares that key with Countersign; regulators doing this for real would agree a key, or run
the protocol on the APAAR numbers themselves, since the protocol hides them either way.

The partner never receives Countersign's set: only the client's request, which is the
client's items encrypted under a key the partner never sees. Nothing here logs an item.
"""

from __future__ import annotations

import base64
import binascii
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import protocol
from app.config import Settings
from app.registry import apaar_hmac, partner_apaars, read_registry

log = logging.getLogger("countersign.psi.partner")


@dataclass(frozen=True)
class PartnerSet:
    items: tuple[str, ...]
    source_mtime: float


class PartnerStore:
    """Builds the partner's set on first use; rebuilds it when the registry file changes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._current: PartnerSet | None = None

    def items(self) -> tuple[str, ...]:
        path = Path(self._settings.registry_path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            raise HTTPException(
                503,
                {
                    "code": "PARTNER_NOT_SEEDED",
                    "message": "The partner registry has no data yet. Run datagen first.",
                },
            ) from None
        with self._lock:
            if self._current is None or self._current.source_mtime != mtime:
                s = self._settings
                apaars = partner_apaars(
                    read_registry(path), s.partner_seed, s.partner_share, s.partner_extras
                )
                items = tuple(apaar_hmac(s.pii_hmac_key, a) for a in apaars)
                self._current = PartnerSet(items=items, source_mtime=mtime)
                log.info("partner set built: %d items", len(items))
            return self._current.items


class SetupRequest(BaseModel):
    # the client's request, a serialized psi_proto.Request, base64
    request: str = Field(min_length=1)


class SetupAnswer(BaseModel):
    setup: str
    response: str
    partner_count: int


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            422, {"code": "PSI_BAD_REQUEST", "message": "request is not base64"}
        ) from None


router = APIRouter(prefix="/psi", tags=["partner"])


@router.post("/setup", response_model=SetupAnswer)
def setup(body: SetupRequest, request: Request) -> SetupAnswer:
    """Answer one client request: the setup message for the partner's set and the response."""
    store: PartnerStore = request.app.state.partner_store
    settings: Settings = request.app.state.settings
    raw = _b64decode(body.request)
    items = store.items()
    try:
        if protocol.request_size(raw) > settings.max_items:
            raise HTTPException(
                413, {"code": "PSI_TOO_LARGE", "message": "too many items in one request"}
            )
        setup_message, response = protocol.answer(raw, items)
    except protocol.ProtocolError as exc:
        raise HTTPException(422, {"code": "PSI_BAD_REQUEST", "message": str(exc)}) from None
    return SetupAnswer(
        setup=base64.b64encode(setup_message).decode(),
        response=base64.b64encode(response).decode(),
        partner_count=len(items),
    )
