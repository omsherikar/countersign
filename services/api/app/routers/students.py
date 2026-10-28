"""GET /students/me (API_CONTRACT A.10). STUDENT only; the read is audited."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core import audit
from app.core.crypto import mask_apaar, mask_mobile
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import not_found
from app.models.enums import UserRole
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.user import User
from app.routers._enrolment_rows import countersigns
from app.schemas.students import StudentEnrolment, StudentMe

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentMe)
async def students_me(
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    request_id: RequestId,
) -> StudentMe:
    student = await session.get(Student, user.student_id) if user.student_id else None
    if student is None:
        raise not_found("Student")
    rows = (
        await session.execute(
            select(Enrolment, Institution, Programme)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .where(Enrolment.student_id == student.id)
            .order_by(Enrolment.academic_year.desc(), Institution.name)
        )
    ).all()
    signs = await countersigns(session, [enrolment.id for enrolment, _, _ in rows])
    await audit.record_read(session, user.id, "student", [student.id], request_id=request_id)
    return StudentMe(
        id=str(student.id),
        name=student.name,
        apaar_masked=mask_apaar(student.apaar_last4),
        consent_status=student.consent_status.value,
        provisional_id=student.provisional_id,
        dob=student.dob.isoformat(),
        email=student.email,
        mobile_masked=mask_mobile(student.mobile_last4),
        enrolments=[
            StudentEnrolment(
                id=str(enrolment.id),
                institution_id=str(institution.id),
                institution_name=institution.name,
                programme_code=programme.code,
                programme_name=programme.name,
                academic_year=enrolment.academic_year,
                year_of_study=enrolment.year_of_study,
                status=enrolment.status.value,
                countersign=signs[enrolment.id],
            )
            for enrolment, institution, programme in rows
        ],
    )
