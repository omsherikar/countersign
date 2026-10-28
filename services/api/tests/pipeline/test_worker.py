import asyncio
import uuid

from app.engine import pipeline
from app.engine.upload.spool import find_spool, write_spool
from app.worker import celery_app, enqueue_batch, run_batch_task
from tests.pipeline.conftest import ROW, csv_bytes, new_batch
from tests.pipeline.fakes import FakeEngines


def test_the_upload_task_is_registered_one_at_a_time():
    task = celery_app.tasks["countersign.run_batch"]
    assert task.acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


async def test_the_task_runs_a_spooled_batch(world, spool, monkeypatch):
    monkeypatch.setattr(pipeline, "default_engines", FakeEngines)
    batch = await new_batch()
    write_spool(batch.id, "csv", csv_bytes([ROW]))
    # the task owns its event loop, as in the worker process
    assert await asyncio.to_thread(run_batch_task, str(batch.id)) == "DONE"
    assert find_spool(batch.id) is None


def test_enqueue_sends_the_batch_id(monkeypatch):
    sent = []
    monkeypatch.setattr(run_batch_task, "apply_async", lambda args: sent.append(args))
    enqueue_batch(uuid.UUID(int=7))
    assert sent == [["00000000-0000-0000-0000-000000000007"]]
