"""Sending the notices of a finished upload batch (D23)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def send_notices_for_batch(
    batch_id: uuid.UUID, *, factory: async_sessionmaker[AsyncSession] | None = None
) -> int:
    """Create and deliver the notices of one DONE batch; returns how many it created.

    Implemented by the notices module. Every ACTIVE enrolment of the batch with no live
    notice for the same claim gets one notification per channel it can be reached on
    (EMAIL, DIGILOCKER). It runs on the worker as `countersign.send_notices`, queued by
    `run_batch_task` once the batch is DONE, and the seed runs it for every batch, so it
    may run more than once for a batch and must create nothing the second time. `factory`
    is the session factory to use; the worker passes one bound to the task's own event
    loop, and None means the app's `session_factory()`.
    """
    return 0
