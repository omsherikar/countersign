from fastapi import APIRouter, Depends
from sqlalchemy import exists, select

from app.chaos import chaos_gate
from app.db import SessionDep
from app.models import AbcCredit, ApaarRecord
from app.schemas import AbcCreditsRequest, AbcCreditsResponse, AbcSemester

router = APIRouter(prefix="/abc", tags=["abc"], dependencies=[Depends(chaos_gate("abc"))])


@router.post("/credits", response_model=AbcCreditsResponse)
async def credits(body: AbcCreditsRequest, session: SessionDep) -> AbcCreditsResponse:
    """Semester credits the Academic Bank of Credits holds for one id in one academic year.

    An id is "known" when the APAAR registry has it or when any credits were ever uploaded
    against it, so a registered student with no uploads is known with an empty list. Each
    semester names its issuer: the affiliating university's code, or the AICTE permanent id
    of a college that issues its own credits.
    """
    known = await session.scalar(
        select(
            exists().where(ApaarRecord.apaar_id == body.apaar_id)
            | exists().where(AbcCredit.apaar_id == body.apaar_id)
        )
    )
    if not known:
        return AbcCreditsResponse(apaar_id_known=False, semesters=[])

    rows = await session.scalars(
        select(AbcCredit)
        .where(AbcCredit.apaar_id == body.apaar_id, AbcCredit.academic_year == body.academic_year)
        .order_by(AbcCredit.sem)
    )
    return AbcCreditsResponse(
        apaar_id_known=True,
        semesters=[
            AbcSemester(
                sem=r.sem,
                credits=r.credits,
                uploaded_at=r.uploaded_at,
                result=r.result,
                issuer=r.issuer,
                issuer_name=r.issuer_name,
            )
            for r in rows
        ],
    )
