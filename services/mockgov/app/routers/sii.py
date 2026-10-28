from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.chaos import chaos_gate
from app.db import SessionDep
from app.models import SiiAdmission
from app.names import name_score, normalize_name
from app.schemas import SiiVerifyRequest, SiiVerifyResponse

FUZZY_NAME_THRESHOLD = 90

router = APIRouter(prefix="/sii", tags=["sii"], dependencies=[Depends(chaos_gate("sii"))])

NOT_ADMITTED = SiiVerifyResponse(
    admitted=False, institution_aicte_id=None, programme=None, academic_year=None
)


@router.post("/verify", response_model=SiiVerifyResponse)
async def verify(body: SiiVerifyRequest, session: SessionDep) -> SiiVerifyResponse:
    """Study in India admission lookup by passport. The passport and nationality must match
    exactly and the name must score at least 90 against the admission record."""
    row = await session.scalar(
        select(SiiAdmission).where(
            SiiAdmission.passport_no == body.passport_no.strip().upper(),
            SiiAdmission.nationality == body.nationality.upper(),
        )
    )
    if row is None:
        return NOT_ADMITTED
    if name_score(normalize_name(body.name), row.name_normalized) < FUZZY_NAME_THRESHOLD:
        return NOT_ADMITTED
    return SiiVerifyResponse(
        admitted=True,
        institution_aicte_id=row.institution_aicte_id,
        programme=row.programme,
        academic_year=row.academic_year,
    )
