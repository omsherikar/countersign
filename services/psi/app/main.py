"""One image, two roles (PSI_ROLE): the partner regulator, or Countersign's PSI client.

    uvicorn --factory app.main:create_app      # role from PSI_ROLE

partner  POST /psi/setup     holds the partner's set; answers one encrypted request
client   POST /psi/compute   holds Countersign's set for one run; called only by the api
both     GET  /healthz
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import client, partner
from app.config import Role, Settings, get_settings


def _error_envelope(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    body = {"code": detail.get("code", "ERROR"), "message": detail.get("message", "")}
    return JSONResponse(status_code=exc.status_code, content={"error": body})


def _invalid_body(_request: Request, exc: Exception) -> JSONResponse:
    """422 without echoing the body back: the default handler repeats the input items."""
    assert isinstance(exc, RequestValidationError)
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(part) for part in first.get("loc", ()) if not isinstance(part, int))
    message = f"{where}: {first.get('msg', 'invalid')}" if where else "invalid body"
    return JSONResponse(
        status_code=422, content={"error": {"code": "PSI_BAD_REQUEST", "message": message}}
    )


def create_app(
    role: Role | None = None,
    settings: Settings | None = None,
    partner_http: httpx.Client | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = settings or get_settings()
    role = role or settings.role

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        own_http = None
        if role == "client" and getattr(app.state, "partner_http", None) is None:
            own_http = httpx.Client(base_url=settings.partner_url, timeout=settings.timeout_seconds)
            app.state.partner_http = own_http
        try:
            yield
        finally:
            if own_http is not None:
                own_http.close()

    app = FastAPI(title=f"Countersign PSI ({role})", lifespan=lifespan, docs_url=None)
    app.state.settings = settings
    app.add_exception_handler(HTTPException, _error_envelope)
    app.add_exception_handler(RequestValidationError, _invalid_body)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "role": role}

    if role == "partner":
        app.state.partner_store = partner.PartnerStore(settings)
        app.include_router(partner.router)
    else:
        app.state.partner_http = partner_http
        app.include_router(client.router)
    return app
