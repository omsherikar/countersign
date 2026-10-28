"""GET /flags and GET /flags/{id} (API_CONTRACT A2.15, A2.16), read-only in Week 2.

Scoping: AICTE_ADMIN all; RO_OFFICER flags against institutions of its region;
INSTITUTION flags against itself, redacted (the other institution of a pair is never
named, its enrolments are hidden and counted). UNIVERSITY and STUDENT get 403.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, case, distinct, false, func, or_, select

from app.core import audit
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError, not_found
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.models.enums import FlagStatus, FlagType, Severity, UserRole
from app.models.geo import Region, State
from app.models.institution import Institution, Programme
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import Flag
from app.routers._enrolment_rows import (
    build_rows,
    is_officer,
    iso,
    row_stmt,
    visible_facts,
    visible_summary,
)
from app.schemas.common import InstitutionRef, PageParams, ProgrammeRef, page_params
from app.schemas.flags import Evidence, EvidenceFact, FlagDetail, FlagPage, FlagRow

router = APIRouter(prefix="/flags", tags=["flags"])

FlagUser = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
Paging = Annotated[PageParams, Depends(page_params)]
FlagSort = Literal["severity_desc", "created_desc"]
UNRESOLVED = "UNRESOLVED"


def scope_flags(stmt: Select, user: User) -> Select:
    """Restrict a SELECT joined to the flag's institution to what the user may see."""
    if user.role is UserRole.AICTE_ADMIN:
        return stmt
    if user.role is UserRole.RO_OFFICER:
        return stmt.where(Institution.region_id == user.region_id)
    if user.role is UserRole.INSTITUTION:
        return stmt.where(Flag.institution_id == user.institution_id)
    return stmt.where(false())


def parse_statuses(raw: str | None) -> list[FlagStatus] | None:
    """One status, a comma-separated list, or UNRESOLVED (OPEN, DOCS_REQUESTED, ESCALATED)."""
    if raw is None or not raw.strip():
        return None
    out: list[FlagStatus] = []
    for token in (t.strip().upper() for t in raw.split(",") if t.strip()):
        if token == UNRESOLVED:
            wanted = list(UNRESOLVED_FLAG_STATUSES)
        else:
            try:
                wanted = [FlagStatus(token)]
            except ValueError:
                message = (
                    "Status must be one of OPEN, DOCS_REQUESTED, CLEARED, ESCALATED, CONFIRMED "
                    "or UNRESOLVED"
                )
                raise ApiError(
                    422,
                    "VALIDATION_ERROR",
                    f"status: {message[:1].lower()}{message[1:]}",
                    {"fields": [{"field": "status", "message": message}]},
                ) from None
        out.extend(s for s in wanted if s not in out)
    return out


def _base() -> Select:
    return (
        select(Flag, Institution, State, Region, Programme)
        .join(Institution, Institution.id == Flag.institution_id)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .outerjoin(Programme, Programme.id == Flag.programme_id)
    )


def _summary_column(user: User) -> Any:
    summary = Flag.evidence["summary"].astext
    if is_officer(user):
        return summary
    return func.coalesce(Flag.evidence["summary_for_institution"].astext, summary)


def _row(
    user: User,
    flag: Flag,
    institution: Institution,
    state: State,
    region: Region,
    programme: Programme | None,
    related_count: int,
) -> dict[str, Any]:
    return dict(
        id=str(flag.id),
        type=flag.type.value,
        severity=flag.severity.value,
        status=flag.status.value,
        institution=InstitutionRef(
            id=str(institution.id),
            name=institution.name,
            aicte_permanent_id=institution.aicte_permanent_id,
            state_code=state.code,
            state_name=state.name,
            region=region.code,
        ),
        programme=ProgrammeRef(id=str(programme.id), code=programme.code, name=programme.name)
        if programme is not None
        else None,
        enrolment_id=str(flag.enrolment_id) if flag.enrolment_id else None,
        academic_year=flag.academic_year,
        summary=visible_summary(user, flag.evidence),
        related_count=related_count,
        assignee=None,
        created_at=iso(flag.created_at) or "",
        updated_at=iso(flag.updated_at or flag.created_at) or "",
    )


async def _owners(session, ids: set[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Enrolment.id, Enrolment.institution_id).where(Enrolment.id.in_(ids))
    )
    return dict(rows.all())


def _visible_related(user: User, flag: Flag, owners: dict[uuid.UUID, uuid.UUID]) -> list:
    if is_officer(user):
        return list(flag.related_enrolment_ids)
    return [i for i in flag.related_enrolment_ids if owners.get(i) == user.institution_id]


@router.get("", response_model=FlagPage)
async def list_flags(
    session: SessionDep,
    user: FlagUser,
    paging: Paging,
    type: FlagType | None = None,
    severity: Severity | None = None,
    status: Annotated[str | None, Query(max_length=120)] = None,
    institution_id: uuid.UUID | None = None,
    programme_id: uuid.UUID | None = None,
    state: Annotated[str | None, Query(max_length=2)] = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    sort: FlagSort = "severity_desc",
) -> FlagPage:
    statuses = parse_statuses(status)
    stmt = scope_flags(_base(), user)
    if type is not None:
        stmt = stmt.where(Flag.type == type)
    if severity is not None:
        stmt = stmt.where(Flag.severity == severity)
    if statuses is not None:
        stmt = stmt.where(Flag.status.in_(statuses))
    if institution_id is not None:
        stmt = stmt.where(Flag.institution_id == institution_id)
    if programme_id is not None:
        stmt = stmt.where(Flag.programme_id == programme_id)
    if state:
        stmt = stmt.where(State.code == state.upper())
    if academic_year:
        stmt = stmt.where(Flag.academic_year == academic_year)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                _summary_column(user).ilike(needle),
                Institution.name.ilike(needle),
                Institution.aicte_permanent_id.ilike(needle),
            )
        )

    filtered = stmt.order_by(None).subquery()
    total, institutions = (
        await session.execute(select(func.count(), func.count(distinct(filtered.c.institution_id))))
    ).one()
    if sort == "created_desc":
        stmt = stmt.order_by(Flag.created_at.desc(), Flag.id)
    else:
        rank = case(
            (Flag.severity == Severity.HIGH, 0),
            (Flag.severity == Severity.MEDIUM, 1),
            else_=2,
        )
        stmt = stmt.order_by(rank, Flag.created_at.asc(), Flag.id)
    rows = (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).all()
    owners = (
        {}
        if is_officer(user)
        else await _owners(session, {i for f, *_ in rows for i in f.related_enrolment_ids})
    )
    items = [
        FlagRow(**_row(user, f, inst, st, rg, prog, len(_visible_related(user, f, owners))))
        for f, inst, st, rg, prog in rows
    ]
    return FlagPage(
        items=items,
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        institutions=institutions,
    )


@router.get("/{flag_id}", response_model=FlagDetail)
async def flag_detail(
    flag_id: uuid.UUID, session: SessionDep, user: FlagUser, request_id: RequestId
) -> FlagDetail:
    row = (await session.execute(scope_flags(_base().where(Flag.id == flag_id), user))).first()
    if row is None:
        raise not_found("Flag")
    flag, institution, state, region, programme = row
    wanted = list(dict.fromkeys([*flag.related_enrolment_ids, flag.enrolment_id]))
    wanted = [i for i in wanted if i is not None]
    built = {
        uuid.UUID(r.id): r
        for r in await build_rows(
            session, (await session.execute(row_stmt().where(Enrolment.id.in_(wanted)))).all()
        )
    }

    def visible(enrolment_id: uuid.UUID) -> bool:
        row = built.get(enrolment_id)
        if row is None:
            return False
        return is_officer(user) or row.institution.id == str(user.institution_id)

    related = [i for i in flag.related_enrolment_ids if visible(i)]
    own = built[flag.enrolment_id] if flag.enrolment_id and visible(flag.enrolment_id) else None
    related_rows = [built[i] for i in related]
    shown_students = [uuid.UUID(r.student.id) for r in ([own] if own else []) + related_rows]
    await audit.record_read(session, user.id, "student", shown_students, request_id=request_id)

    evidence = flag.evidence
    return FlagDetail(
        **_row(user, flag, institution, state, region, programme, len(related)),
        evidence=Evidence(
            summary=visible_summary(user, evidence),
            facts=[EvidenceFact(**f) for f in visible_facts(user, evidence)],
            related_enrolment_ids=[str(i) for i in related],
            rule_source=evidence.get("rule_source"),
        ),
        enrolment=own,
        related_enrolments=related_rows,
        related_hidden=len(flag.related_enrolment_ids) - len(related),
        history=[],
    )
