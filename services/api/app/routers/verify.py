"""The public verifier (API_CONTRACT A3.20, §A4.15): no sign-in, 60 requests a minute per
address across the routes together (D32 limits /verify/* as one).

The completion attestation routes are declared before /verify/{code} so their paths are
never read as a share code. `/verify/degree/{short_id}` answers as before, for blocks
already printed with that address.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from slowapi.util import get_remote_address

from app.core.deps import SessionDep
from app.core.ratelimit import limiter
from app.credentials import verifier
from app.schemas.credentials import VerifyPasteRequest, VerifyResult

router = APIRouter(prefix="/verify", tags=["verify"])

VERIFY_LIMIT = "60/minute"


def _ip(request: Request) -> str:
    return get_remote_address(request) or "unknown"


@router.get("/d/{jws}", response_model=VerifyResult)
@limiter.shared_limit(VERIFY_LIMIT, scope="verify")
async def verify_degree_qr(request: Request, jws: str, session: SessionDep) -> dict:
    return await verifier.verify_degree_jws(session, jws, ip=_ip(request))


@router.get("/completion/{short_id}", response_model=VerifyResult)
@limiter.shared_limit(VERIFY_LIMIT, scope="verify")
async def verify_completion_id(request: Request, short_id: str, session: SessionDep) -> dict:
    return await verifier.verify_degree_id(session, short_id, ip=_ip(request))


@router.get("/degree/{short_id}", response_model=VerifyResult, include_in_schema=False)
@limiter.shared_limit(VERIFY_LIMIT, scope="verify")
async def verify_degree_id(request: Request, short_id: str, session: SessionDep) -> dict:
    return await verifier.verify_degree_id(session, short_id, ip=_ip(request))


@router.get("/{code}", response_model=VerifyResult)
@limiter.shared_limit(VERIFY_LIMIT, scope="verify")
async def verify_code(request: Request, code: str, session: SessionDep) -> dict:
    return await verifier.verify_code(session, code, ip=_ip(request))


@router.post("", response_model=VerifyResult)
@limiter.shared_limit(VERIFY_LIMIT, scope="verify")
async def verify_pasted(request: Request, body: VerifyPasteRequest, session: SessionDep) -> dict:
    return await verifier.verify_presentation(session, body.presentation, ip=_ip(request))
