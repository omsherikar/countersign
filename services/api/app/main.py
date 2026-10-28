"""App factory: settings, logging, middleware, error envelope, routers, startup migration."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.factory import build_adapters
from app.core.config import get_settings
from app.core.errors import envelope, install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.db.session import dispose_engine, get_engine
from app.routers import (
    admin,
    auth,
    cases,
    credentials,
    dashboard,
    enrolments,
    flags,
    healthz,
    institutions,
    issuer,
    meta,
    notices,
    privacy,
    signals,
    students,
    university,
    uploads,
    users,
    verify,
)

log = logging.getLogger("countersign.api")

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# The routes that take a form instead of JSON: the file upload (API_CONTRACT §A2.1) and a
# college's response to a document request (§A3.1).
MULTIPART_ROUTES = {("POST", "/uploads")}
MULTIPART_PATTERNS = (("POST", re.compile(r"^/flags/[^/]+/response$")),)


def takes_form(method: str, path: str) -> bool:
    if (method, path) in MULTIPART_ROUTES:
        return True
    return any(method == m and pattern.match(path) for m, pattern in MULTIPART_PATTERNS)


def run_migrations() -> None:
    """`alembic upgrade head` in a worker thread (alembic env.py owns its own event loop)."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "alembic"))
    cfg.attributes["configure_logger"] = False  # keep the app's JSON logging in place
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auto_migrate:
        await asyncio.to_thread(run_migrations)
        log.info("migrations applied")
    get_engine()
    app.state.adapters = build_adapters(settings)
    log.info("api ready", extra={"adapter": settings.gov_adapter, "version": settings.api_version})
    try:
        yield
    finally:
        adapters = getattr(app.state, "adapters", None)
        if adapters is not None:
            await adapters.aclose()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Countersign API",
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.limiter = limiter
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        if request.method in MUTATING and _has_body(request):
            content_type = request.headers.get("content-type", "")
            multipart = takes_form(request.method, request.url.path)
            expected = "multipart/form-data" if multipart else "application/json"
            if not content_type.lower().startswith(expected):
                response = envelope(
                    415,
                    "UNSUPPORTED_MEDIA_TYPE",
                    f"Request bodies must be {expected}.",
                    {"content_type": content_type or None},
                )
                response.headers["x-request-id"] = request_id
                return response
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "user_id": str(getattr(request.state, "user_id", "")) or None,
            },
        )
        return response

    # registration order of ENGINES §16.9
    for router in (
        healthz,
        auth,
        issuer,
        notices,
        verify,
        privacy,
        dashboard,
        institutions,
        enrolments,
        flags,
        cases,
        signals,
        users,
        uploads,
        students,
        credentials,
        university,
        meta,
        admin,
    ):
        app.include_router(router.router)
    return app


def _has_body(request: Request) -> bool:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            return int(length) > 0
        except ValueError:
            return True
    return "transfer-encoding" in request.headers


app = create_app()
