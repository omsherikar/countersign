from fastapi import APIRouter, Request

from app.chaos import ChaosState
from app.db import SessionDep
from app.schemas import ChaosEntry, ChaosUpdateRequest

router = APIRouter(prefix="/admin", tags=["admin"])


def _chaos(request: Request) -> ChaosState:
    return request.app.state.chaos


@router.get("/chaos", response_model=dict[str, ChaosEntry])
async def get_chaos(request: Request) -> dict:
    return _chaos(request).snapshot()


@router.post("/chaos", response_model=dict[str, ChaosEntry])
async def set_chaos(body: ChaosUpdateRequest, request: Request, session: SessionDep) -> dict:
    """Overrides one source (or `all`). Returns only the entries that changed."""
    chaos = _chaos(request)
    changed = chaos.set(body.source, body.latency_ms, body.fail_rate, body.down)
    await chaos.save(session)
    return changed


@router.post("/chaos/reset", response_model=dict[str, ChaosEntry])
async def reset_chaos(request: Request, session: SessionDep) -> dict:
    """Puts every source back to the MOCKGOV_LATENCY_MS / MOCKGOV_FAIL_RATE defaults."""
    chaos = _chaos(request)
    chaos.reset()
    await chaos.save(session)
    return chaos.snapshot()
