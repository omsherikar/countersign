"""GET /flags and GET /flags/{id} (API_CONTRACT A2.15, A2.16, A3.13, A4.11).

Scoping: AICTE_ADMIN all; RO_OFFICER flags against institutions of its region;
INSTITUTION flags against itself, redacted (the other institution of a pair is never
named, its enrolments are hidden and counted, and it never sees who a flag is assigned
to or the notes officers keep to themselves). UNIVERSITY and STUDENT get 403.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.cases import decisions
from app.cases import service as cases
from app.cases.service import scope_flags
from app.core import audit
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError
from app.engine.contracts import DECIDED_FLAG_STATUSES, UNRESOLVED_FLAG_STATUSES
from app.models.enums import CaseActionKind, FlagStatus, FlagType, Severity, UserRole
from app.models.geo import Region, State
from app.models.institution import Institution, Programme
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import CaseAction, Flag
from app.routers._enrolment_rows import (
    build_rows,
    is_officer,
    iso,
    row_stmt,
    visible_facts,
    visible_summary,
)
from app.schemas.common import IdName, InstitutionRef, PageParams, ProgrammeRef, page_params
from app.schemas.flags import (
    CaseApproval,
    CaseHistoryItem,
    DecisionRef,
    Evidence,
    EvidenceFact,
    FlagDetail,
    FlagPage,
    FlagRow,
    MissingStudent,
)

router = APIRouter(prefix="/flags", tags=["flags"])

FlagUser = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
Paging = Annotated[PageParams, Depends(page_params)]
FlagSort = Literal["severity_desc", "created_desc"]
UNRESOLVED = "UNRESOLVED"
DECIDED = "DECIDED"
SIGNAL_TYPES = (FlagType.GHOST_RING, FlagType.ANOMALY)
Assignee = aliased(User, name="assignee")


def parse_statuses(raw: str | None) -> list[FlagStatus] | None:
    """One status, a comma-separated list, UNRESOLVED (OPEN, DOCS_REQUESTED, ESCALATED) or
    DECIDED (UPHELD, CORRECTED, WITHDRAWN)."""
    if raw is None or not raw.strip():
        return None
    out: list[FlagStatus] = []
    for token in (t.strip().upper() for t in raw.split(",") if t.strip()):
        if token == UNRESOLVED:
            wanted = list(UNRESOLVED_FLAG_STATUSES)
        elif token == DECIDED:
            wanted = list(DECIDED_FLAG_STATUSES)
        else:
            try:
                wanted = [FlagStatus(token)]
            except ValueError:
                message = (
                    "Status must be one of "
                    + ", ".join(status.value for status in FlagStatus)
                    + ", UNRESOLVED or DECIDED"
                )
                raise ApiError(
                    422,
                    "VALIDATION_ERROR",
                    f"status: {message[:1].lower()}{message[1:]}",
                    {"fields": [{"field": "status", "message": message}]},
                ) from None
        out.extend(s for s in wanted if s not in out)
    return out


def _bad_query(field: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field, "message": message}]},
    )


def assignee_filter(raw: str | None, user: User) -> Any:
    """`me`, `none` or an officer's id; ignored for a college, which never sees assignees."""
    if raw is None or not raw.strip() or user.role is UserRole.INSTITUTION:
        return None
    token = raw.strip()
    if token.lower() == "me":
        return Flag.assignee_id == user.id
    if token.lower() == "none":
        return Flag.assignee_id.is_(None)
    try:
        return Flag.assignee_id == uuid.UUID(token)
    except ValueError:
        raise _bad_query("assignee", "Assignee must be me, none or an officer's id") from None


def _base() -> Select:
    return (
        select(Flag, Institution, State, Region, Programme, Assignee.name)
        .join(Institution, Institution.id == Flag.institution_id)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .outerjoin(Programme, Programme.id == Flag.programme_id)
        .outerjoin(Assignee, Assignee.id == Flag.assignee_id)
    )


def _summary_column(user: User) -> Any:
    summary = Flag.evidence["summary"].astext
    if is_officer(user):
        return summary
    return func.coalesce(Flag.evidence["summary_for_institution"].astext, summary)


def signal_of(flag: Flag) -> str | None:
    """The signal a GHOST_RING or ANOMALY case was opened from, read from its key
    (`GHOST_RING:{signal_id}:{institution_id}`, `ANOMALY:{signal_id}`)."""
    if flag.type not in SIGNAL_TYPES:
        return None
    parts = flag.dedupe_key.split(":")
    return parts[1] if len(parts) > 1 and parts[1] else None


def signal_filter(signal_id: uuid.UUID) -> Any:
    return or_(
        Flag.dedupe_key == f"{FlagType.ANOMALY.value}:{signal_id}",
        Flag.dedupe_key.like(f"{FlagType.GHOST_RING.value}:{signal_id}:%"),
    )


async def latest_decisions(
    session: AsyncSession, flags: list[Flag]
) -> dict[uuid.UUID, DecisionRef]:
    """The latest UPHOLD, CORRECT or WITHDRAW of each decided case."""
    ids = [f.id for f in flags if f.status in DECIDED_FLAG_STATUSES]
    if not ids:
        return {}
    rows = await session.execute(
        select(CaseAction.flag_id, CaseAction.action, CaseAction.reason_code, CaseAction.at)
        .where(
            CaseAction.flag_id.in_(ids),
            CaseAction.action.in_(
                [CaseActionKind.UPHOLD, CaseActionKind.CORRECT, CaseActionKind.WITHDRAW]
            ),
        )
        .order_by(CaseAction.flag_id, CaseAction.seq.desc())
    )
    out: dict[uuid.UUID, DecisionRef] = {}
    for flag_id, action, reason_code, at in rows.all():
        out.setdefault(
            flag_id, DecisionRef(action=action.value, reason_code=reason_code, at=iso(at) or "")
        )
    return out


def _row(
    user: User,
    flag: Flag,
    institution: Institution,
    state: State,
    region: Region,
    programme: Programme | None,
    assignee_name: str | None,
    related_count: int,
    decision: DecisionRef | None = None,
) -> dict[str, Any]:
    assignee = None
    if flag.assignee_id is not None and is_officer(user):
        assignee = IdName(id=str(flag.assignee_id), name=assignee_name or "")
    rule = decisions.rule_of(flag)
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
        assignee=assignee,
        response_received=flag.response_received,
        docs_due_on=iso(flag.docs_due_on),
        last_action_at=iso(flag.last_action_at),
        covers=rule.covers.value if rule.covers else None,
        scope=rule.scope,
        decision=decision if flag.status in DECIDED_FLAG_STATUSES else None,
        signal_id=signal_of(flag) if is_officer(user) else None,
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
    assignee: Annotated[str | None, Query(max_length=64)] = None,
    response_received: bool | None = None,
    signal_id: uuid.UUID | None = None,
) -> FlagPage:
    statuses = parse_statuses(status)
    by_assignee = assignee_filter(assignee, user)
    stmt = scope_flags(_base(), user)
    if by_assignee is not None:
        stmt = stmt.where(by_assignee)
    if response_received is not None:
        stmt = stmt.where(Flag.response_received.is_(response_received))
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
    if signal_id is not None and is_officer(user):
        stmt = stmt.where(signal_filter(signal_id))
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
    decided = await latest_decisions(session, [f for f, *_ in rows])
    items = [
        FlagRow(
            **_row(
                user,
                f,
                inst,
                st,
                rg,
                prog,
                who,
                len(_visible_related(user, f, owners)),
                decided.get(f.id),
            )
        )
        for f, inst, st, rg, prog, who in rows
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
    return await build_detail(session, user, flag_id, request_id=request_id)


async def build_detail(
    session: AsyncSession, user: User, flag_id: uuid.UUID, *, request_id: str | None
) -> FlagDetail:
    """The flag as the caller may see it, with its history; the students shown are audited
    as READs. Also the response of every case action."""
    row = (
        await session.execute(
            scope_flags(_base().where(Flag.id == flag_id), user).execution_options(
                populate_existing=True
            )
        )
    ).first()
    if row is None:
        raise cases.case_not_found()
    flag, institution, state, region, programme, assignee_name = row
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
    college = user.role is UserRole.INSTITUTION
    decision = (await latest_decisions(session, [flag])).get(flag.id)
    approval = await decisions.approval_view(session, flag)
    missing: list[dict[str, Any]] = []
    if flag.type is FlagType.MISSING_FROM_UPLOAD:
        from app.engine import completeness

        missing = await completeness.missing_for_case(session, flag)
    return FlagDetail(
        **_row(
            user,
            flag,
            institution,
            state,
            region,
            programme,
            assignee_name,
            len(related),
            decision,
        ),
        evidence=Evidence(
            summary=visible_summary(user, evidence),
            facts=[EvidenceFact(**f) for f in visible_facts(user, evidence)],
            related_enrolment_ids=[str(i) for i in related],
            rule_source=evidence.get("rule_source"),
        ),
        enrolment=own,
        related_enrolments=related_rows,
        related_hidden=len(flag.related_enrolment_ids) - len(related),
        outstanding_enrolment_ids=[str(i) for i in await decisions.outstanding(session, flag)],
        approval=CaseApproval(**approval) if approval else None,
        missing_students=[MissingStudent(**m) for m in missing],
        history=[CaseHistoryItem(**item) for item in await cases.history(session, flag, user)],
        allowed_actions=[] if college else cases.allowed_actions(user.role, flag),
        can_respond=college and flag.status is FlagStatus.DOCS_REQUESTED,
    )
