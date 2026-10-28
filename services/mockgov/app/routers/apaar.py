from fastapi import APIRouter, Depends

from app.chaos import chaos_gate
from app.db import SessionDep
from app.models import ApaarRecord
from app.names import name_score, normalize_name
from app.schemas import ApaarVerifyRequest, ApaarVerifyResponse

router = APIRouter(prefix="/apaar", tags=["apaar"], dependencies=[Depends(chaos_gate("apaar"))])


@router.post("/verify", response_model=ApaarVerifyResponse)
async def verify(body: ApaarVerifyRequest, session: SessionDep) -> ApaarVerifyResponse:
    """Verify-only: reports whether the id exists and how well the claim matches.

    The stored name is never returned; only a similarity score against it.
    """
    record = await session.get(ApaarRecord, body.apaar_id)
    if record is None:
        return ApaarVerifyResponse(exists=False, name_score=0, dob_match=False)
    return ApaarVerifyResponse(
        exists=True,
        name_score=name_score(normalize_name(body.name), record.name_normalized),
        dob_match=record.dob == body.dob,
    )
