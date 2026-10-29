"""Completeness and reporting deadlines (D40; API_CONTRACT §A4.18, scoping §A4.23).

`/institutions/{id}/completeness.csv` is declared before `/institutions/{id}/completeness`.
Reads come from `institution_scores`; only `POST /completeness/refresh` calls the authority.
"""

from __future__ import annotations

import csv
import io
import time
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import (
    Adapters,
    RequestId,
    SessionDep,
    require_roles,
    scope_institutions,
    scoped_institution,
)
from app.core.ratelimit import limiter
from app.core.rules import get_rules
from app.engine import completeness
from app.models.enums import UserRole
from app.models.geo import Region, State
from app.models.institution import Institution
from app.models.user import User
from app.routers.institutions import user_key
from app.schemas.common import InstitutionRef, PageParams, page_params
from app.schemas.flags import MissingStudent

router = APIRouter(tags=["completeness"])

Reader = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION, UserRole.UNIVERSITY
        )
    ),
]
ListReader = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
Officer = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
Admin = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN))]
Paging = Annotated[PageParams, Depends(page_params)]
Year = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]
DeadlineStateName = Literal["NOT_DUE", "ON_TIME", "LATE", "OVERDUE"]
CompletenessSort = Literal["completeness_asc", "missing_desc", "name_asc"]
REFRESH_LIMIT = "6/minute"
CSV_COLUMNS = ("name", "roll_no", "programme_code", "joined_on", "round", "route", "apaar_masked")


class CaseRef(BaseModel):
    id: str
    status: str


class InstitutionCompleteness(BaseModel):
    institution: InstitutionRef
    academic_year: str
    joined: int
    uploaded_and_joined: int
    missing: int
    uploaded_not_joined: int
    completeness_pct: float | None
    published: bool
    deadline: str
    first_upload_at: str | None
    deadline_state: str
    computed_at: str | None
    source_unavailable: bool
    case: CaseRef | None
    missing_students: list[MissingStudent] = Field(default_factory=list)


class CompletenessRow(BaseModel):
    institution: InstitutionRef
    joined: int
    uploaded_and_joined: int
    missing: int
    completeness_pct: float | None
    published: bool
    deadline_state: str
    first_upload_at: str | None
    case_status: str | None


class CompletenessTotals(BaseModel):
    joined: int
    uploaded_and_joined: int
    missing: int
    completeness_pct: float | None
    deadline_states: dict[str, int]


class CompletenessPage(BaseModel):
    items: list[CompletenessRow]
    total: int
    page: int
    page_size: int
    totals: CompletenessTotals
    deadline: str


class RefreshIn(BaseModel):
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    institution_id: uuid.UUID | None = None


class RefreshOut(BaseModel):
    academic_year: str
    institutions: int
    missing: int
    cases_raised: int
    cases_updated: int
    unavailable: int
    duration_ms: int


def _year(academic_year: str | None) -> str:
    return academic_year or get_settings().academic_year


async def _ref(session: AsyncSession, institution: Institution) -> InstitutionRef:
    state = await session.get(State, institution.state_id)
    region = await session.get(Region, institution.region_id)
    return InstitutionRef(
        id=str(institution.id),
        name=institution.name,
        aicte_permanent_id=institution.aicte_permanent_id,
        state_code=state.code if state else "",
        state_name=state.name if state else "",
        region=region.code if region else "",
    )


@router.get("/institutions/{institution_id}/completeness.csv")
async def completeness_csv(
    institution_id: uuid.UUID,
    session: SessionDep,
    user: ListReader,
    request_id: RequestId,
    academic_year: Year = None,
) -> Response:
    institution = await scoped_institution(session, user, institution_id)
    year = _year(academic_year)
    body = await completeness.read(session, user, institution, year, request_id=request_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for student in body["missing_students"]:
        writer.writerow(["" if student.get(c) is None else student.get(c) for c in CSV_COLUMNS])
    filename = f"{institution.aicte_permanent_id}_{year}_missing.csv"
    return Response(
        "﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/institutions/{institution_id}/completeness", response_model=InstitutionCompleteness)
async def institution_completeness(
    institution_id: uuid.UUID,
    session: SessionDep,
    user: Reader,
    request_id: RequestId,
    academic_year: Year = None,
) -> InstitutionCompleteness:
    institution = await scoped_institution(session, user, institution_id)
    body = await completeness.read(
        session, user, institution, _year(academic_year), request_id=request_id
    )
    return InstitutionCompleteness(institution=await _ref(session, institution), **body)


@router.get("/completeness", response_model=CompletenessPage)
async def completeness_list(
    session: SessionDep,
    user: Officer,
    paging: Paging,
    academic_year: Year = None,
    region: Annotated[str | None, Query(max_length=16)] = None,
    state: Annotated[str | None, Query(max_length=2)] = None,
    deadline_state: DeadlineStateName | None = None,
    sort: CompletenessSort = "completeness_asc",
) -> CompletenessPage:
    year = _year(academic_year)
    with_approval = set(await completeness.institutions_for(session, year))
    stmt = scope_institutions(
        select(Institution, State, Region)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id),
        user,
    )
    if region and user.role is UserRole.AICTE_ADMIN:
        stmt = stmt.where(Region.code == region.upper())
    if state:
        stmt = stmt.where(State.code == state.upper())
    rows = [r for r in (await session.execute(stmt)).all() if r[0].id in with_approval]
    ids = [r[0].id for r in rows]
    stored = await completeness.scores(session, ids, year)
    firsts = await completeness.first_upload_at(session, ids, year)
    cases = await completeness.case_for(session, ids, year)
    deadline = get_rules().reporting.deadline_for(year)
    today = completeness.today_ist()

    items: list[dict[str, Any]] = []
    for institution, st, rg in rows:
        result = stored.get(institution.id) or completeness.Reconciliation()
        first = firsts.get(institution.id)
        state_now = completeness.deadline_state(deadline, first, today).value
        case = cases.get(institution.id)
        items.append(
            {
                "institution": InstitutionRef(
                    id=str(institution.id),
                    name=institution.name,
                    aicte_permanent_id=institution.aicte_permanent_id,
                    state_code=st.code,
                    state_name=st.name,
                    region=rg.code,
                ),
                "joined": result.joined,
                "uploaded_and_joined": result.uploaded_and_joined,
                "missing": result.missing,
                "completeness_pct": result.completeness_pct,
                "published": result.published,
                "deadline_state": state_now,
                "first_upload_at": completeness._iso(first),
                "case_status": case[1] if case else None,
            }
        )
    if deadline_state is not None:
        items = [i for i in items if i["deadline_state"] == deadline_state]
    if sort == "name_asc":
        items.sort(key=lambda i: (i["institution"].name.lower(), i["institution"].id))
    elif sort == "missing_desc":
        items.sort(key=lambda i: (-i["missing"], i["institution"].name.lower()))
    else:
        items.sort(
            key=lambda i: (
                i["completeness_pct"] is None,
                i["completeness_pct"] or 0,
                i["institution"].name.lower(),
            )
        )
    joined = sum(i["joined"] for i in items)
    matched = sum(i["uploaded_and_joined"] for i in items)
    states = dict.fromkeys(["NOT_DUE", "ON_TIME", "LATE", "OVERDUE"], 0)
    for item in items:
        states[item["deadline_state"]] += 1
    page = items[paging.offset : paging.offset + paging.page_size]
    return CompletenessPage(
        items=[CompletenessRow(**i) for i in page],
        total=len(items),
        page=paging.page,
        page_size=paging.page_size,
        totals=CompletenessTotals(
            joined=joined,
            uploaded_and_joined=matched,
            missing=sum(i["missing"] for i in items),
            completeness_pct=completeness.pct(matched, joined),
            deadline_states=states,
        ),
        deadline=deadline.isoformat(),
    )


@router.post("/completeness/refresh", response_model=RefreshOut)
@limiter.limit(REFRESH_LIMIT, key_func=user_key)
async def completeness_refresh(
    request: Request,
    body: RefreshIn,
    session: SessionDep,
    user: Admin,
    adapters: Adapters,
) -> RefreshOut:
    started = time.perf_counter()
    if body.institution_id is not None:
        institution = await scoped_institution(session, user, body.institution_id)
        ids = [institution.id]
    else:
        ids = await completeness.institutions_for(session, body.academic_year)
    totals = dict.fromkeys(["missing", "cases_raised", "cases_updated", "unavailable"], 0)
    for institution_id in ids:
        result = await completeness.reconcile(
            session, adapters, institution_id, body.academic_year, actor_id=user.id
        )
        totals["missing"] += result.missing
        totals["cases_raised"] += int(result.case_raised)
        totals["cases_updated"] += int(result.case_updated)
        totals["unavailable"] += int(result.source_unavailable)
    return RefreshOut(
        academic_year=body.academic_year,
        institutions=len(ids),
        duration_ms=int((time.perf_counter() - started) * 1000),
        **totals,
    )
