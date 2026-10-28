from fastapi import APIRouter, Request, Response

from app.chaos import ChaosState
from app.db import Database
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def healthz(request: Request, response: Response) -> HealthResponse:
    db: Database = request.app.state.db
    chaos: ChaosState = request.app.state.chaos
    db_ok = await db.ping()
    if not db_ok:
        response.status_code = 503
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db="ok" if db_ok else "down",
        chaos=chaos.snapshot(),
    )
