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
    # Reliability + resource hygiene for long-running analysis tasks:
    #  * acks_late: a task is acknowledged only after it finishes, so a worker
    #    crash mid-analysis requeues it instead of silently dropping it.
    #  * reject_on_worker_lost: requeue (don't fail) when the worker dies.
    #  * prefetch_multiplier=1: each worker reserves one task at a time so a
    #    long job doesn't hoard a queue of others behind it.
    #  * max_tasks_per_child: recycle workers periodically to bound memory
    #    growth from pandas / kernel churn.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
)

# Windows does not support the default prefork pool.  Fall back to the
# thread-based pool (solo is single-threaded, threads allows concurrency)
# unless the user has explicitly set a pool via CELERY_POOL env var.
if sys.platform == "win32" and not os.getenv("CELERY_POOL"):
    celery_app.conf.update(worker_pool="solo")
