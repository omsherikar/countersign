"""GET /enrolments/{id} and POST /enrolments/{id}/recheck (API_CONTRACT A2.11, A2.12, §A3.7)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app import credentials
from app.core import audit
from app.core.config import get_settings
from app.core.crypto import mask_apaar, mask_mobile
from app.core.deps import Adapters, RequestId, SessionDep, require_roles, scope_institutions
from app.core.errors import not_found
from app.core.ratelimit import limiter
from app.credentials import holder
from app.engine.checks import RECHECKABLE, recheck_pending
from app.engine.contracts import CHECK_ORDER, RECHECK_STATES
from app.engine.score import countersign
from app.models.enums import SeatEventKind, UserRole
from app.models.geo import Region, State
from app.models.institution import Approval, Institution, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import Check
from app.notices.service import notices_for_enrolment, resend_state
from app.routers._enrolment_rows import flags_for, iso, visible_summary
from app.routers.institutions import user_key
from app.schemas.common import CheckOut, Countersign, FlagSummary, InstitutionRef
from app.schemas.enrolments import (
    CheckTransition,
    EnrolmentDetail,
    EnrolmentRecheck,
    ProgrammeDetailRef,
    SeatRef,
    StudentDetail,
    UploadRef,
)

router = APIRouter(prefix="/enrolments", tags=["enrolments"])

ReadUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION, UserRole.UNIVERSITY
        )
    ),
]
RecheckUser = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
ENROLMENT_RECHECK_LIMIT = "30/minute"
_ORDER = {t: i for i, t in enumerate(CHECK_ORDER)}


async def _scoped(session, user: User, enrolment_id: uuid.UUID):
    """(enrolment, student, institution, state, region, programme) or 404 out of scope."""
    stmt = (
        select(Enrolment, Student, Institution, State, Region, Programme)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .where(Enrolment.id == enrolment_id)
    )
    row = (await session.execute(scope_institutions(stmt, user))).first()
    if row is None:
        raise not_found("Enrolment")
    return row


async def _checks(session, enrolment_id: uuid.UUID) -> list[Check]:
    rows = (
        (await session.execute(select(Check).where(Check.enrolment_id == enrolment_id)))
        .scalars()
        .all()
    )
    return sorted(rows, key=lambda c: _ORDER[c.type])


@router.get("/{enrolment_id}", response_model=EnrolmentDetail)
async def enrolment_detail(
    enrolment_id: uuid.UUID, session: SessionDep, user: ReadUser, request_id: RequestId
) -> EnrolmentDetail:
    enrolment, student, institution, state, region, programme = await _scoped(
        session, user, enrolment_id
    )
    seat = None
    if enrolment.seat_id is not None:
        held = (
            await session.execute(
                select(Seat, SeatPool.seat_type, Approval.academic_year)
                .join(SeatPool, SeatPool.id == Seat.pool_id)
                .join(Approval, Approval.id == SeatPool.approval_id)
                .where(Seat.id == enrolment.seat_id)
            )
        ).first()
        if held is not None:
            held_seat, seat_type, seat_year = held
            assigned_at = (
                await session.execute(
                    select(func.max(SeatEvent.at)).where(
                        SeatEvent.seat_id == held_seat.id,
                        SeatEvent.enrolment_id == enrolment.id,
                        SeatEvent.kind == SeatEventKind.ASSIGN,
                    )
                )
            ).scalar_one_or_none()
            seat = SeatRef(
                id=str(held_seat.id),
                seat_code=held_seat.seat_code,
                seat_type=seat_type.value,
                academic_year=seat_year,
                assigned_at=iso(assigned_at),
            )
    upload = None
    if enrolment.upload_batch_id is not None:
        batch = await session.get(UploadBatch, enrolment.upload_batch_id)
        if batch is not None:
            upload = UploadRef(
                batch_id=str(batch.id), filename=batch.filename, row_no=enrolment.source_row_no
            )
    checks = await _checks(session, enrolment.id)
    flags = (
        await flags_for(session, {enrolment.id: enrolment.institution_id}, unresolved_only=False)
    ).get(enrolment.id, [])
    notices = await notices_for_enrolment(session, enrolment.id)
    resend = await resend_state(session, enrolment, user)
    proofs = await holder.credential_refs(session, enrolment.id)
    await audit.record_read(session, user.id, "student", [student.id], request_id=request_id)
    return EnrolmentDetail(
        id=str(enrolment.id),
        institution=InstitutionRef(
            id=str(institution.id),
            name=institution.name,
            aicte_permanent_id=institution.aicte_permanent_id,
            state_code=state.code,
            state_name=state.name,
            region=region.code,
        ),
        student=StudentDetail(
            id=str(student.id),
            name=student.name,
            apaar_masked=mask_apaar(student.apaar_last4),
            consent_status=student.consent_status.value,
            provisional_id=student.provisional_id,
            nationality=student.nationality,
            dob=student.dob.isoformat(),
            gender=student.gender.value,
            mobile_masked=mask_mobile(student.mobile_last4),
        ),
        programme=ProgrammeDetailRef(
            id=str(programme.id),
            code=programme.code,
            name=programme.name,
            level=programme.level.value,
            mode=programme.mode.value,
            duration_years=programme.duration_years,
        ),
        academic_year=enrolment.academic_year,
        cohort_year=enrolment.cohort_year,
        year_of_study=enrolment.year_of_study,
        admission_route=enrolment.admission_route.value,
        counselling_ref=enrolment.counselling_ref,
        category=enrolment.category.value,
        status=enrolment.status.value,
        status_date=iso(enrolment.status_date) or "",
        admission_date=iso(enrolment.admission_date) or "",
        uploaded_at=iso(enrolment.uploaded_at) or "",
        record_status=enrolment.record_status.value,
        status_reason=enrolment.status_reason,
        next_step=enrolment.next_step,
        record_status_at=iso(enrolment.record_status_at),
        upload=upload,
        seat=seat,
        countersign=Countersign.model_validate(countersign(checks)),
        checks=[
            CheckOut(
                type=c.type.value,
                status=c.status.value,
                source=c.source,
                checked_at=iso(c.checked_at),
                attempts=c.attempts,
                detail=c.detail,
                supplied_by=c.supplied_by,
                observed_at=iso(c.observed_at),
                independent=c.independent,
                resolved={k: c.resolved.get(k) for k in ("outcome", "at")} if c.resolved else None,
            )
            for c in checks
        ],
        flags=[
            FlagSummary(
                id=str(f.id),
                type=f.type.value,
                severity=f.severity.value,
                status=f.status.value,
                summary=visible_summary(user, f.evidence),
                created_at=iso(f.created_at) or "",
            )
            for f in flags
        ],
        notices=notices,
        resend=resend,
        credentials=proofs,
    )


@router.post("/{enrolment_id}/recheck", response_model=EnrolmentRecheck)
@limiter.limit(ENROLMENT_RECHECK_LIMIT, key_func=user_key)
async def enrolment_recheck(
    request: Request,
    enrolment_id: uuid.UUID,
    session: SessionDep,
    user: RecheckUser,
    adapters: Adapters,
) -> EnrolmentRecheck:
    """Re-run this enrolment's PENDING and SOURCE_UNAVAILABLE checks except STUDENT,
    synchronously."""
    enrolment, *_ = await _scoped(session, user, enrolment_id)
    before = {
        c.type: c.status
        for c in await _checks(session, enrolment.id)
        if c.status in RECHECK_STATES and c.type in RECHECKABLE
    }
    result = await recheck_pending(
        session,
        [enrolment.id],
        adapters,
        concurrency=get_settings().checks_concurrency,
        actor_id=user.id,
    )
    # a recheck can clear the last pending source after the student said Yes
    await credentials.issue_if_eligible(session, enrolment.id)
    after = await _checks(session, enrolment.id)
    return EnrolmentRecheck(
        enrolment_id=str(enrolment.id),
        rechecked=result.rechecked,
        results=[
            CheckTransition(type=c.type.value, before=before[c.type].value, after=c.status.value)
            for c in after
            if c.type in before
        ],
        flags_raised=result.flags.created,
        countersign=Countersign.model_validate(countersign(after)),
    )
