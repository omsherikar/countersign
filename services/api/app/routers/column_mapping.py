"""A college's saved column mapping (D42; API_CONTRACT §A4.16, scoping §A4.23).

GET: AICTE_ADMIN any institution, RO_OFFICER its region, INSTITUTION its own; PUT: the
institution itself or AICTE_ADMIN. Others 403; outside scope 404 "Institution not found.".
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import RequestId, SessionDep, require_roles, scoped_institution
from app.engine.upload import mapping as column_mapping
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter(prefix="/institutions", tags=["column mapping"])

Reader = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
Writer = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.INSTITUTION))]


class TemplateColumn(BaseModel):
    column: str
    required: bool


class MappingUser(BaseModel):
    id: str
    name: str


class ColumnMappingOut(BaseModel):
    institution_id: str
    mapping: dict[str, str]
    updated_at: str | None
    updated_by: MappingUser | None
    columns: list[TemplateColumn]


class ColumnMappingIn(BaseModel):
    # their header -> template column; the values are checked by the mapping rules
    mapping: dict[str, Any]
    headers: list[str] | None = Field(default=None, max_length=500)


@router.get("/{institution_id}/column-mapping", response_model=ColumnMappingOut)
async def get_column_mapping(
    institution_id: uuid.UUID, session: SessionDep, user: Reader
) -> ColumnMappingOut:
    institution = await scoped_institution(session, user, institution_id)
    return ColumnMappingOut(**await column_mapping.read(session, institution.id))


@router.put("/{institution_id}/column-mapping", response_model=ColumnMappingOut)
async def put_column_mapping(
    institution_id: uuid.UUID,
    body: ColumnMappingIn,
    session: SessionDep,
    user: Writer,
    request_id: RequestId,
) -> ColumnMappingOut:
    institution = await scoped_institution(session, user, institution_id)
    column_mapping.validate(body.mapping, body.headers)
    saved = await column_mapping.save(
        session, institution.id, body.mapping, user, request_id=request_id
    )
    return ColumnMappingOut(**saved)
