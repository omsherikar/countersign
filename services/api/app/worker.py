"""Celery app and the upload task. The worker runs with --concurrency=1 so batches never overlap."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from celery import Celery
from celery.signals import worker_ready
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models.enums import UploadStage, UploadStatus
from app.models.upload import UploadBatch

log = logging.getLogger(__name__)
UNFINISHED = (UploadStatus.QUEUED, UploadStatus.VALIDATING, UploadStatus.PROCESSING)

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


async def _with_session[T](work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    engine = create_async_engine(get_settings().database_url(), pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await work(session)
    finally:
        await engine.dispose()


async def _mark_failed(batch_id: uuid.UUID) -> bool:
    """Fail a batch the task could not finish, so the college can upload again."""
    from app.engine.pipeline import stopped_error
    from app.engine.upload.spool import delete_spool

    async def work(session: AsyncSession) -> bool:
        batch = await session.get(UploadBatch, batch_id)
        if batch is None or batch.status not in UNFINISHED:
            return False
        batch.status = UploadStatus.FAILED
        batch.error = stopped_error(batch.stage or UploadStage.PARSE)
        batch.finished_at = datetime.now(UTC)
        await session.commit()
        return True

    failed = await _with_session(work)
    if failed:
        delete_spool(batch_id)
    return failed


async def _unfinished_batch_ids() -> list[uuid.UUID]:
    async def work(session: AsyncSession) -> list[uuid.UUID]:
        stmt = (
            select(UploadBatch.id)
            .where(UploadBatch.status.in_(UNFINISHED))
            .order_by(UploadBatch.created_at)
        )
        return list((await session.execute(stmt)).scalars())

    return await _with_session(work)


@celery_app.task(name="countersign.run_batch", acks_late=True)
def run_batch_task(batch_id: str) -> str:
    """Process one upload batch; returns its final status (DONE or FAILED)."""
    try:
        return asyncio.run(_run(uuid.UUID(batch_id)))
    except Exception:
        # run_batch fails a batch itself for anything inside a stage; this covers a
        # crash before or around it, which would otherwise leave the batch QUEUED and
        # block that college and year with 409 UPLOAD_IN_PROGRESS.
        log.exception("upload task crashed", extra={"data": {"batch_id": batch_id}})
        asyncio.run(_mark_failed(uuid.UUID(batch_id)))
        raise


def enqueue_batch(batch_id: uuid.UUID) -> None:
    run_batch_task.apply_async(args=[str(batch_id)])


def requeue_unfinished() -> list[uuid.UUID]:
    """Queue every batch a previous worker left unfinished. run_batch skips DONE and
    FAILED batches and the worker runs one task at a time, so a duplicate is harmless."""
    ids = asyncio.run(_unfinished_batch_ids())
    for batch_id in ids:
        enqueue_batch(batch_id)
    if ids:
        log.info("requeued unfinished uploads", extra={"data": {"count": len(ids)}})
    return ids


@worker_ready.connect
def _requeue_on_start(**_: object) -> None:
    requeue_unfinished()
