"""GET /institutions, /institutions/{id}, /{id}/seats, /{id}/enrolments (A.6 to A.9,
Addendum 1, A2.10, A2.18, A2.20) and POST /institutions/{id}/recheck (A2.13)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from slowapi.util import get_remote_address
from sqlalchemy import Float, Select, String, case, cast, func, or_, select
from sqlalchemy.orm import aliased

from app.core import audit
from app.core.config import get_settings
from app.core.deps import Adapters, RequestId, SessionDep, require_roles, scoped_institution
from app.core.errors import ApiError
from app.core.ratelimit import limiter
from app.engine.checks import recheck_pending
from app.engine.seatpools import INTERNATIONAL_RESERVED_LABEL
from app.engine.status import settle
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    EnrolmentStatus,
    InstitutionType,
    RecordStatus,
    SeatEventKind,
    SeatStatus,
    SeatType,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, ApprovalVersion, Institution, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.notices.dispatch import issue_due_proofs
from app.routers._enrolment_rows import (
    build_rows,
    iso,
    plain_row,
    row_stmt,
    unresolved_flag_exists,
)
from app.routers._stats import (
    InstitutionStats,
    completeness_body,
    institution_stats_stmt,
    region_label,
    stats_of,
)
from app.schemas.common import Page, PageParams, page_params
from app.schemas.enrolments import EnrolmentPage
from app.schemas.institutions import (
    ApprovalOut,
    InstitutionDetail,
    InstitutionRecheck,
    InstitutionRecheckBody,
    InstitutionRow,
    LastUpload,
    ProgrammeDetail,
    SeatPoolOut,
    SeatRow,
)

router = APIRouter(prefix="/institutions", tags=["institutions"])

INSTITUTION_ROLES = (
    UserRole.AICTE_ADMIN,
    UserRole.RO_OFFICER,
    UserRole.INSTITUTION,
    UserRole.UNIVERSITY,
)
InstitutionUser = Annotated[User, Depends(require_roles(*INSTITUTION_ROLES))]
OfficerUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
Paging = Annotated[PageParams, Depends(page_params)]

ListSort = Literal[
    "flags_open_desc",
    "enrolments_desc",
    "name_asc",
    "completeness_asc",
    "countersigned_asc",
    "name",
    "enrolments",
    "approved_seats",
]
DeadlineStateFilter = Literal["NOT_DUE", "ON_TIME", "LATE", "OVERDUE"]
EnrolmentSort = Literal["name_asc", "year_desc", "route_asc", "status_priority"]
# copy deck `record_status.sort.attention`
ATTENTION_ORDER = (
    RecordStatus.DISPUTED,
    RecordStatus.UNDER_REVIEW,
    RecordStatus.AWAITING_EVIDENCE,
    RecordStatus.COUNTERSIGNED,
)
INSTITUTION_RECHECK_LIMIT = "6/minute"


def user_key(request: Request) -> str:
    """Rate-limit key: the signed-in user, else the client address."""
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else get_remote_address(request)


async def _count(session, stmt: Select) -> int:
    return (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()


# ---------------------------------------------------------------------------- list


def institution_row(stats: InstitutionStats) -> InstitutionRow:
    inst, uni = stats.institution, stats.university
    return InstitutionRow(
        id=str(inst.id),
        aicte_permanent_id=inst.aicte_permanent_id,
        name=inst.name,
        type=inst.type.value,
        state_code=stats.state.code,
        state_name=stats.state.name,
        region=stats.region.code,
        region_name=region_label(stats.region),
        university_id=str(uni.id) if uni else None,
        university_name=uni.name if uni else None,
        programmes=stats.programmes,
        approved_seats=stats.approved_seats,
        admitted=stats.admitted,
        enrolments=stats.enrolments,
        flags_open=stats.flags_open,
        records=stats.records,
        countersigned_pct=stats.countersigned_pct,
        completeness_pct=stats.completeness_pct,
        missing_from_upload=stats.missing,
        deadline_state=stats.deadline_state,
    )


@router.get("", response_model=Page[InstitutionRow])
async def list_institutions(
    session: SessionDep,
    user: InstitutionUser,
    paging: Paging,
    state: Annotated[str | None, Query(max_length=2)] = None,
    region: Annotated[str | None, Query(max_length=20)] = None,
    type: InstitutionType | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    deadline_state: DeadlineStateFilter | None = None,
    sort: ListSort = "flags_open_desc",
    order: Literal["asc", "desc"] | None = None,
) -> Page[InstitutionRow]:
    year = get_settings().academic_year
    stmt = institution_stats_stmt(user, year)
    columns = stmt.selected_columns
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
    if deadline_state:
        stmt = stmt.where(columns["deadline_state"] == deadline_state)

    enrolments_col = columns["enrolments"]
    flags_col = columns["flags_open"]
    name_key = func.lower(Institution.name)
    if sort == "flags_open_desc":
        keys = [flags_col.asc() if order == "asc" else flags_col.desc(), enrolments_col.desc()]
    elif sort in ("enrolments_desc", "enrolments"):
        keys = [enrolments_col.asc() if order == "asc" else enrolments_col.desc()]
    elif sort == "approved_seats":
        seats_col = columns["approved_seats"]
        keys = [seats_col.asc() if order == "asc" else seats_col.desc()]
    elif sort == "completeness_asc":
        keys = [columns["completeness_pct"].asc().nulls_last()]
    elif sort == "countersigned_asc":
        share = case(
            (enrolments_col > 0, cast(columns["countersigned"], Float) / enrolments_col),
            else_=None,
        )
        keys = [share.asc().nulls_last()]
    else:
        keys = [name_key.desc() if order == "desc" else name_key.asc()]
    stmt = stmt.order_by(*keys, Institution.name.asc(), Institution.id.asc())

    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    items = [institution_row(stats_of(row)) for row in rows]
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
    current_versions: dict[uuid.UUID, ApprovalVersion] = {}
    if approval_ids:
        current_versions = {
            v.approval_id: v
            for v in (
                await session.execute(
                    select(ApprovalVersion)
                    .join(Approval, Approval.id == ApprovalVersion.approval_id)
                    .where(
                        Approval.id.in_(approval_ids),
                        ApprovalVersion.version == Approval.current_version,
                    )
                )
            ).scalars()
        }

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
                Enrolment.cohort_year == year,
            )
            .group_by(Enrolment.programme_id)
        )
    ).all()
    enrolled = {pid: (total, unseated) for pid, total, unseated in enrol_counts}

    order = {t: i for i, t in enumerate(SeatType)}
    programmes: list[ProgrammeDetail] = []
    for programme, approval in prog_rows:
        total, unseated = enrolled.get(programme.id, (0, 0))
        version = current_versions.get(approval.id)
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
                mode=programme.mode.value,
                approval=ApprovalOut(
                    id=str(approval.id),
                    academic_year=approval.academic_year,
                    approved_intake=approval.approved_intake,
                    cutoff_date=approval.cutoff_date.isoformat() if approval.cutoff_date else None,
                    version=approval.current_version,
                    effective_from=version.effective_from.isoformat() if version else None,
                    source=version.source if version else None,
                ),
                enrolments=total,
                seated=sum(p.assigned for p in pools_out),
                unseated=unseated,
                pools=pools_out,
            )
        )

    [row] = (
        await session.execute(
            institution_stats_stmt(user, year).where(Institution.id == institution.id)
        )
    ).all()
    stats = stats_of(row)
    completeness = await completeness_body(session, institution.id, year, with_students=False)

    batch = (
        (
            await session.execute(
                select(UploadBatch)
                .where(
                    UploadBatch.institution_id == institution.id,
                    UploadBatch.academic_year == year,
                )
                .order_by(UploadBatch.created_at.desc(), UploadBatch.id.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    last_upload = None
    if batch is not None:
        counts = batch.counts or {}
        last_upload = LastUpload(
            batch_id=str(batch.id),
            uploaded_at=iso(batch.created_at) or "",
            rows=int(counts.get("rows", batch.total_rows or 0)),
            errors=int(counts.get("errors", 0)),
            status=batch.status.value,
        )

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
        approved_seats=stats.approved_seats,
        admitted=stats.admitted,
        enrolments=stats.enrolments,
        flags_open=stats.flags_open,
        records=stats.records,
        countersigned_pct=stats.countersigned_pct,
        completeness_pct=stats.completeness_pct,
        missing_from_upload=stats.missing,
        deadline_state=stats.deadline_state,
        completeness=completeness,
        last_upload=last_upload,
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
            assigned_at=iso(at) if seat.enrolment_id else None,
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


@router.get("/{institution_id}/enrolments", response_model=EnrolmentPage)
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
    record_status: Annotated[str | None, Query(max_length=120)] = None,
    flagged: bool | None = None,
    seated: bool | None = None,
    sort: EnrolmentSort = "name_asc",
) -> EnrolmentPage:
    """The college's records with their status and brief rows (API_CONTRACT §A4.5).
    `record_status` takes one value or a comma-separated list; `status_counts` counts the
    ACTIVE records that match every other filter but `status`."""
    statuses = _record_statuses(record_status)
    institution = await scoped_institution(session, user, institution_id)
    filters = [Enrolment.institution_id == institution.id]
    if programme_id:
        filters.append(Enrolment.programme_id == programme_id)
    if academic_year:
        filters.append(Enrolment.academic_year == academic_year)
    if admission_route:
        filters.append(Enrolment.admission_route == admission_route)
    if year_of_study:
        filters.append(Enrolment.year_of_study == year_of_study)
    if flagged is not None:
        filters.append(unresolved_flag_exists() if flagged else ~unresolved_flag_exists())
    if seated is not None:
        filters.append(Enrolment.seat_id.is_not(None) if seated else Enrolment.seat_id.is_(None))
    if q:
        needle = q.strip()
        filters.append(or_(Student.name.ilike(f"%{needle}%"), Student.apaar_last4 == needle))
    counts = await _status_counts(session, filters)

    stmt = row_stmt().where(*filters)
    if status:
        stmt = stmt.where(Enrolment.status == status)
    if statuses:
        stmt = stmt.where(
            Enrolment.record_status.in_(statuses), Enrolment.status == EnrolmentStatus.ACTIVE
        )
    if sort == "year_desc":
        stmt = stmt.order_by(Enrolment.year_of_study.desc(), Student.name.asc(), Enrolment.id)
    elif sort == "route_asc":
        stmt = stmt.order_by(
            cast(Enrolment.admission_route, String).asc(), Student.name.asc(), Enrolment.id
        )
    elif sort == "status_priority":
        stmt = stmt.order_by(
            _attention_order(), Enrolment.record_status_at.asc().nulls_last(), Enrolment.id
        )
    else:
        stmt = stmt.order_by(Student.name.asc(), Enrolment.id)

    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    items = [plain_row(r) for r in await build_rows(session, rows)]
    await audit.record_read(
        session, user.id, "student", [r[1].id for r in rows], request_id=request_id
    )
    return EnrolmentPage(
        items=items,
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        status_counts=counts,
    )


def _record_statuses(raw: str | None) -> list[RecordStatus]:
    """`DISPUTED` or `UNDER_REVIEW,DISPUTED`; anything else is a 422."""
    if not raw:
        return []
    out: list[RecordStatus] = []
    for part in raw.split(","):
        value = part.strip().upper()
        if not value:
            continue
        try:
            out.append(RecordStatus(value))
        except ValueError:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"record_status: {part.strip()} is not a record status.",
                {"fields": [{"field": "record_status", "message": "Not a record status."}]},
            ) from None
    return out


def _attention_order():
    """Disputed, Under review, Awaiting evidence, then Countersigned (copy deck
    `record_status.sort.attention`); records that are not ACTIVE last."""
    return case(
        (Enrolment.status != EnrolmentStatus.ACTIVE, len(ATTENTION_ORDER)),
        *((Enrolment.record_status == value, n) for n, value in enumerate(ATTENTION_ORDER)),
        else_=len(ATTENTION_ORDER),
    )


async def _status_counts(session, filters: list) -> dict[str, int]:
    """ACTIVE records matching the filters, by record status, every status present."""
    counts = dict.fromkeys((s.value for s in RecordStatus), 0)
    rows = await session.execute(
        select(Enrolment.record_status, func.count())
        .select_from(Enrolment)
        .join(Student, Student.id == Enrolment.student_id)
        .where(*filters, Enrolment.status == EnrolmentStatus.ACTIVE)
        .group_by(Enrolment.record_status)
    )
    for value, n in rows.all():
        counts[value.value] = n
    return counts


# ------------------------------------------------------------------------- recheck


@router.post("/{institution_id}/recheck", response_model=InstitutionRecheck)
@limiter.limit(INSTITUTION_RECHECK_LIMIT, key_func=user_key)
async def institution_recheck(
    request: Request,
    institution_id: uuid.UUID,
    session: SessionDep,
    user: OfficerUser,
    adapters: Adapters,
    body: InstitutionRecheckBody | None = None,
) -> InstitutionRecheck:
    """Re-run every PENDING and SOURCE_UNAVAILABLE check except STUDENT of the institution's
    ACTIVE enrolments."""
    started = time.perf_counter()
    year = (body.academic_year if body else None) or get_settings().academic_year
    institution = await scoped_institution(session, user, institution_id)
    ids = (
        (
            await session.execute(
                select(Enrolment.id)
                .where(
                    Enrolment.institution_id == institution.id,
                    Enrolment.academic_year == year,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
                .order_by(Enrolment.source_row_no.nulls_last(), Enrolment.id)
            )
        )
        .scalars()
        .all()
    )
    result = await recheck_pending(
        session,
        ids,
        adapters,
        concurrency=get_settings().checks_concurrency,
        actor_id=user.id,
    )
    # the statuses follow the rows, then the attestations are asked for (API_CONTRACT §A4.6)
    await settle(session, issue=False)
    await issue_due_proofs(session, ids)
    return InstitutionRecheck(
        institution_id=str(institution.id),
        academic_year=year,
        enrolments=result.enrolments,
        rechecked=result.rechecked,
        outcomes=result.outcomes or dict.fromkeys((s.value for s in CheckStatus), 0),
        flags_raised=result.flags.created,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
