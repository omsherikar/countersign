"""The wallet: GET /credentials, GET /credentials/{id}, shares and revocation
(API_CONTRACT A3.16 to A3.18). A student sees only their own proofs; AICTE_ADMIN sees any
and is the only one who revokes; only the holder shares."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from app.core import audit
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError
from app.core.ratelimit import limiter
from app.credentials import holder, issuer
from app.credentials.holder import CredentialFilters
from app.models.credential import Credential
from app.models.enums import CredentialKind, UserRole
from app.models.user import User
from app.routers.institutions import user_key
from app.schemas.common import Page, PageParams, page_params
from app.schemas.credentials import (
    CredentialCard,
    CredentialDetail,
    PresentationCreated,
    PresentationRow,
    PresentRequest,
    RevokeRequest,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])

WalletUser = Annotated[User, Depends(require_roles(UserRole.STUDENT, UserRole.AICTE_ADMIN))]
HolderUser = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
Paging = Annotated[PageParams, Depends(page_params)]
PRESENT_LIMIT = "10/minute"


async def _credential(session: SessionDep, user: User, credential_id: uuid.UUID) -> Credential:
    """The credential, or 404 when it does not exist or is another student's."""
    credential = await session.get(Credential, credential_id)
    if credential is None or (
        user.role is UserRole.STUDENT and credential.student_id != user.student_id
    ):
        raise ApiError(404, "NOT_FOUND", "Attestation not found.")
    return credential


@router.get("", response_model=Page[CredentialCard])
async def list_credentials(
    session: SessionDep,
    user: WalletUser,
    page: Paging,
    student_id: uuid.UUID | None = None,
    enrolment_id: uuid.UUID | None = None,
    kind: CredentialKind | None = None,
    status: Literal["ACTIVE", "REVOKED", "EXPIRED"] | None = None,
) -> Page:
    filters = (
        CredentialFilters(
            student_id=student_id, enrolment_id=enrolment_id, kind=kind, status=status
        )
        if user.role is UserRole.AICTE_ADMIN
        else CredentialFilters()
    )
    return await holder.cards(session, user, filters=filters, page=page)


@router.get("/{credential_id}", response_model=CredentialDetail)
async def get_credential(
    credential_id: uuid.UUID, session: SessionDep, user: WalletUser, request_id: RequestId
) -> dict:
    credential = await _credential(session, user, credential_id)
    body = await holder.detail(session, credential)
    await audit.record_read(session, user.id, "credential", [credential.id], request_id=request_id)
    return body


@router.post("/{credential_id}/present", response_model=PresentationCreated, status_code=201)
@limiter.limit(PRESENT_LIMIT, key_func=user_key)
async def present_credential(
    request: Request,
    credential_id: uuid.UUID,
    body: PresentRequest,
    session: SessionDep,
    user: HolderUser,
) -> dict:
    credential = await _credential(session, user, credential_id)
    return await holder.present(session, credential, user, fields=body.fields, consent=body.consent)


@router.get("/{credential_id}/presentations", response_model=Page[PresentationRow])
async def list_presentations(
    credential_id: uuid.UUID, session: SessionDep, user: WalletUser, page: Paging
) -> Page:
    credential = await _credential(session, user, credential_id)
    return await holder.presentations(session, credential, page)


@router.post("/{credential_id}/revoke", response_model=CredentialCard)
async def revoke_credential(
    credential_id: uuid.UUID, body: RevokeRequest, session: SessionDep, user: AdminUser
) -> dict:
    credential = await _credential(session, user, credential_id)
    await issuer.revoke(session, credential, reason=body.reason, actor_id=user.id)
    return await holder.card(session, credential)
