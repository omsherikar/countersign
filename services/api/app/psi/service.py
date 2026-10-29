"""Private set intersection with a partner regulator (D48, API_CONTRACT §A4.26).

Countersign and a partner regulator (in the demo, a mock UGC: compose service `psi`) learn
how many APAAR-linked students they both hold, and nothing about which ones.

Countersign's set is the APAAR HMAC of every LINKED student. It leaves the api only for
Countersign's own PSI client (compose service `psi-client`, `PSI_CLIENT_URL`), which exists
because openmined.psi has no wheel for the api's arm64 image. That client encrypts the set
under a key of its own before anything reaches the partner, and returns three counts. The
partner's set never leaves the partner. Nothing here logs an item.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.errors import ApiError
from app.models.enums import AuditAction, ConsentStatus
from app.models.student import Student

log = logging.getLogger("countersign.psi")

METHOD = "ECDH PSI cardinality (OpenMined)"
PARTNER = "UGC (mock)"
AUDIT_ENTITY = "psi_run"


@dataclass(frozen=True)
class Counts:
    countersign_count: int
    partner_count: int
    overlap: int


async def countersign_items(session: AsyncSession) -> list[str]:
    """Hex APAAR HMACs of the linked students, the same digest the partner computes."""
    rows = await session.execute(
        select(Student.apaar_hmac).where(
            Student.consent_status == ConsentStatus.LINKED, Student.apaar_hmac.is_not(None)
        )
    )
    return sorted(digest.hex() for digest in rows.scalars())


def _unavailable(detail: str) -> ApiError:
    return ApiError(
        503,
        "PSI_UNAVAILABLE",
        "The partner registry did not answer, so no overlap was computed. Try again in a minute.",
        {"source": "psi", "detail": detail},
    )


def _http_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(base_url=settings.psi_client_url, timeout=settings.psi_timeout_seconds)


async def run_client(items: list[str]) -> Counts:
    """One run through Countersign's PSI client."""
    try:
        async with _http_client() as client:
            response = await client.post("/psi/compute", json={"items": items})
    except httpx.HTTPError as exc:
        raise _unavailable(exc.__class__.__name__) from exc
    if response.status_code != 200:
        try:
            code = response.json()["error"]["code"]
        except (ValueError, KeyError, TypeError):
            code = f"HTTP_{response.status_code}"
        raise _unavailable(str(code))
    try:
        body = response.json()
        counts = Counts(
            countersign_count=int(body["countersign_count"]),
            partner_count=int(body["partner_count"]),
            overlap=int(body["overlap"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise _unavailable("BAD_ANSWER") from exc
    if counts.countersign_count != len(items) or not 0 <= counts.overlap <= min(
        counts.countersign_count, counts.partner_count
    ):
        raise _unavailable("BAD_ANSWER")
    return counts


async def compute(
    session: AsyncSession, *, actor_id: uuid.UUID, request_id: str | None
) -> dict[str, object]:
    """Run the protocol over Countersign's set and record the run (counts only) in the audit."""
    items = await countersign_items(session)
    counts = await run_client(items)
    computed_at = datetime.now(UTC)
    result: dict[str, object] = {
        "countersign_count": counts.countersign_count,
        "partner_count": counts.partner_count,
        "overlap": counts.overlap,
        "computed_at": computed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "method": METHOD,
    }
    await audit.record(
        session,
        actor_id,
        AuditAction.CREATE,
        AUDIT_ENTITY,
        entity_id=uuid.uuid4(),
        after={**result, "partner": PARTNER},
        request_id=request_id,
    )
    log.info(
        "psi run",
        extra={
            "countersign_count": counts.countersign_count,
            "partner_count": counts.partner_count,
            "overlap": counts.overlap,
        },
    )
    return result
