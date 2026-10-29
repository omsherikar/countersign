"""Certificate integration for awarding bodies (API_CONTRACT A3.21, §A4.15, D44).

Countersign does not issue degrees: a university lists the graduates of its affiliates,
issues a completion attestation, and gets the masked APAAR and a QR for its own
certificate, as print data or as a certificate block PDF. AICTE_ADMIN sees every graduate.
The `/university/degrees/*` routes are gone.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response

from app.core.deps import SessionDep, require_roles
from app.credentials import degree, issuer
from app.credentials.degree import GraduateQuery
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.university import CertificatePrint, GraduateRow

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
    attestation: Literal["issued", "not_issued"] | None = None,
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
            attestation=attestation,
            university_id=university_id if user.role is UserRole.AICTE_ADMIN else None,
        ),
    )


@router.post("/certificates/{enrolment_id}/issue", response_model=CertificatePrint, status_code=201)
async def issue_completion(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser, response: Response
) -> dict:
    """201 with the print data when an attestation is made; 200 when one is already live."""
    record = await degree.scoped_graduate(session, user, enrolment_id)
    _credential, created = await issuer.issue_degree(session, enrolment_id, actor_id=user.id)
    if not created:
        response.status_code = 200
    return await degree.print_body(session, record)


@router.get("/certificates/{enrolment_id}", response_model=CertificatePrint)
async def certificate_print_data(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser
) -> dict:
    return await degree.print_data(session, user, enrolment_id)


@router.get("/certificates/{enrolment_id}/block.pdf")
async def certificate_block(
    enrolment_id: uuid.UUID, session: SessionDep, user: UniversityUser
) -> Response:
    record = await degree.scoped_graduate(session, user, enrolment_id)
    credential = degree.active_degree_or_conflict(await degree.degree_for(session, enrolment_id))
    data = await degree.print_body(session, record)
    await degree.audit_print(session, user, record)
    return Response(
        content=degree.block_pdf(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="certificate-block-{credential.short_id}.pdf"'
            )
        },
    )
