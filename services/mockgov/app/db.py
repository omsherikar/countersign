"""Async SQLAlchemy engine and session for the mockgov database.

Schema management: `Base.metadata.create_all` on startup instead of Alembic. The registries
are throwaway demo data that `python -m app.seed --reset` rebuilds in seconds, so a migration
history buys nothing here. If a column changes, drop the database (or `make nuke`) and reseed.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # A database created before the admission authority source existed keeps a
            # 16-character chaos.source; widen it so "admission_authority" fits. A no-op
            # once the column is 32 wide.
            await conn.execute(text("ALTER TABLE chaos ALTER COLUMN source TYPE varchar(32)"))

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.sessions() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
