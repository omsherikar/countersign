"""Celery app. Week 1 ships one no-op task so the worker container comes up green."""

from __future__ import annotations

from celery import Celery

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
)


@celery_app.task(name="countersign.ping")
def ping() -> str:
    """Liveness task; the upload pipeline arrives in Week 2."""
    return "pong"
