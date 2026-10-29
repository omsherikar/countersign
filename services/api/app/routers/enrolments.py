"""GET /enrolments/{id} (the record card), GET /enrolments/{id}/history and
POST /enrolments/{id}/recheck (API_CONTRACT A2.11, A2.12, §A3.7, §A4.6, §A4.7)."""

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
from app.engine import status, versions
from app.engine.checks import RECHECKABLE, recheck_pending
from app.engine.contracts import RECHECK_ROW_STATES
from app.models.enums import (
    CheckType,
    ConsentStatus,
    EnrolmentStatus,
    SeatEventKind,
    UserRole,
)
from app.models.geo import Region, State
from app.models.institution import Approval, ApprovalVersion, Institution, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import Check
from app.notices.service import notices_for_enrolment, resend_state
from app.routers._enrolment_rows import (
    brief,
    eligibility_of,
    flags_for,
    full_rows,
    iso,
    ordered,
    record_fields,
    visible_summary,
)
from app.routers.institutions import user_key
from app.schemas.common import FlagSummary, InstitutionRef, PageParams, page_params
from app.schemas.enrolments import (
    ApprovalRef,
    CheckTransition,
    ClaimRef,
    EnrolmentDetail,
    EnrolmentHistory,
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
Paging = Annotated[PageParams, Depends(page_params)]
ENROLMENT_RECHECK_LIMIT = "30/minute"
CARD_VERSIONS = 20


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
    return ordered(
        (await session.execute(select(Check).where(Check.enrolment_id == enrolment_id)))
        .scalars()
        .all()
    )


async def _seat(session, enrolment: Enrolment) -> SeatRef | None:
    if enrolment.seat_id is None:
        return None
    held = (
        await session.execute(
            select(Seat, SeatPool.seat_type, Approval.academic_year)
            .join(SeatPool, SeatPool.id == Seat.pool_id)
            .join(Approval, Approval.id == SeatPool.approval_id)
            .where(Seat.id == enrolment.seat_id)
        )
    ).first()
    if held is None:
        return None
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
    return SeatRef(
        id=str(held_seat.id),
        seat_code=held_seat.seat_code,
        seat_type=seat_type.value,
        academic_year=seat_year,
        assigned_at=iso(assigned_at),
    )


async def _approval(session, enrolment: Enrolment) -> ApprovalRef | None:
    """The cohort approval the Seat row was checked against, at its current version."""
    row = (
        await session.execute(
            select(Approval, ApprovalVersion)
            .outerjoin(
                ApprovalVersion,
                (ApprovalVersion.approval_id == Approval.id)
                & (ApprovalVersion.version == Approval.current_version),
            )
            .where(
                Approval.programme_id == enrolment.programme_id,
                Approval.academic_year == enrolment.cohort_year,
            )
        )
    ).first()
    if row is None:
        return None
    approval, version = row
    return ApprovalRef(
        id=str(approval.id),
        academic_year=approval.academic_year,
        version=approval.current_version,
        approved_intake=approval.approved_intake,
        effective_from=iso(version.effective_from) if version else None,
        source=version.source if version else None,
    )


async def _claim(session, student: Student, checks: list[Check]) -> ClaimRef | None:
    """A record without a linked APAAR: whether the student claimed it through DigiLocker
    (D36). None for a linked APAAR or an international student."""
    if student.consent_status in (ConsentStatus.LINKED, ConsentStatus.INTERNATIONAL):
        return None
    user = (
        await session.execute(
            select(User).where(
                User.student_id == student.id,
                User.role == UserRole.STUDENT,
                User.digilocker_sub.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        return ClaimRef(claimed=False, claimed_at=None)
    identity = next((c for c in checks if c.type is CheckType.IDENTITY), None)
    claimed_at = (
        identity.observed_at
        if identity is not None and (identity.detail or {}).get("basis") == "DIGILOCKER_CLAIM"
        else user.updated_at
    )
    return ClaimRef(claimed=True, claimed_at=iso(claimed_at))


@router.get("/{enrolment_id}", response_model=EnrolmentDetail)
async def enrolment_detail(
    enrolment_id: uuid.UUID, session: SessionDep, user: ReadUser, request_id: RequestId
) -> EnrolmentDetail:
    enrolment, student, institution, state, region, programme = await _scoped(
        session, user, enrolment_id
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
    attestations = await holder.credential_refs(session, enrolment.id)
    card_versions = await versions.latest(session, enrolment.id, CARD_VERSIONS)
    history_count = await versions.count(session, enrolment.id)
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
        eligibility=eligibility_of(enrolment),
        status=enrolment.status.value,
        status_date=iso(enrolment.status_date) or "",
        admission_date=iso(enrolment.admission_date) or "",
        uploaded_at=iso(enrolment.uploaded_at) or "",
        upload=upload,
        seat=await _seat(session, enrolment),
        approval=await _approval(session, enrolment),
        claim=await _claim(session, student, checks),
        checks=await full_rows(session, enrolment.id),
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
        credentials=attestations,
        versions=card_versions,
        history_count=history_count,
        **record_fields(enrolment),
    )


@router.get("/{enrolment_id}/history", response_model=EnrolmentHistory)
async def enrolment_history(
    enrolment_id: uuid.UUID,
    session: SessionDep,
    user: ReadUser,
    request_id: RequestId,
    paging: Paging,
) -> EnrolmentHistory:
    """Every version of the record, newest first (API_CONTRACT §A4.7)."""
    enrolment, student, *_ = await _scoped(session, user, enrolment_id)
    page = await versions.history(session, enrolment.id, page=paging, user=user)
    await audit.record_read(session, user.id, "student", [student.id], request_id=request_id)
    return EnrolmentHistory.model_validate(page)


@router.post("/{enrolment_id}/recheck", response_model=EnrolmentRecheck)
@limiter.limit(ENROLMENT_RECHECK_LIMIT, key_func=user_key)
async def enrolment_recheck(
    request: Request,
    enrolment_id: uuid.UUID,
    session: SessionDep,
    user: RecheckUser,
    adapters: Adapters,
) -> EnrolmentRecheck:
    """Re-run this record's IDENTITY, SEAT, ADMISSION and STUDYING rows that are PENDING,
    NOT_YET_DUE or SOURCE_UNAVAILABLE, synchronously; then its status, then issuance."""
    enrolment, *_ = await _scoped(session, user, enrolment_id)
    before = {
        c.type: c.status
        for c in await _checks(session, enrolment.id)
        if c.status in RECHECK_ROW_STATES and c.type in RECHECKABLE
    }
    result = await recheck_pending(
        session,
        [enrolment.id],
        adapters,
        concurrency=get_settings().checks_concurrency,
        actor_id=user.id,
    )
    # the status follows the rows, then the attestation is asked for (API_CONTRACT §A4.6)
    await status.settle(session, issue=False)
    await credentials.issue_if_eligible(session, enrolment.id)
    after = await _checks(session, enrolment.id)
    await session.refresh(enrolment)
    return EnrolmentRecheck(
        enrolment_id=str(enrolment.id),
        rechecked=result.rechecked,
        results=[
            CheckTransition(type=c.type.value, before=before[c.type].value, after=c.status.value)
            for c in after
            if c.type in before
        ],
        flags_raised=result.flags.created,
        record_status=enrolment.record_status.value
        if enrolment.status is EnrolmentStatus.ACTIVE
        else None,
        checks=[brief(c) for c in after],
    )
