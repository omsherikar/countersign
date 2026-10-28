from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.chaos import chaos_gate
from app.db import SessionDep
from app.models import CounsellingAllotment
from app.names import name_score, normalize_name
from app.schemas import CounsellingVerifyRequest, CounsellingVerifyResponse

FUZZY_NAME_THRESHOLD = 90

router = APIRouter(
    prefix="/counselling",
    tags=["counselling"],
    dependencies=[Depends(chaos_gate("counselling"))],
)

NOT_FOUND = CounsellingVerifyResponse(found=False, round=None, category=None, allotment_ref=None)


@router.post("/verify", response_model=CounsellingVerifyResponse)
async def verify(body: CounsellingVerifyRequest, session: SessionDep) -> CounsellingVerifyResponse:
    """Confirms an allotment in the state's counselling list.

    With a roll number the match is exact; otherwise the claimant's name must score at
    least 90 against the allotment's name, with the same date of birth. State, year and
    programme always have to agree, and the institution when the caller gives one.
    """
    stmt = select(CounsellingAllotment).where(
        CounsellingAllotment.state == body.state.upper(),
        CounsellingAllotment.year == body.year,
        CounsellingAllotment.programme == body.programme,
    )
    if body.institution_aicte_id:
        stmt = stmt.where(CounsellingAllotment.institution_aicte_id == body.institution_aicte_id)

    if body.roll_no:
        stmt = stmt.where(CounsellingAllotment.roll_no == body.roll_no.strip())
        match = await session.scalar(stmt)
    else:
        stmt = stmt.where(CounsellingAllotment.dob == body.dob)
        claimed = normalize_name(body.name)
        match, best = None, FUZZY_NAME_THRESHOLD - 1
        for row in await session.scalars(stmt):
            score = name_score(claimed, row.name_normalized)
            if score > best:
                match, best = row, score

    if match is None:
        return NOT_FOUND
    return CounsellingVerifyResponse(
        found=True,
        round=match.round,
        category=match.category,
        allotment_ref=match.allotment_ref,
    )
