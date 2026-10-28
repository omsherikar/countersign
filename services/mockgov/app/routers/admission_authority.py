"""Simulated state admission authority: joining records and the per-college joinings list.

One state's joining-record format, simulated, served for every state. A real authority (a
state CET cell or technical education directorate) publishes who reported and joined at
which college, in which programme, by which route; this simulator holds the synthetic
equivalent from datagen (`mockgov/admission_joinings.jsonl`). Management, NRI and spot
admissions are listed too, as the state regulator approves them; international admissions are
not (Study in India holds those).

- `POST /admission-authority/joining` verifies one claimed joining, verify-only like every
  mockgov source: it never returns the stored name.
- `GET /admission-authority/joinings` lists one college's joinings for one academic year with
  names, dates of birth and roll numbers (an APAAR only as its last four digits), for
  reconciliation against the college's upload: the students a college left out have to be
  named for the college to find them. The real authority would share this with AICTE under
  its mandate; it is the one mockgov route that returns stored names.

`published` is false when the authority holds no joining at all for the state and academic
year (an authority that has not published its record yet).

Both sit behind the `admission_authority` chaos gate.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chaos import chaos_gate
from app.db import SessionDep
from app.models import AdmissionJoining
from app.names import name_score, normalize_name
from app.schemas import (
    JoiningListItem,
    JoiningListResponse,
    JoiningVerifyRequest,
    JoiningVerifyResponse,
)

FUZZY_NAME_THRESHOLD = 90
SIMULATED = "One state's joining-record format, simulated, served for every state."

router = APIRouter(
    prefix="/admission-authority",
    tags=["admission authority (simulated)"],
    dependencies=[Depends(chaos_gate("admission_authority"))],
)


async def published(session: AsyncSession, state: str | None, academic_year: str) -> bool:
    if not state:
        return False
    return bool(
        await session.scalar(
            select(
                exists().where(
                    AdmissionJoining.state == state, AdmissionJoining.academic_year == academic_year
                )
            )
        )
    )


def not_found(is_published: bool) -> JoiningVerifyResponse:
    return JoiningVerifyResponse(
        found=False, joined_on=None, round=None, route=None, category=None,
        published=is_published,
    )  # fmt: skip


@router.post("/joining", response_model=JoiningVerifyResponse, description=SIMULATED)
async def joining(body: JoiningVerifyRequest, session: SessionDep) -> JoiningVerifyResponse:
    """Confirms that the student reported and joined at this college in this programme.

    State, academic year (the year the student joined), institution and programme must
    agree. With a roll number the match is exact; otherwise the claimant's name must score at
    least 90 against the joining's name, with the same date of birth. The stored name is never
    returned.
    """
    state = body.state.upper()
    stmt = select(AdmissionJoining).where(
        AdmissionJoining.state == state,
        AdmissionJoining.academic_year == body.academic_year,
        AdmissionJoining.institution_code == body.institution_code.strip(),
        AdmissionJoining.programme == body.programme.strip(),
    )
    if body.roll_no and body.roll_no.strip():
        match = await session.scalar(stmt.where(AdmissionJoining.roll_no == body.roll_no.strip()))
    else:
        claimed = normalize_name(body.name)
        match, best = None, FUZZY_NAME_THRESHOLD - 1
        for row in await session.scalars(stmt.where(AdmissionJoining.dob == body.dob)):
            score = name_score(claimed, row.name_normalized)
            if score > best:
                match, best = row, score
    if match is None:
        return not_found(await published(session, state, body.academic_year))
    return JoiningVerifyResponse(
        found=True,
        joined_on=match.joined_on,
        round=match.round,
        route=match.route,
        category=match.category,
        published=True,
    )


@router.get("/joinings", response_model=JoiningListResponse, description=SIMULATED)
async def joinings(
    session: SessionDep,
    institution_code: Annotated[str, Query(min_length=1, max_length=64)],
    academic_year: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> JoiningListResponse:
    """Every joining the authority holds for one college and academic year, ordered by
    programme, date joined and roll number. `published` is read for the college's state, as
    the authority's other records give it."""
    code = institution_code.strip()
    rows = list(
        await session.scalars(
            select(AdmissionJoining)
            .where(
                AdmissionJoining.institution_code == code,
                AdmissionJoining.academic_year == academic_year,
            )
            .order_by(
                AdmissionJoining.programme,
                AdmissionJoining.joined_on,
                AdmissionJoining.roll_no.nulls_last(),
            )
        )
    )
    state = (
        rows[0].state
        if rows
        else await session.scalar(
            select(AdmissionJoining.state).where(AdmissionJoining.institution_code == code).limit(1)
        )
    )
    return JoiningListResponse(
        institution_code=code,
        academic_year=academic_year,
        published=bool(rows) or await published(session, state, academic_year),
        items=[
            JoiningListItem(
                roll_no=row.roll_no,
                name=row.name,
                dob=row.dob,
                programme=row.programme,
                joined_on=row.joined_on,
                round=row.round,
                route=row.route,
                category=row.category,
                apaar_last4=row.apaar_id[-4:] if row.apaar_id else None,
            )
            for row in rows
        ],
    )
