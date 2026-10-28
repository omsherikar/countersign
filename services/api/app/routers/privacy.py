"""Privacy notice, the student's consents and data rights, and the data request queue
(D30, API_CONTRACT §A3.22).

GET /privacy/notice is public. Everything under /students/me is the signed-in student's
own record only; /data-requests is AICTE_ADMIN's queue of correction and erasure requests.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.deps import SessionDep, require_roles
from app.core.errors import not_found
from app.core.ratelimit import PUBLIC_LIMIT, limiter
from app.models.enums import DataRequestKind, DataRequestStatus, UserRole
from app.models.user import User
from app.privacy import notice
from app.privacy import service as privacy
from app.routers.institutions import user_key
from app.schemas.common import Page, PageParams, page_params
from app.schemas.privacy import (
    AccessLogRow,
    ConsentsView,
    ConsentWithdrawResult,
    DataRequestAdminRow,
    DataRequestCreate,
    DataRequestResolve,
    DataRequestRow,
    PrivacyNoticeOut,
)

router = APIRouter(tags=["privacy"])

StudentUser = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
Paging = Annotated[PageParams, Depends(page_params)]
DATA_REQUEST_LIMIT = "10/minute"


def _student_id(user: User) -> uuid.UUID:
    if user.student_id is None:
        raise not_found("Student")
    return user.student_id


@router.get("/privacy/notice", response_model=PrivacyNoticeOut)
@limiter.limit(PUBLIC_LIMIT)
async def privacy_notice(request: Request) -> PrivacyNoticeOut:
    return PrivacyNoticeOut(**notice.public_notice())


@router.get("/students/me/consents", response_model=ConsentsView)
async def my_consents(session: SessionDep, user: StudentUser) -> ConsentsView:
    return ConsentsView(**await privacy.consents_view(session, _student_id(user)))


@router.post("/students/me/consents/{purpose}/withdraw", response_model=ConsentWithdrawResult)
async def withdraw_consent(
    purpose: str, session: SessionDep, user: StudentUser
) -> ConsentWithdrawResult:
    student_id = _student_id(user)
    chosen = privacy.parse_purpose(purpose)
    return ConsentWithdrawResult(**await privacy.withdraw(session, student_id, chosen, user))


@router.get("/students/me/access-log", response_model=Page[AccessLogRow])
async def my_access_log(session: SessionDep, user: StudentUser, paging: Paging) -> Page:
    page = await privacy.access_log(session, _student_id(user), own_user_id=user.id, page=paging)
    return Page[AccessLogRow](**page)


@router.get("/students/me/data-requests", response_model=Page[DataRequestRow])
async def my_data_requests(session: SessionDep, user: StudentUser, paging: Paging) -> Page:
    page = await privacy.student_requests(session, _student_id(user), paging)
    return Page[DataRequestRow](**page)


@router.post("/students/me/data-requests", status_code=201, response_model=DataRequestRow)
@limiter.limit(DATA_REQUEST_LIMIT, key_func=user_key)
async def new_data_request(
    request: Request, body: DataRequestCreate, session: SessionDep, user: StudentUser
) -> DataRequestRow:
    student_id = _student_id(user)
    return DataRequestRow(**await privacy.create_request(session, student_id, user, body))


@router.get("/students/me/export.json")
async def my_export(session: SessionDep, user: StudentUser) -> Response:
    body = await privacy.export(session, _student_id(user), user)
    return JSONResponse(
        content=body,
        headers={
            "Content-Disposition": 'attachment; filename="countersign-my-data.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/data-requests", response_model=Page[DataRequestAdminRow])
async def data_requests(
    session: SessionDep,
    user: AdminUser,
    paging: Paging,
    status: DataRequestStatus | None = None,
    kind: DataRequestKind | None = None,
) -> Page:
    query = privacy.DataRequestQuery(page=paging, status=status, kind=kind)
    return Page[DataRequestAdminRow](**await privacy.admin_requests(session, user, query))


@router.post("/data-requests/{request_id}/resolve", response_model=DataRequestAdminRow)
async def resolve_data_request(
    request_id: uuid.UUID, body: DataRequestResolve, session: SessionDep, user: AdminUser
) -> DataRequestAdminRow:
    return DataRequestAdminRow(**await privacy.resolve(session, request_id, user, body))
