"""POST /auth/login, POST /auth/logout, GET /me (API_CONTRACT A.2 to A.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core import audit
from app.core.deps import CurrentUser, RequestId, SessionDep
from app.core.errors import ApiError
from app.core.ratelimit import LOGIN_LIMIT, limiter
from app.core.security import (
    COOKIE_NAME,
    clear_auth_cookie,
    create_access_token,
    decode_access_token,
    set_auth_cookie,
    verify_password,
)
from app.models.enums import AuditAction
from app.models.institution import Institution
from app.models.user import User
from app.schemas.auth import LoginRequest, UserEnvelope, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=UserEnvelope)
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: SessionDep,
    request_id: RequestId,
) -> UserEnvelope:
    stmt = (
        select(User)
        .where(User.email == body.email)
        .options(selectinload(User.institution).selectinload(Institution.region))
    )
    user = (await session.execute(stmt)).unique().scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    user.last_login_at = datetime.now(UTC)
    await audit.record(session, user.id, AuditAction.LOGIN, "user", user.id, request_id=request_id)
    set_auth_cookie(response, create_access_token(user.id, user.role.value))
    return UserEnvelope(user=UserOut.from_user(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep, request_id: RequestId) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    token = request.cookies.get(COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    if claims and claims.get("sub"):
        try:
            user = await session.get(User, uuid.UUID(str(claims["sub"])))
        except ValueError:
            user = None
        if user is not None:
            await audit.record(
                session, user.id, AuditAction.LOGOUT, "user", user.id, request_id=request_id
            )
    clear_auth_cookie(response)
    return response


@router.get("/me", response_model=UserEnvelope)
async def me(user: CurrentUser) -> UserEnvelope:
    return UserEnvelope(user=UserOut.from_user(user))
