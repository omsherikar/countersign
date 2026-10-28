"""Celery app and the upload task. The worker runs with --concurrency=1 so batches never overlap."""

from __future__ import annotations

import asyncio
import uuid

from celery import Celery
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

celery_app = Celery("countersign", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    # one upload at a time: take the next task only when this one is acknowledged
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="countersign.ping")
def ping() -> str:
    """Liveness task."""
    return "pong"


async def _run(batch_id: uuid.UUID) -> str:
    from app.engine.pipeline import run_batch

    # Each task runs in its own event loop, so it gets its own connection pool.
    engine = create_async_engine(get_settings().database_url(), pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        batch = await run_batch(batch_id, factory=factory)
        return batch.status.value
    finally:
        await engine.dispose()


@celery_app.task(name="countersign.run_batch", acks_late=True)
def run_batch_task(batch_id: str) -> str:
    """Process one upload batch; returns its final status (DONE or FAILED)."""
    return asyncio.run(_run(uuid.UUID(batch_id)))


def enqueue_batch(batch_id: uuid.UUID) -> None:
    run_batch_task.apply_async(args=[str(batch_id)])
