"""GET /institutions, /institutions/{id}, /{id}/seats, /{id}/enrolments (A.6 to A.9, addendum 1)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import aliased

from app.core import audit
from app.core.cohort import cohort_year_sql
from app.core.config import get_settings
from app.core.crypto import mask_apaar
from app.core.deps import RequestId, SessionDep, require_roles, scoped_institution
from app.engine.seatpools import INTERNATIONAL_RESERVED_LABEL
from app.models.enums import (
    AdmissionRoute,
    EnrolmentStatus,
    InstitutionType,
    SeatEventKind,
    SeatStatus,
    SeatType,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.user import User
from app.routers._stats import institution_stats_stmt, region_label
from app.schemas.common import Page, PageParams, page_params
from app.schemas.institutions import (
    ApprovalOut,
    EnrolmentRow,
    InstitutionDetail,
    InstitutionRow,
    ProgrammeDetail,
    SeatPoolOut,
    SeatRow,
    StudentRef,
)

router = APIRouter(prefix="/institutions", tags=["institutions"])

INSTITUTION_ROLES = (
    UserRole.AICTE_ADMIN,
    UserRole.RO_OFFICER,
    UserRole.INSTITUTION,
    UserRole.UNIVERSITY,
)
InstitutionUser = Annotated[User, Depends(require_roles(*INSTITUTION_ROLES))]
Paging = Annotated[PageParams, Depends(page_params)]

ListSort = Literal[
    "enrolments_desc",
    "name_asc",
    "flags_open_desc",
    "name",
    "enrolments",
    "approved_seats",
]
EnrolmentSort = Literal["name_asc", "year_desc", "route_asc"]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


async def _count(session, stmt: Select) -> int:
    return (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()


# ---------------------------------------------------------------------------- list


@router.get("", response_model=Page[InstitutionRow])
async def list_institutions(
    session: SessionDep,
    user: InstitutionUser,
    paging: Paging,
    state: Annotated[str | None, Query(max_length=2)] = None,
    region: Annotated[str | None, Query(max_length=20)] = None,
    type: InstitutionType | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    sort: ListSort = "enrolments_desc",
    order: Literal["asc", "desc"] | None = None,
) -> Page[InstitutionRow]:
    year = get_settings().academic_year
    stmt = institution_stats_stmt(user, year)
    if state:
        stmt = stmt.where(State.code == state.upper())
    if region and user.role is not UserRole.RO_OFFICER:
        stmt = stmt.where(Region.code == region.upper())
    if type:
        stmt = stmt.where(Institution.type == type)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Institution.name.ilike(needle), Institution.aicte_permanent_id.ilike(needle))
        )

    enrolments_col = stmt.selected_columns["enrolments"]
    seats_col = stmt.selected_columns["approved_seats"]
    if sort in ("enrolments_desc", "flags_open_desc", "enrolments"):
        key, default_order = enrolments_col, "desc"
    elif sort == "approved_seats":
        key, default_order = seats_col, "desc"
    else:
        key, default_order = func.lower(Institution.name), "asc"
    direction = order or default_order
    ordered = key.desc() if direction == "desc" else key.asc()
    stmt = stmt.order_by(ordered, Institution.name.asc(), Institution.id.asc())

    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    items = [
        InstitutionRow(
            id=str(inst.id),
            aicte_permanent_id=inst.aicte_permanent_id,
            name=inst.name,
            type=inst.type.value,
            state_code=st.code,
            state_name=st.name,
            region=rg.code,
            region_name=region_label(rg),
            university_id=str(uni.id) if uni else None,
            university_name=uni.name if uni else None,
            programmes=programmes,
            approved_seats=approved_seats,
            enrolments=enrolments,
        )
        for inst, st, rg, uni, programmes, approved_seats, enrolments in rows
    ]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


# -------------------------------------------------------------------------- detail


@router.get("/{institution_id}", response_model=InstitutionDetail)
async def institution_detail(
    institution_id: uuid.UUID,
    session: SessionDep,
    user: InstitutionUser,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> InstitutionDetail:
    year = academic_year or get_settings().academic_year
    institution = await scoped_institution(session, user, institution_id)
    state = await session.get(State, institution.state_id)
    region = await session.get(Region, institution.region_id)
    university = None
    if institution.university_id is not None:
        university = await session.get(University, institution.university_id)

    prog_stmt = (
        select(Programme, Approval)
        .join(Approval, Approval.programme_id == Programme.id)
        .where(Programme.institution_id == institution.id, Approval.academic_year == year)
        .order_by(Programme.code, Programme.shift)
    )
    prog_rows = (await session.execute(prog_stmt)).all()
    approval_ids = [a.id for _, a in prog_rows]

    pools_by_approval: dict[uuid.UUID, list[SeatPool]] = defaultdict(list)
    seat_counts: dict[uuid.UUID, dict[SeatStatus, int]] = defaultdict(dict)
    if approval_ids:
        pools = (
            (await session.execute(select(SeatPool).where(SeatPool.approval_id.in_(approval_ids))))
            .scalars()
            .all()
        )
        for pool in pools:
            pools_by_approval[pool.approval_id].append(pool)
        pool_ids = [p.id for p in pools]
        if pool_ids:
            counts = (
                await session.execute(
                    select(Seat.pool_id, Seat.status, func.count())
                    .where(Seat.pool_id.in_(pool_ids))
                    .group_by(Seat.pool_id, Seat.status)
                )
            ).all()
            for pool_id, status_value, n in counts:
                seat_counts[pool_id][status_value] = n

    # "Admitted" against an approval is the approval's cohort in the current roll: rows
    # from the current academic year whose year of study puts them in that intake.
    enrol_counts = (
        await session.execute(
            select(
                Enrolment.programme_id,
                func.count(),
                func.count().filter(Enrolment.seat_id.is_(None)),
            )
            .where(
                Enrolment.institution_id == institution.id,
                Enrolment.academic_year == get_settings().academic_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
                cohort_year_sql(Enrolment.academic_year, Enrolment.year_of_study) == year,
            )
            .group_by(Enrolment.programme_id)
        )
    ).all()
    enrolled = {pid: (total, unseated) for pid, total, unseated in enrol_counts}

    order = {t: i for i, t in enumerate(SeatType)}
    programmes: list[ProgrammeDetail] = []
    for programme, approval in prog_rows:
        total, unseated = enrolled.get(programme.id, (0, 0))
        pools_out = []
        for pool in sorted(pools_by_approval[approval.id], key=lambda p: order[p.seat_type]):
            assigned = seat_counts[pool.id].get(SeatStatus.ASSIGNED, 0)
            free = seat_counts[pool.id].get(SeatStatus.FREE, 0)
            pools_out.append(
                SeatPoolOut(
                    seat_type=pool.seat_type.value,
                    capacity=pool.capacity,
                    is_supernumerary=pool.is_supernumerary,
                    assigned=assigned,
                    free=free,
                    reserved_for=(
                        INTERNATIONAL_RESERVED_LABEL
                        if pool.seat_type is SeatType.INTERNATIONAL
                        else None
                    ),
                    rule_source=pool.rule_source,
                )
            )
        programmes.append(
            ProgrammeDetail(
                id=str(programme.id),
                code=programme.code,
                name=programme.name,
                level=programme.level.value,
                discipline=programme.discipline.value,
                shift=programme.shift.value,
                approval=ApprovalOut(
                    academic_year=approval.academic_year,
                    approved_intake=approval.approved_intake,
                    cutoff_date=approval.cutoff_date.isoformat() if approval.cutoff_date else None,
                ),
                enrolments=total,
                pools=pools_out,
                unseated=unseated,
            )
        )

    enrolments_total = (
        await session.execute(
            select(func.count()).where(
                Enrolment.institution_id == institution.id,
                Enrolment.academic_year == get_settings().academic_year,
                Enrolment.status == EnrolmentStatus.ACTIVE,
            )
        )
    ).scalar_one()

    return InstitutionDetail(
        id=str(institution.id),
        aicte_permanent_id=institution.aicte_permanent_id,
        name=institution.name,
        type=institution.type.value,
        state_code=state.code,
        state_name=state.name,
        region=region.code,
        region_name=region_label(region),
        university_id=str(university.id) if university else None,
        university_name=university.name if university else None,
        address_city=institution.address_city,
        established_year=institution.established_year,
        approved_seats=sum(a.approved_intake for _, a in prog_rows),
        enrolments=enrolments_total,
        programmes=programmes,
    )


# --------------------------------------------------------------------------- seats


@router.get("/{institution_id}/seats", response_model=Page[SeatRow])
async def institution_seats(
    institution_id: uuid.UUID,
    session: SessionDep,
    user: InstitutionUser,
    paging: Paging,
    request_id: RequestId,
    programme_id: uuid.UUID | None = None,
    seat_type: SeatType | None = None,
    status: SeatStatus | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> Page[SeatRow]:
    year = academic_year or get_settings().academic_year
    institution = await scoped_institution(session, user, institution_id)
    holder = aliased(Enrolment)
    holder_student = aliased(Student)
    assigned_at = (
        select(func.max(SeatEvent.at))
        .where(SeatEvent.seat_id == Seat.id, SeatEvent.kind == SeatEventKind.ASSIGN)
        .scalar_subquery()
    )
    # Each approval year has its own pools, and seat codes repeat across years.
    stmt = (
        select(
            Seat,
            SeatPool,
            Programme.code,
            Approval.academic_year,
            holder_student,
            assigned_at.label("assigned_at"),
        )
        .join(SeatPool, SeatPool.id == Seat.pool_id)
        .join(Approval, Approval.id == SeatPool.approval_id)
        .join(Programme, Programme.id == Approval.programme_id)
        .outerjoin(holder, holder.id == Seat.enrolment_id)
        .outerjoin(holder_student, holder_student.id == holder.student_id)
        .where(Programme.institution_id == institution.id, Approval.academic_year == year)
    )
    if programme_id:
        stmt = stmt.where(Programme.id == programme_id)
    if seat_type:
        stmt = stmt.where(SeatPool.seat_type == seat_type)
    if status:
        stmt = stmt.where(Seat.status == status)
    if q:
        needle = q.strip()
        stmt = stmt.where(
            or_(Seat.seat_code.ilike(f"{needle}%"), holder_student.name.ilike(f"%{needle}%"))
        )
    stmt = stmt.order_by(Seat.seat_code, Seat.id)
    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()

    items = [
        SeatRow(
            id=str(seat.id),
            seat_code=seat.seat_code,
            programme_code=programme_code,
            academic_year=seat_year,
            seat_type=pool.seat_type.value,
            status=seat.status.value,
            reserved_for=seat.reserved_for,
            enrolment_id=str(seat.enrolment_id) if seat.enrolment_id else None,
            student_name=student.name if student is not None else None,
            assigned_at=_iso(at) if seat.enrolment_id else None,
        )
        for seat, pool, programme_code, seat_year, student, at in rows
    ]
    await audit.record_read(
        session,
        user.id,
        "student",
        [student.id for *_, student, _ in rows if student is not None],
        request_id=request_id,
    )
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


# ---------------------------------------------------------------------- enrolments


@router.get("/{institution_id}/enrolments", response_model=Page[EnrolmentRow])
async def institution_enrolments(
    institution_id: uuid.UUID,
    session: SessionDep,
    user: InstitutionUser,
    paging: Paging,
    request_id: RequestId,
    programme_id: uuid.UUID | None = None,
    status: EnrolmentStatus | None = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    admission_route: AdmissionRoute | None = None,
    year_of_study: Annotated[int | None, Query(ge=1, le=6)] = None,
    sort: EnrolmentSort = "name_asc",
) -> Page[EnrolmentRow]:
    institution = await scoped_institution(session, user, institution_id)
    stmt = (
        select(Enrolment, Student, Programme.code, Seat.seat_code)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .outerjoin(Seat, Seat.id == Enrolment.seat_id)
        .where(Enrolment.institution_id == institution.id)
    )
    if programme_id:
        stmt = stmt.where(Enrolment.programme_id == programme_id)
    if status:
        stmt = stmt.where(Enrolment.status == status)
    if academic_year:
        stmt = stmt.where(Enrolment.academic_year == academic_year)
    if admission_route:
        stmt = stmt.where(Enrolment.admission_route == admission_route)
    if year_of_study:
        stmt = stmt.where(Enrolment.year_of_study == year_of_study)
    if q:
        needle = q.strip()
        stmt = stmt.where(or_(Student.name.ilike(f"%{needle}%"), Student.apaar_last4 == needle))
    if sort == "year_desc":
        stmt = stmt.order_by(Enrolment.year_of_study.desc(), Student.name.asc(), Enrolment.id)
    elif sort == "route_asc":
        stmt = stmt.order_by(
            cast(Enrolment.admission_route, String).asc(), Student.name.asc(), Enrolment.id
        )
    else:
        stmt = stmt.order_by(Student.name.asc(), Enrolment.id)

    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    items = [
        EnrolmentRow(
            id=str(enrolment.id),
            student=StudentRef(
                id=str(student.id),
                name=student.name,
                apaar_masked=mask_apaar(student.apaar_last4),
                consent_status=student.consent_status.value,
                provisional_id=student.provisional_id,
                nationality=student.nationality,
            ),
            programme_id=str(enrolment.programme_id),
            programme_code=programme_code,
            academic_year=enrolment.academic_year,
            year_of_study=enrolment.year_of_study,
            admission_route=enrolment.admission_route.value,
            counselling_ref=enrolment.counselling_ref,
            category=enrolment.category.value,
            seat_code=seat_code,
            status=enrolment.status.value,
            uploaded_at=_iso(enrolment.uploaded_at) or "",
            upload_batch_id=str(enrolment.upload_batch_id) if enrolment.upload_batch_id else None,
            source_row_no=enrolment.source_row_no,
        )
        for enrolment, student, programme_code, seat_code in rows
    ]
    await audit.record_read(
        session,
        user.id,
        "student",
        [student.id for _, student, _, _ in rows],
        request_id=request_id,
    )
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)
