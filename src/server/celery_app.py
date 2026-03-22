import os
import sys

from celery import Celery  # type: ignore

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "inzyts_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.server.services.engine"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Windows does not support the default prefork pool.  Fall back to the
# thread-based pool (solo is single-threaded, threads allows concurrency)
# unless the user has explicitly set a pool via CELERY_POOL env var.
if sys.platform == "win32" and not os.getenv("CELERY_POOL"):
    celery_app.conf.update(worker_pool="solo")
