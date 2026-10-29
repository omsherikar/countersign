"""GET and POST /approvals/{id}/versions (API_CONTRACT §A4.17, D41)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.approvals import service
from app.core.deps import SessionDep, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.approvals import ApprovalVersionCreate, ApprovalVersionCreated, ApprovalVersions

router = APIRouter(prefix="/approvals", tags=["approvals"])

ReadUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION, UserRole.UNIVERSITY
        )
    ),
]
AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]


@router.get("/{approval_id}/versions", response_model=ApprovalVersions)
async def approval_versions(
    approval_id: uuid.UUID, session: SessionDep, user: ReadUser
) -> ApprovalVersions:
    return ApprovalVersions.model_validate(await service.versions(session, user, approval_id))


@router.post("/{approval_id}/versions", response_model=ApprovalVersionCreated, status_code=201)
async def add_approval_version(
    approval_id: uuid.UUID, body: ApprovalVersionCreate, session: SessionDep, user: AdminUser
) -> ApprovalVersionCreated:
    """A new version of the approval; the ledger, the Seat rows, the seat cases and the
    record statuses follow it in the same transaction."""
    return ApprovalVersionCreated.model_validate(
        await service.add_version(
            session,
            user,
            approval_id,
            approved_intake=body.approved_intake,
            effective_from=body.effective_from,
            source=body.source,
        )
    )
