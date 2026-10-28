"""mockgov: simulated government systems for the Countersign demo.

APAAR registry, state counselling allotments, the state admission authority's joining
records, Academic Bank of Credits, DigiLocker inbox and sign-in, and Study in India, each
behind a chaos gate (latency, failure rate, down); the registries are verify-only. Separate
process and database; the Countersign API only ever reaches this over HTTP. Every record is
synthetic.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.chaos import ChaosState
from app.config import Settings, get_settings
from app.db import Database
from app.digilocker_signin import load_signing_key
from app.errors import install_error_handlers
from app.routers import (
    abc,
    admin,
    admission_authority,
    apaar,
    counselling,
    digilocker,
    digilocker_oauth,
    digilocker_ui,
    healthz,
    sii,
)

DESCRIPTION = (
    "Simulated government systems for Countersign, with synthetic data only. Verify-only; "
    "no auth. The state admission authority serves one state's joining-record format, "
    "simulated, for every state. DigiLocker sign-in is a labelled simulation over synthetic "
    "accounts (demo OTP 123456)."
)


async def startup(app: FastAPI) -> None:
    """Connect, create any missing tables, load persisted chaos settings and the DigiLocker
    sign-in key."""
    db: Database = app.state.db
    await db.create_all()
    async with db.sessions() as session:
        await app.state.chaos.load(session)
        app.state.digilocker_key = await load_signing_key(session, app.state.settings)


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
        description=DESCRIPTION,
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
        admission_authority.router,
        abc.router,
        digilocker.router,
        digilocker_ui.router,
        digilocker_oauth.router,
        sii.router,
        admin.router,
    ):
        app.include_router(router)
    return app


app = create_app()
