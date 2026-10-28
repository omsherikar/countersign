"""/admin/*: audit list and verify, adapter ping, chaos passthrough, demo reset (AICTE_ADMIN)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core import audit
from app.core.config import get_settings
from app.core.deps import Adapters, RequestId, SessionDep, require_roles
from app.core.errors import ApiError
from app.models.audit import AuditLog
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.schemas.admin import AdapterPing, AuditRow, AuditVerify, ChaosRequest, SourcePing
from app.schemas.common import Page, PageParams, page_params

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
Paging = Annotated[PageParams, Depends(page_params)]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@router.get("/adapters/ping", response_model=AdapterPing)
async def adapters_ping(_user: AdminUser, adapters: Adapters) -> AdapterPing:
    from app.adapters.factory import ping_all

    results = await ping_all(adapters)
    return AdapterPing(
        adapter=adapters.name,
        sources={
            source: SourcePing(status=r.status, latency_ms=r.latency_ms, detail=r.detail)
            for source, r in results.items()
        },
        checked_at=_now(),
    )


@router.get("/audit/verify", response_model=AuditVerify)
async def audit_verify(session: SessionDep, _user: AdminUser) -> AuditVerify:
    ok, length, first_broken = await audit.verify_chain(session)
    return AuditVerify(ok=ok, length=length, first_broken_seq=first_broken, checked_at=_now())


@router.get("/audit", response_model=Page[AuditRow])
async def audit_list(
    session: SessionDep,
    _user: AdminUser,
    paging: Paging,
    actor_id: uuid.UUID | None = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[AuditRow]:
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(AuditLog.seq.desc()).offset(paging.offset).limit(paging.page_size)
        )
    ).all()
    items = [
        AuditRow(
            seq=row.seq,
            at=_iso(row.at),
            actor_id=str(row.actor_id) if row.actor_id else None,
            actor_email=email,
            action=row.action.value,
            entity_type=row.entity_type,
            entity_id=str(row.entity_id) if row.entity_id else None,
            hash=row.hash,
            prev_hash=row.prev_hash,
        )
        for row, email in rows
    ]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


# ------------------------------------------------------------- chaos passthrough


async def _mockgov(method: str, path: str, json: Any | None = None) -> JSONResponse:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=settings.mockgov_base_url, timeout=settings.gov_timeout_seconds
        ) as client:
            response = await client.request(method, path, json=json)
    except httpx.HTTPError as exc:
        raise ApiError(
            503,
            "SOURCE_UNAVAILABLE",
            "mockgov is not reachable.",
            {"source": "mockgov", "detail": exc.__class__.__name__},
        ) from exc
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    return JSONResponse(status_code=response.status_code, content=body)


@router.get("/chaos")
async def chaos_get(session: SessionDep, user: AdminUser, request_id: RequestId) -> JSONResponse:
    await audit.record(session, user.id, AuditAction.READ, "mockgov_chaos", request_id=request_id)
    return await _mockgov("GET", "/admin/chaos")


@router.post("/chaos")
async def chaos_set(
    body: ChaosRequest, session: SessionDep, user: AdminUser, request_id: RequestId
) -> JSONResponse:
    payload = body.model_dump()
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "mockgov_chaos",
        after=payload,
        request_id=request_id,
    )
    return await _mockgov("POST", "/admin/chaos", payload)


@router.post("/chaos/reset")
async def chaos_reset(session: SessionDep, user: AdminUser, request_id: RequestId) -> JSONResponse:
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "mockgov_chaos",
        after={"reset": True},
        request_id=request_id,
    )
    return await _mockgov("POST", "/admin/chaos/reset")


@router.post("/demo/reset")
async def demo_reset(_user: AdminUser) -> None:
    raise ApiError(501, "NOT_IMPLEMENTED", "Run make demo-reset.")
