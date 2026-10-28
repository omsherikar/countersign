"""mockgov: simulated government systems for the Countersign demo.

APAAR registry, state counselling allotments, Academic Bank of Credits, DigiLocker inbox and
Study in India, each verify-only, each behind a chaos gate (latency, failure rate, down).
Separate process and database; the Countersign API only ever reaches this over HTTP.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.chaos import ChaosState
from app.config import Settings, get_settings
from app.db import Database
from app.errors import install_error_handlers
from app.routers import abc, admin, apaar, counselling, digilocker, digilocker_ui, healthz, sii


async def startup(app: FastAPI) -> None:
    """Connect, create any missing tables and load persisted chaos settings."""
    db: Database = app.state.db
    await db.create_all()
    async with db.sessions() as session:
        await app.state.chaos.load(session)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await startup(app)
    try:
        yield
    finally:
        await app.state.db.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="mockgov",
        version="0.1.0",
        description="Simulated government systems for Countersign. Verify-only; no auth.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_url())
    app.state.chaos = ChaosState(settings.mockgov_latency_ms, settings.mockgov_fail_rate)

    install_error_handlers(app)
    for router in (
        healthz.router,
        apaar.router,
        counselling.router,
        abc.router,
        digilocker.router,
        digilocker_ui.router,
        sii.router,
        admin.router,
    ):
        app.include_router(router)
    return app


app = create_app()
