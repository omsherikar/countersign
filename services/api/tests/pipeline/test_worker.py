import asyncio
import uuid

import pytest

from app import worker
from app.db.session import session_factory
from app.engine import pipeline
from app.engine.upload.spool import find_spool, write_spool
from app.models.enums import UploadStatus
from app.worker import (
    celery_app,
    enqueue_batch,
    requeue_unfinished,
    run_batch_task,
    send_notices_task,
)
from tests.pipeline.conftest import ROW, csv_bytes, new_batch
from tests.pipeline.fakes import FakeEngines


@pytest.fixture(autouse=True)
def queued_notices(monkeypatch) -> list[str]:
    """Batch ids whose notices were queued; nothing here reaches a real broker."""
    queued: list[str] = []
    monkeypatch.setattr(send_notices_task, "delay", lambda batch_id: queued.append(batch_id))
    return queued


def test_the_upload_task_is_registered_one_at_a_time():
    task = celery_app.tasks["countersign.run_batch"]
    assert task.acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


async def test_the_task_runs_a_spooled_batch(world, spool, monkeypatch, queued_notices):
    monkeypatch.setattr(pipeline, "default_engines", FakeEngines)
    batch = await new_batch()
    write_spool(batch.id, "csv", csv_bytes([ROW]))
    # the task owns its event loop, as in the worker process
    assert await asyncio.to_thread(run_batch_task, str(batch.id)) == "DONE"
    assert find_spool(batch.id) is None
    # a DONE batch queues its student notices as a task of their own
    assert queued_notices == [str(batch.id)]


async def test_a_failed_batch_queues_no_notices(world, spool, queued_notices):
    batch = await new_batch()  # nothing spooled: the file cannot be read
    assert await asyncio.to_thread(run_batch_task, str(batch.id)) == "FAILED"
    assert queued_notices == []


async def test_a_batch_stays_done_when_its_notices_cannot_be_queued(world, spool, monkeypatch):
    monkeypatch.setattr(pipeline, "default_engines", FakeEngines)

    def broker_down(batch_id):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(send_notices_task, "delay", broker_down)
    batch = await new_batch()
    write_spool(batch.id, "csv", csv_bytes([ROW]))
    assert await asyncio.to_thread(run_batch_task, str(batch.id)) == "DONE"
    async with session_factory()() as session:
        assert (await session.get(type(batch), batch.id)).status is UploadStatus.DONE


def test_the_notices_task_is_registered():
    task = celery_app.tasks["countersign.send_notices"]
    assert task.acks_late is True
    assert send_notices_task.run(str(uuid.UUID(int=9))) == 0  # sending is not built yet


def test_enqueue_sends_the_batch_id(monkeypatch):
    sent = []
    monkeypatch.setattr(run_batch_task, "apply_async", lambda args: sent.append(args))
    enqueue_batch(uuid.UUID(int=7))
    assert sent == [["00000000-0000-0000-0000-000000000007"]]


async def test_a_crashed_task_fails_the_batch_not_leaves_it_queued(
    world, spool, monkeypatch, queued_notices
):
    batch = await new_batch()
    write_spool(batch.id, "csv", csv_bytes([ROW]))

    async def boom(_batch_id):
        raise RuntimeError("worker could not start the batch")

    monkeypatch.setattr(worker, "_run", boom)
    with pytest.raises(RuntimeError):
        await asyncio.to_thread(run_batch_task, str(batch.id))
    async with session_factory()() as session:
        stored = await session.get(type(batch), batch.id)
        assert stored.status is UploadStatus.FAILED
        assert stored.error.startswith("Processing stopped while")
        assert stored.error.endswith("Upload the file again; rows already saved are kept.")
    assert find_spool(batch.id) is None
    assert queued_notices == []


async def test_the_worker_requeues_unfinished_batches_on_start(world, spool, monkeypatch):
    monkeypatch.setattr(pipeline, "default_engines", FakeEngines)
    stuck = await new_batch(filename="stuck.csv")
    done = await new_batch(filename="done.csv")
    write_spool(done.id, "csv", csv_bytes([ROW]))
    assert await asyncio.to_thread(run_batch_task, str(done.id)) == "DONE"
    sent = []
    monkeypatch.setattr(worker, "enqueue_batch", lambda batch_id: sent.append(batch_id))
    assert await asyncio.to_thread(requeue_unfinished) == [stuck.id]
    assert sent == [stuck.id]
