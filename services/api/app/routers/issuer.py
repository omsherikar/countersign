"""What any verifier fetches: the issuer's keys, its metadata and the revocation status
list (API_CONTRACT A3.19). Public, 120 requests a minute per address across the three."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.core.errors import ApiError
from app.core.ratelimit import limiter
from app.credentials import keys, status_list

router = APIRouter(tags=["issuer"])

ISSUER_LIMIT = "120/minute"
STATUS_LIST_TYPE = "application/statuslist+jwt"


@router.get("/.well-known/jwks.json")
@limiter.shared_limit(ISSUER_LIMIT, scope="issuer")
async def jwks(request: Request, session: SessionDep) -> JSONResponse:
    """Every issuer key, active and retired; the first call makes the key."""
    return JSONResponse(await keys.jwks(session), headers={"Cache-Control": "public, max-age=300"})


@router.get("/.well-known/jwt-vc-issuer")
@limiter.shared_limit(ISSUER_LIMIT, scope="issuer")
async def jwt_vc_issuer(request: Request) -> dict[str, str]:
    issuer_url = get_settings().issuer_url
    return {"issuer": issuer_url, "jwks_uri": f"{issuer_url}/.well-known/jwks.json"}


@router.get("/status-lists/{list_id}")
@limiter.shared_limit(ISSUER_LIMIT, scope="issuer")
async def status_list_token(request: Request, list_id: str, session: SessionDep) -> Response:
    if list_id != str(status_list.LIST_ID):
        raise ApiError(404, "NOT_FOUND", "Status list not found.")
    token = await status_list.current(session)
    return Response(
        content=token.jwt,
        media_type=STATUS_LIST_TYPE,
        headers={"Cache-Control": "public, max-age=60"},
    )
