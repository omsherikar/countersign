"""Signals: GET /signals, GET /signals/{id}, POST /signals/{id}/open-case,
POST /signals/{id}/dismiss, POST /signals/run (API_CONTRACT §A4.19, §A4.23).

Officers only; a college, a student and a university get 403 on every route.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import get_settings
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.ratelimit import limiter
from app.engine import status
from app.models.enums import Severity, SignalStatus, SignalType, UserRole
from app.models.user import User
from app.models.verification import Flag
from app.routers.flags import _base, _row
from app.routers.institutions import user_key
from app.schemas.common import PageParams, page_params
from app.schemas.flags import FlagRow
from app.schemas.signals import (
    SignalDetail,
    SignalDismissBody,
    SignalOpenCaseBody,
    SignalOpenCaseResult,
    SignalPage,
    SignalRunBody,
    SignalRunResult,
)
from app.signals import service

router = APIRouter(prefix="/signals", tags=["signals"])

OfficerUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
Paging = Annotated[PageParams, Depends(page_params)]
RUN_LIMIT = "2/minute"


@router.get("", response_model=SignalPage)
async def list_signals(
    session: SessionDep,
    user: OfficerUser,
    paging: Paging,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    type: SignalType | None = None,
    status: SignalStatus | None = None,
    institution_id: uuid.UUID | None = None,
    state: Annotated[str | None, Query(max_length=2)] = None,
    sort: Literal["newest", "score"] = "newest",
) -> SignalPage:
    page = await service.list_signals(
        session,
        user,
        service.SignalQuery(
            academic_year=academic_year or get_settings().academic_year,
            type=type,
            status=status,
            institution_id=institution_id,
            state=state,
            sort=sort,
            page=paging.page,
            page_size=paging.page_size,
        ),
    )
    return SignalPage(**page)


@router.post("/run", response_model=SignalRunResult)
@limiter.limit(RUN_LIMIT, key_func=user_key)
async def run_signals(
    request: Request, body: SignalRunBody, session: SessionDep, user: AdminUser
) -> SignalRunResult:
    return SignalRunResult(**await service.run(session, body.academic_year, actor_id=user.id))


@router.get("/{signal_id}", response_model=SignalDetail)
async def signal_detail(
    signal_id: uuid.UUID, session: SessionDep, user: OfficerUser, request_id: RequestId
) -> SignalDetail:
    return SignalDetail(**await service.detail(session, user, signal_id, request_id=request_id))


async def _flag_rows(session, user: User, flags: list[Flag]) -> list[FlagRow]:
    """The cases as the case list shows them (API_CONTRACT §A4.11)."""
    if not flags:
        return []
    rows = (await session.execute(_base().where(Flag.id.in_([f.id for f in flags])))).all()
    by_id = {r[0].id: r for r in rows}
    out = []
    for flag in flags:
        f, inst, st, rg, prog, who = by_id[flag.id]
        out.append(FlagRow(**_row(user, f, inst, st, rg, prog, who, len(f.related_enrolment_ids))))
    return out


@router.post("/{signal_id}/open-case", response_model=SignalOpenCaseResult, status_code=201)
async def open_case(
    signal_id: uuid.UUID,
    body: SignalOpenCaseBody,
    session: SessionDep,
    user: OfficerUser,
    request_id: RequestId,
) -> SignalOpenCaseResult:
    flags = await service.open_cases(
        session,
        user,
        signal_id,
        institution_ids=body.institution_ids,
        note=body.note,
        severity=Severity(body.severity) if body.severity else None,
    )
    # the records the new cases name read Under review before the response is built
    session.info.setdefault("actor_id", user.id)
    await status.settle(session)
    return SignalOpenCaseResult(
        cases=await _flag_rows(session, user, flags),
        signal=SignalDetail(
            **await service.detail(session, user, signal_id, request_id=request_id)
        ),
    )


@router.post("/{signal_id}/dismiss", response_model=SignalDetail)
async def dismiss_signal(
    signal_id: uuid.UUID,
    body: SignalDismissBody,
    session: SessionDep,
    user: OfficerUser,
    request_id: RequestId,
) -> SignalDetail:
    return SignalDetail(
        **await service.dismiss(session, user, signal_id, note=body.note, request_id=request_id)
    )
