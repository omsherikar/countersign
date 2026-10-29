"""The student's own page (API_CONTRACT A.10, §A3.6, §A4.5, §A4.13). STUDENT only, signed in
through DigiLocker; every read is audited."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core import audit
from app.core.crypto import mask_apaar, mask_mobile
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import not_found
from app.core.ratelimit import limiter
from app.credentials import holder
from app.engine import status
from app.models.enums import NoticeResponse, UserRole
from app.models.student import Student
from app.models.user import User
from app.notices import service
from app.notices.records import student_enrolments
from app.routers.institutions import user_key
from app.schemas.notices import NoticeRespondRequest
from app.schemas.students import StudentEnrolment, StudentMe

router = APIRouter(prefix="/students", tags=["students"])

StudentUser = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
RESPOND_LIMIT = "10/minute"  # per signed-in student


async def _student(session, user: User) -> Student:
    student = await session.get(Student, user.student_id) if user.student_id else None
    if student is None:
        raise not_found("Student")
    return student


@router.get("/me", response_model=StudentMe)
async def students_me(session: SessionDep, user: StudentUser, request_id: RequestId) -> StudentMe:
    student = await _student(session, user)
    enrolments = await student_enrolments(session, student)
    notices = await service.notices_for_student(session, student.id)
    wallet = await holder.wallet_summary(session, student.id)
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
        enrolments=[StudentEnrolment.model_validate(e) for e in enrolments],
        notices=notices,
        credentials=wallet,
    )


@router.post("/me/enrolments/{enrolment_id}/respond", response_model=StudentEnrolment)
@limiter.shared_limit(RESPOND_LIMIT, scope="students-respond", key_func=user_key)
async def respond_to_claim(
    request: Request,
    enrolment_id: uuid.UUID,
    body: NoticeRespondRequest,
    session: SessionDep,
    user: StudentUser,
) -> StudentEnrolment:
    """The student answers a claim on their own enrolments page, with or without a notice
    link (§A4.13); the answer is recorded as one given after DigiLocker sign-in."""
    student = await _student(session, user)
    await service.respond_as_student(
        session, user, enrolment_id, NoticeResponse(body.response), body.comment
    )
    await status.settle(session)
    [enrolment] = await student_enrolments(session, student, only=[enrolment_id])
    return StudentEnrolment.model_validate(enrolment)
