"""Degree print for universities (API_CONTRACT A3.21): graduates of the university's
affiliates, Degree proof issue, print data and the sample A4 insert. AICTE_ADMIN sees
every graduate."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import SessionDep, require_roles
from app.credentials import degree, issuer
from app.credentials.degree import GraduateQuery
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.university import DegreePrint, GraduateRow

router = APIRouter(prefix="/university", tags=["university"])

UniversityUser = Annotated[User, Depends(require_roles(UserRole.UNIVERSITY, UserRole.AICTE_ADMIN))]


@router.get("/graduates", response_model=Page[GraduateRow])
async def list_graduates(
    session: SessionDep,
    user: UniversityUser,
    page: Annotated[PageParams, Depends(page_params)],
    q: str | None = None,
    institution_id: uuid.UUID | None = None,
    academic_year: str | None = None,
    degree_state: Annotated[Literal["issued", "not_issued"] | None, Query(alias="degree")] = None,
    university_id: uuid.UUID | None = None,
) -> Page:
    return await degree.graduates(
        session,
        user,
        GraduateQuery(
            page=page,
            q=q,
            institution_id=institution_id,
            academic_year=academic_year,
            degree=degree_state,
            university_id=university_id if user.role is UserRole.AICTE_ADMIN else None,
        ),
    )


@router.post("/degrees/{enrolment_id}/issue", response_model=DegreePrint, status_code=201)
async def issue_degree(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser, response: Response
) -> dict:
    """201 with the print data when a proof is made; 200 when an active one already exists."""
    record = await degree.scoped_graduate(session, user, enrolment_id)
    _credential, created = await issuer.issue_degree(session, enrolment_id, actor_id=user.id)
    if not created:
        response.status_code = 200
    return await degree.print_body(session, record)


@router.get("/degrees/{enrolment_id}", response_model=DegreePrint)
async def degree_print_data(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser
) -> dict:
    return await degree.print_data(session, user, enrolment_id)


@router.get("/degrees/{enrolment_id}/insert.pdf")
async def degree_insert(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser
) -> Response:
    record = await degree.scoped_graduate(session, user, enrolment_id)
    credential = degree.active_degree_or_conflict(await degree.degree_for(session, enrolment_id))
    data = await degree.print_body(session, record)
    await degree.audit_print(session, user, record)
    return Response(
        content=degree.insert_pdf(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="degree-insert-{credential.short_id}.pdf"'
        },
    )
