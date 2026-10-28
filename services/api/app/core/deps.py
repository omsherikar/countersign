"""Request dependencies: session, current user, role gate, scope helpers."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.adapters.base import AdapterSet
from app.adapters.factory import build_adapters
from app.core.errors import forbidden, not_found, unauthenticated
from app.core.security import COOKIE_NAME, decode_access_token
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise unauthenticated()
    claims = decode_access_token(token)
    if not claims or "sub" not in claims:
        raise unauthenticated()
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        raise unauthenticated() from None
    user = await session.get(
        User,
        user_id,
        options=[joinedload(User.institution).joinedload(Institution.region)],
    )
    if user is None or not user.is_active:
        raise unauthenticated()
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    required = [r.value for r in roles]

    async def _dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise forbidden(required)
        return user

    return _dep


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


RequestId = Annotated[str | None, Depends(request_id)]


def scope_institutions(stmt: Select, user: User) -> Select:
    """Restrict a SELECT over `institutions` to what the user may see (ARCHITECTURE §4)."""
    if user.role is UserRole.AICTE_ADMIN:
        return stmt
    if user.role is UserRole.RO_OFFICER:
        return stmt.where(Institution.region_id == user.region_id)
    if user.role is UserRole.INSTITUTION:
        return stmt.where(Institution.id == user.institution_id)
    if user.role is UserRole.UNIVERSITY:
        return stmt.where(Institution.university_id == user.university_id)
    # STUDENT and anything else: nothing
    return stmt.where(Institution.id.is_(None))


async def scoped_institution(
    session: AsyncSession, user: User, institution_id: uuid.UUID
) -> Institution:
    """The institution, or 404 when it does not exist or sits outside the user's scope."""
    stmt = scope_institutions(select(Institution).where(Institution.id == institution_id), user)
    institution = (await session.execute(stmt)).scalar_one_or_none()
    if institution is None:
        raise not_found("Institution")
    return institution


def get_adapters(request: Request) -> AdapterSet:
    adapters = getattr(request.app.state, "adapters", None)
    if adapters is None:
        adapters = build_adapters()
        request.app.state.adapters = adapters
    return adapters


Adapters = Annotated[AdapterSet, Depends(get_adapters)]
