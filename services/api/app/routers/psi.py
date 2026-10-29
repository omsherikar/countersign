"""POST /psi/compute: how many linked students Countersign and a partner regulator both hold,
learned by private set intersection (D48, API_CONTRACT §A4.26). AICTE_ADMIN only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import RequestId, SessionDep, require_roles
from app.core.ratelimit import limiter
from app.models.enums import UserRole
from app.models.user import User
from app.psi import service
from app.routers.institutions import user_key
from app.schemas.psi import PsiResult

router = APIRouter(prefix="/psi", tags=["psi"])

AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
# one run takes about ten seconds of CPU on both sides
COMPUTE_LIMIT = "4/minute"


@router.post("/compute", response_model=PsiResult)
@limiter.limit(COMPUTE_LIMIT, key_func=user_key)
async def compute(
    request: Request, session: SessionDep, user: AdminUser, request_id: RequestId
) -> PsiResult:
    return PsiResult(**await service.compute(session, actor_id=user.id, request_id=request_id))
