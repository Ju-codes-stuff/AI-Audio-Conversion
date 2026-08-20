"""
Celery application factory.
Broker and result backend are configured from app settings (Redis).
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "grievance_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry settings
    task_max_retries=3,
    task_default_retry_delay=30,  # seconds
    # Result expiry
    result_expires=86400,  # 24 hours
)

if __name__ == "__main__":
    celery_app.start()
