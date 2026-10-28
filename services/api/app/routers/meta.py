"""GET /meta/regions and /meta/states (API_CONTRACT A.14): any authenticated role."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, SessionDep
from app.models.geo import Region, State
from app.schemas.admin import ItemsOnly, RegionMeta, StateMeta

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/regions", response_model=ItemsOnly)
async def regions(session: SessionDep, _user: CurrentUser) -> ItemsOnly:
    rows = sorted((await session.execute(select(Region))).scalars(), key=lambda r: r.name)
    return ItemsOnly(items=[RegionMeta(code=r.code, name=r.name, hq_city=r.hq_city) for r in rows])


@router.get("/states", response_model=ItemsOnly)
async def states(session: SessionDep, _user: CurrentUser) -> ItemsOnly:
    rows = (
        await session.execute(select(State, Region).join(Region, Region.id == State.region_id))
    ).all()
    rows = sorted(rows, key=lambda pair: pair[0].name)
    return ItemsOnly(items=[StateMeta(code=s.code, name=s.name, region=r.code) for s, r in rows])
