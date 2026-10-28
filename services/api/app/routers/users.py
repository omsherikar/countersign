"""GET /users: the officers a flag can be assigned to (API_CONTRACT §A3.14).

AICTE_ADMIN sees every officer; RO_OFFICER sees AICTE officers and its own region's
officers. Active users only, AICTE first, then by name. Never an email address.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.cases import service as cases
from app.core.deps import SessionDep, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.flags import OfficerRow

router = APIRouter(prefix="/users", tags=["users"])

Officer = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
Paging = Annotated[PageParams, Depends(page_params)]
PICKABLE = (UserRole.AICTE_ADMIN, UserRole.RO_OFFICER)


def parse_roles(raw: str) -> list[UserRole]:
    out: list[UserRole] = []
    for token in (t.strip().upper() for t in raw.split(",")):
        role = next((r for r in PICKABLE if r.value == token), None)
        if role is None:
            message = "Role must be RO_OFFICER, AICTE_ADMIN or both, comma-separated"
            raise cases.invalid("role", message)
        if role not in out:
            out.append(role)
    return out


@router.get("", response_model=Page[OfficerRow])
async def list_officers(
    session: SessionDep,
    user: Officer,
    paging: Paging,
    role: Annotated[str, Query(max_length=40)],
    flag_id: uuid.UUID | None = None,
) -> Page[OfficerRow]:
    roles = parse_roles(role)
    flag = await cases.scoped_flag(session, user, flag_id) if flag_id else None
    stmt = await cases.assignable_officers(session, user, roles=roles, flag=flag)
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    return Page(
        items=[
            OfficerRow(id=str(officer_id), name=name, role=officer_role.value, region=region)
            for officer_id, name, officer_role, region in rows
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
