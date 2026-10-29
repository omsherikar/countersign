"""Countersign's PSI client, a sidecar on Countersign's side of the network.

The api cannot run the protocol itself (openmined.psi has no linux arm64 wheel, and the api
image is native), so it hands its set to this process, which runs only for the api and
calls nobody but the partner. It keeps Countersign's set in memory for one run, sends the
partner only the encrypted request, and returns three counts. Nothing here logs an item.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app import protocol
from app.config import Settings

log = logging.getLogger("countersign.psi.client")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ComputeRequest(BaseModel):
    # Countersign's set: hex HMAC-SHA256 of each linked student's APAAR
    items: list[str] = Field(max_length=2_000_000)

    @field_validator("items")
    @classmethod
    def _hex_digests(cls, items: list[str]) -> list[str]:
        if not all(_HEX64.match(item) for item in items):
            raise ValueError("every item must be a lower-case hex SHA-256 digest")
        return items


class ComputeAnswer(BaseModel):
    countersign_count: int
    partner_count: int
    overlap: int


router = APIRouter(prefix="/psi", tags=["client"])


def _partner_error(message: str, status: int = 502) -> HTTPException:
    return HTTPException(status, {"code": "PARTNER_UNAVAILABLE", "message": message})


def _b64(value: object) -> bytes:
    if not isinstance(value, str):
        raise _partner_error("the partner's answer is not a PSI answer")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise _partner_error("the partner's answer is not a PSI answer") from None


@router.post("/compute", response_model=ComputeAnswer)
def compute(body: ComputeRequest, request: Request) -> ComputeAnswer:
    """Run one cardinality PSI with the partner over Countersign's set."""
    settings: Settings = request.app.state.settings
    items = sorted(set(body.items))
    if len(items) > settings.max_items:
        raise HTTPException(413, {"code": "PSI_TOO_LARGE", "message": "too many items"})
    run = protocol.ClientRun(items)
    partner: httpx.Client = request.app.state.partner_http
    try:
        answer = partner.post(
            "/psi/setup", json={"request": base64.b64encode(run.request).decode()}
        )
    except httpx.HTTPError as exc:
        log.warning("partner not reachable: %s", exc.__class__.__name__)
        raise _partner_error("the partner registry is not reachable", 503) from None
    if answer.status_code != 200:
        log.warning("partner answered %s", answer.status_code)
        raise _partner_error(f"the partner registry answered {answer.status_code}")
    try:
        data = answer.json()
    except ValueError:
        raise _partner_error("the partner's answer is not a PSI answer") from None
    partner_count = data.get("partner_count") if isinstance(data, dict) else None
    if not isinstance(partner_count, int) or partner_count < 0:
        raise _partner_error("the partner's answer is not a PSI answer")
    try:
        overlap = run.intersection_size(_b64(data.get("setup")), _b64(data.get("response")))
    except protocol.ProtocolError:
        raise _partner_error("the partner's answer is not a PSI answer") from None
    log.info("run done: %d and %d items, overlap %d", run.count, partner_count, overlap)
    return ComputeAnswer(countersign_count=run.count, partner_count=partner_count, overlap=overlap)
