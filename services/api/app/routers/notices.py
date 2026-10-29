"""Student notices: the public page and reply, and resends (API_CONTRACT §A3.3 to §A3.5,
§A4.13).

`GET /notices/{token}` is public: the link token opens the page, and the `cs_access` and
`cs_dl_claim` cookies are read only to say who is looking. `POST /notices/{token}/respond`
records an answer only for the record's own student, signed in through DigiLocker (D37).
A malformed or unknown token gets the same 404. A resend commits its QUEUED rows before
delivery starts, on the worker or, with UPLOAD_INLINE, after the response in this process.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy import select

from app.auth import digilocker
from app.core.config import get_settings
from app.core.deps import Adapters, SessionDep, require_roles, scope_institutions
from app.core.errors import not_found
from app.core.ratelimit import limiter
from app.core.security import COOKIE_NAME
from app.models.enums import NoticeResponse, UserRole
from app.models.institution import Institution
from app.models.student import Enrolment
from app.models.user import User
from app.notices import dispatch, service
from app.routers.institutions import user_key
from app.schemas.notices import (
    EnrolmentNotice,
    NoticePublic,
    NoticeResendResult,
    NoticeRespondRequest,
    ResendState,
)

log = logging.getLogger("countersign.notices")

router = APIRouter(tags=["notices"])

# The limiter keys limits by URL unless a scope is shared, and every token is its own URL,
# so the notice routes share one scope: 30 a minute per client address over all tokens.
NOTICE_LIMIT = "30/minute"  # per client address (D32)
NOTICE_SCOPE = "notices"
RESEND_LIMIT = "30/minute"  # per signed-in user, over all enrolments
RESEND_SCOPE = "notices-resend"

ResendUser = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]


async def _viewer(request: Request, session) -> User | None:
    user = await digilocker.session_user(session, request.cookies.get(COOKIE_NAME))
    if user is not None:
        request.state.user_id = user.id
    return user


@router.get("/notices/{token}", response_model=NoticePublic)
@limiter.shared_limit(NOTICE_LIMIT, scope=NOTICE_SCOPE)
async def get_notice(request: Request, token: str, session: SessionDep) -> NoticePublic:
    body = await service.open_notice(
        session,
        token,
        user=await _viewer(request, session),
        pending=digilocker.read_claim(request.cookies.get(digilocker.CLAIM_COOKIE)),
    )
    return NoticePublic.model_validate(body)


@router.post("/notices/{token}/respond", response_model=NoticePublic)
@limiter.shared_limit(NOTICE_LIMIT, scope=NOTICE_SCOPE)
async def respond_to_notice(
    request: Request, token: str, body: NoticeRespondRequest, session: SessionDep
) -> NoticePublic:
    answer = await service.respond(
        session,
        token,
        NoticeResponse(body.response),
        body.comment,
        user=await _viewer(request, session),
    )
    return NoticePublic.model_validate(answer)


async def _scoped_enrolment(session, user: User, enrolment_id: uuid.UUID) -> Enrolment:
    stmt = (
        select(Enrolment)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .where(Enrolment.id == enrolment_id)
    )
    enrolment = (await session.execute(scope_institutions(stmt, user))).scalar_one_or_none()
    if enrolment is None:
        raise not_found("Enrolment")
    return enrolment


def _enqueue(notification_ids: list[uuid.UUID]) -> None:
    from app.worker import enqueue_delivery

    enqueue_delivery(notification_ids)


@router.post(
    "/enrolments/{enrolment_id}/notices/resend",
    response_model=NoticeResendResult,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.shared_limit(RESEND_LIMIT, scope=RESEND_SCOPE, key_func=user_key)
async def resend_notice(
    request: Request,
    enrolment_id: uuid.UUID,
    session: SessionDep,
    user: ResendUser,
    adapters: Adapters,
    background: BackgroundTasks,
) -> NoticeResendResult:
    enrolment = await _scoped_enrolment(session, user, enrolment_id)
    created = await service.resend(session, enrolment, user)
    now = datetime.now(UTC)
    result = NoticeResendResult(
        enrolment_id=str(enrolment.id),
        notices=[EnrolmentNotice.model_validate(service.enrolment_notice(n, now)) for n in created],
        resend=ResendState.model_validate(await service.resend_state(session, enrolment, user)),
    )
    await session.commit()
    ids = [n.id for n in created]
    if get_settings().upload_inline:
        background.add_task(dispatch.deliver_notices, ids, adapters=adapters)
    else:
        _enqueue(ids)
    return result
