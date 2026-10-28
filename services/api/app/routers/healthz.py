"""GET /healthz: database and redis, degraded (503) when either is down."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.ratelimit import PUBLIC_LIMIT, limiter
from app.db.session import get_engine

log = logging.getLogger("countersign.healthz")
router = APIRouter(tags=["health"])


async def _db_status() -> str:
    try:
        async with get_engine().connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2.0)
        return "ok"
    except Exception as exc:
        log.warning("db health check failed", extra={"error": str(exc)})
        return "down"


async def _redis_status() -> str:
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(get_settings().redis_url, socket_connect_timeout=1.0)
        try:
            await asyncio.wait_for(client.ping(), timeout=1.5)
        finally:
            await client.aclose()
        return "ok"
    except Exception as exc:
        log.warning("redis health check failed", extra={"error": str(exc)})
        return "down"


@router.get("/healthz")
@limiter.limit(PUBLIC_LIMIT)
async def healthz(request: Request) -> JSONResponse:
    db, redis_state = await asyncio.gather(_db_status(), _redis_status())
    ok = db == "ok" and redis_state == "ok"
    body = {
        "status": "ok" if ok else "degraded",
        "db": db,
        "redis": redis_state,
        "version": get_settings().api_version,
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)
