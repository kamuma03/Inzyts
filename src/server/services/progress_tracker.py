"""
ProgressTracker - Redis-backed job progress tracking.

Maps structured LogEvents to progress percentages and stores them
in Redis hashes for retrieval by the API and frontend.

Dual-write contract
-------------------
Progress is written to **two** stores with different roles:

* **Redis** (source of truth for real-time): Queried by the frontend via
  Socket.IO and the ``GET /jobs/{id}`` endpoint for *running* jobs.
  Keys auto-expire after 24 h (TTL_SECONDS).

* **SQL JobProgress table** (audit log): Provides a persistent record once
  Redis keys expire.  Used by ``GET /jobs/{id}`` for *completed/failed* jobs
  and for historical dashboards.

Redis is always written first; the SQL write is best-effort (failures are
logged at DEBUG level and do not block the pipeline).
"""

import os
import time
import redis
from typing import Any, Optional, Dict

from src.utils.logger import get_logger

progress_logger = get_logger()

# Event-to-progress mapping
EVENT_PROGRESS_MAP: Dict[str, tuple[int, str]] = {
    # (progress_percentage, human_readable_message)
    "MODE_DETECTED": (5, "Analysis mode detected"),
    "MODE_EXPLICIT": (5, "Analysis mode detected"),
    "MODE_INFERRED": (5, "Analysis mode detected"),
    "MODE_DEFAULT": (5, "Analysis mode detected"),
    "PHASE1_START": (10, "Starting data profiling..."),
    "AGENT_INVOKED:DataProfiler": (15, "Profiling data..."),
    "AGENT_COMPLETED:DataProfiler": (25, "Data profiling complete"),
    "AGENT_INVOKED:ProfileCodeGenerator": (28, "Generating profile code..."),
    "AGENT_COMPLETED:ProfileCodeGenerator": (30, "Profile code generated"),
    "AGENT_INVOKED:ProfileValidatorAgent": (32, "Validating profile..."),
    "PROFILE_LOCK_GRANTED": (35, "Profile locked"),
    "CACHE_SAVED": (37, "Profile cached"),
    "PHASE1_COMPLETE": (38, "Phase 1 complete"),
    "PHASE2_START": (40, "Starting analysis phase..."),
    "AGENT_INVOKED:StrategyAgent": (45, "Designing analysis strategy..."),
    "AGENT_INVOKED:ForecastingStrategyAgent": (45, "Designing forecasting strategy..."),
    "AGENT_INVOKED:ComparativeStrategyAgent": (45, "Designing comparative strategy..."),
    "AGENT_INVOKED:DiagnosticStrategyAgent": (45, "Designing diagnostic strategy..."),
    "AGENT_COMPLETED:StrategyAgent": (55, "Strategy designed"),
    "AGENT_INVOKED:AnalysisCodeGenerator": (60, "Generating analysis code..."),
    "AGENT_COMPLETED:AnalysisCodeGenerator": (70, "Analysis code generated"),
    "VALIDATION_PASSED": (75, "Code validated"),
    "VALIDATION_FAILED": (65, "Validation failed, retrying..."),
    "PHASE2_COMPLETE": (85, "Assembling notebook..."),
    "EXPLORATORY_CONCLUSIONS_START": (88, "Generating conclusions..."),
    "EXPLORATORY_CONCLUSIONS_COMPLETE": (92, "Conclusions generated"),
}


class ProgressTracker:
    """Track job progress in Redis for real-time status updates."""

    REDIS_KEY_PREFIX = "job_progress"
    PHASE_KEY_PREFIX = "job_phases"
    TTL_SECONDS = 86400  # 24 hours

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"{self.REDIS_KEY_PREFIX}:{job_id}"

    def _phase_key(self, job_id: str) -> str:
        return f"{self.PHASE_KEY_PREFIX}:{job_id}"

    def set_progress(
        self, job_id: str, progress: int, message: str, phase: str = ""
    ) -> None:
        """Set job progress in Redis with timing data."""
        now = time.time()
        key = self._key(job_id)

        mapping: Dict[str, str] = {
            "progress": str(progress),
            "message": message,
            "phase": phase,
            "updated_at": str(now),
        }

        # Store job start time on first progress update
        if not self._redis.hexists(key, "started_at"):
            mapping["started_at"] = str(now)

        self._redis.hset(key, mapping=mapping)
        self._redis.expire(key, self.TTL_SECONDS)

        # Track per-phase timing
        if phase and phase not in ("done", "error"):
            phase_key = self._phase_key(job_id)
            if not self._redis.hexists(phase_key, f"{phase}_start"):
                self._redis.hset(phase_key, f"{phase}_start", str(now))
            self._redis.hset(phase_key, f"{phase}_latest", str(now))
            self._redis.expire(phase_key, self.TTL_SECONDS)

    def get_progress(self, job_id: str) -> Dict[str, str]:
        """Get job progress from Redis. Returns defaults if not found."""
        key = self._key(job_id)
        data = self._redis.hgetall(key)
        if not data:
            return {"progress": "0", "message": "Queued", "phase": ""}
        return data

    def get_progress_with_timing(self, job_id: str) -> Dict[str, Any]:
        """Return progress with elapsed time, ETA, and per-phase timings."""
        data = self.get_progress(job_id)
        progress = int(data.get("progress", "0"))

        now = time.time()
        started_at = float(data.get("started_at", "0"))
        elapsed = now - started_at if started_at > 0 else 0

        # Linear ETA: if X% done in Y seconds, total ~= Y / (X/100)
        eta_seconds = None
        if progress > 5 and progress < 100 and elapsed > 0:
            total_estimated = elapsed / (progress / 100.0)
            eta_seconds = round(max(0, total_estimated - elapsed), 1)

        # Per-phase timing
        phase_key = self._phase_key(job_id)
        phase_data = self._redis.hgetall(phase_key)

        phases: Dict[str, Dict[str, float]] = {}
        for k, v in phase_data.items():
            # Keys are like "phase1_start", "phase1_latest"
            parts = k.rsplit("_", 1)
            if len(parts) == 2:
                phase_name, metric = parts
                if phase_name not in phases:
                    phases[phase_name] = {}
                phases[phase_name][metric] = float(v)

        phase_timings = {}
        for pname, pdata in phases.items():
            start = pdata.get("start", 0)
            latest = pdata.get("latest", start)
            phase_timings[pname] = {"elapsed": round(latest - start, 1)}

        return {
            "progress": progress,
            "message": data.get("message", ""),
            "phase": data.get("phase", ""),
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": eta_seconds,
            "phase_timings": phase_timings,
        }

    def update_from_event(
        self, job_id: str, event: str, agent: Optional[str] = None
    ) -> None:
        """
        Update progress based on a structured log event.

        Looks up the event in the progress map and updates Redis
        only if the new progress is greater than the current progress
        (prevents backwards movement from retries).
        """
        # Build lookup key: agent-specific events use "EVENT:AgentName" format
        lookup_key = event
        if agent and event in ("AGENT_INVOKED", "AGENT_COMPLETED", "AGENT_FAILED"):
            lookup_key = f"{event}:{agent}"

        mapping = EVENT_PROGRESS_MAP.get(lookup_key)
        if not mapping:
            # Try the base event without agent suffix
            mapping = EVENT_PROGRESS_MAP.get(event)

        if not mapping:
            return  # Unknown event, skip

        new_progress, message = mapping

        # Only advance forward (don't regress on retries)
        current = self.get_progress(job_id)
        current_progress = int(current.get("progress", "0"))

        if new_progress > current_progress:
            phase = "phase1" if new_progress < 40 else "phase2"
            self.set_progress(job_id, new_progress, message, phase)

            # Audit log: persist to SQL (best-effort, see module docstring).
            self._persist_to_db(job_id, new_progress, message, phase)

    def _persist_to_db(
        self, job_id: str, progress: int, message: str, phase: str
    ) -> None:
        """Write progress to the JobProgress SQL table."""
        try:
            from src.server.db.database import SessionLocal
            from src.server.db.models import JobProgress

            with SessionLocal() as session:
                entry = JobProgress(
                    job_id=job_id,
                    phase=phase,
                    progress=progress,
                    message=message,
                )
                session.add(entry)
                session.commit()
        except Exception as exc:
            progress_logger.debug(f"Failed to persist progress to DB: {exc}")

    def mark_complete(self, job_id: str, success: bool = True) -> None:
        """Mark job as 100% complete or failed."""
        if success:
            self.set_progress(job_id, 100, "Analysis complete", "done")
        else:
            self.set_progress(job_id, -1, "Analysis failed", "error")
