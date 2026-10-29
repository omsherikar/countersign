"""Celery app, the upload task, the notices task that follows it, the completeness task
that follows the notices, and notice delivery.

The worker runs with --concurrency=1 so batches never overlap.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta

from celery import Celery
from celery.signals import worker_ready
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models.enums import NoticeDelivery, UploadStage, UploadStatus
from app.models.upload import UploadBatch
from app.models.verification import Notification

log = logging.getLogger(__name__)
UNFINISHED = (UploadStatus.QUEUED, UploadStatus.VALIDATING, UploadStatus.PROCESSING)
# QUEUED notices younger than this may still be in the hands of the request that made them
NOTICE_REQUEUE_AGE = timedelta(minutes=2)
DELIVERY_BATCH = 500

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
    """Process one upload batch; returns its final status (DONE or FAILED).

    A DONE batch then queues its student notices as a separate task, so sending them
    never holds up DONE.
    """
    try:
        status = asyncio.run(_run(uuid.UUID(batch_id)))
    except Exception:
        # run_batch fails a batch itself for anything inside a stage; this covers a
        # crash before or around it, which would otherwise leave the batch QUEUED and
        # block that college and year with 409 UPLOAD_IN_PROGRESS.
        log.exception("upload task crashed", extra={"data": {"batch_id": batch_id}})
        asyncio.run(_mark_failed(uuid.UUID(batch_id)))
        raise
    if status == UploadStatus.DONE.value:
        enqueue_notices(batch_id)
    return status


async def _send_notices(batch_id: uuid.UUID) -> int:
    from app.notices.dispatch import send_notices_for_batch

    engine = create_async_engine(get_settings().database_url(), pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return await send_notices_for_batch(batch_id, factory=factory)
    finally:
        await engine.dispose()


@celery_app.task(name="countersign.send_notices", acks_late=True)
def send_notices_task(batch_id: str) -> int:
    """Send the student notices of one DONE batch; returns how many were created. The
    college's completeness for the batch's year is reconciled next, whatever the notices
    did."""
    try:
        return asyncio.run(_send_notices(uuid.UUID(batch_id)))
    finally:
        enqueue_completeness(batch_id)


async def _batch_scope(batch_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    async def work(session: AsyncSession) -> tuple[uuid.UUID, str] | None:
        batch = await session.get(UploadBatch, batch_id)
        if batch is None or batch.status is not UploadStatus.DONE:
            return None
        return batch.institution_id, batch.academic_year

    return await _with_session(work)


async def _refresh_completeness(institution_id: uuid.UUID, academic_year: str) -> int:
    from app.engine.completeness import refresh_one

    engine = create_async_engine(get_settings().database_url(), pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return await refresh_one(factory, institution_id, academic_year)
    finally:
        await engine.dispose()


@celery_app.task(name="countersign.refresh_completeness", acks_late=True)
def refresh_completeness_task(institution_id: str, academic_year: str) -> int:
    """The completeness of one college and year, after its batch's notices."""
    return asyncio.run(_refresh_completeness(uuid.UUID(institution_id), academic_year))


def enqueue_completeness(batch_id: uuid.UUID | str) -> None:
    """Queue the completeness of a DONE batch's college and year. A failure is logged: the
    next batch, `make seed` or POST /completeness/refresh reconciles it again."""
    try:
        scope = asyncio.run(_batch_scope(uuid.UUID(str(batch_id))))
        if scope is not None:
            refresh_completeness_task.delay(str(scope[0]), scope[1])
    except Exception:
        log.exception(
            "could not queue the completeness refresh", extra={"data": {"batch_id": str(batch_id)}}
        )


def enqueue_notices(batch_id: uuid.UUID | str) -> None:
    """Queue the notices of a DONE batch. A queue failure is logged, not raised: the batch
    is already DONE and its notices can be sent again later."""
    try:
        send_notices_task.delay(str(batch_id))
    except Exception:
        log.exception(
            "could not queue student notices", extra={"data": {"batch_id": str(batch_id)}}
        )


async def _deliver_notices(notification_ids: list[uuid.UUID]) -> int:
    from app.notices.dispatch import deliver_notices

    engine = create_async_engine(get_settings().database_url(), pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return await deliver_notices(notification_ids, factory=factory)
    finally:
        await engine.dispose()


@celery_app.task(name="countersign.deliver_notices", acks_late=True)
def deliver_notices_task(notification_ids: list[str]) -> int:
    """Deliver QUEUED notices (a resend, or rows a stopped worker left); returns how many
    were sent. Only ids travel through the queue, never a token."""
    return asyncio.run(_deliver_notices([uuid.UUID(i) for i in notification_ids]))


def enqueue_delivery(notification_ids: Sequence[uuid.UUID | str]) -> bool:
    """Queue delivery of notices already committed as QUEUED. A queue failure is logged:
    the rows stay QUEUED and the worker picks them up when it next starts."""
    ids = [str(i) for i in notification_ids]
    if not ids:
        return True
    try:
        deliver_notices_task.delay(ids)
        return True
    except Exception:
        log.exception("could not queue notice delivery", extra={"data": {"count": len(ids)}})
        return False


async def _unfinished_notice_ids(created_before: datetime) -> list[uuid.UUID]:
    from app.notices.dispatch import MAX_ATTEMPTS

    async def work(session: AsyncSession) -> list[uuid.UUID]:
        stmt = (
            select(Notification.id)
            .where(
                Notification.delivery_status == NoticeDelivery.QUEUED,
                Notification.attempts < MAX_ATTEMPTS,
                Notification.created_at < created_before,
            )
            .order_by(Notification.created_at, Notification.id)
        )
        return list((await session.execute(stmt)).scalars())

    return await _with_session(work)


def enqueue_batch(batch_id: uuid.UUID) -> None:
    run_batch_task.apply_async(args=[str(batch_id)])


def requeue_unfinished() -> list[uuid.UUID]:
    """Queue every batch a previous worker left unfinished, then the delivery of QUEUED
    notices older than two minutes with tries left. run_batch skips DONE and FAILED
    batches, delivery skips anything no longer QUEUED, and the worker runs one task at a
    time, so a duplicate is harmless. Returns the batch ids."""
    started = datetime.now(UTC)
    ids = asyncio.run(_unfinished_batch_ids())
    for batch_id in ids:
        enqueue_batch(batch_id)
    if ids:
        log.info("requeued unfinished uploads", extra={"data": {"count": len(ids)}})
    notice_ids = asyncio.run(_unfinished_notice_ids(started - NOTICE_REQUEUE_AGE))
    for start in range(0, len(notice_ids), DELIVERY_BATCH):
        enqueue_delivery(notice_ids[start : start + DELIVERY_BATCH])
    if notice_ids:
        log.info("requeued notice delivery", extra={"data": {"count": len(notice_ids)}})
    return ids


@worker_ready.connect
def _requeue_on_start(**_: object) -> None:
    requeue_unfinished()
