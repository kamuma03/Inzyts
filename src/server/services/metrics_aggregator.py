"""Per-job background thread that emits ``metrics_snapshot`` every 500 ms.

Architectural choice locked in plan §A13: a steady-cadence background task
(daemon thread) over event-driven emission. The Command Center top strip
re-renders on each tick, so the user sees elapsed/eta/cost advance smoothly
even when no agent event has fired in a while.

The aggregator reads from sources that are already populated during a run:
  * ``ProgressTracker`` (Redis) — progress %, elapsed, ETA, phase
  * ``AgentFactory`` agents — running token totals (singleton per worker process)
  * ``find_previous_job`` — one-shot lookup at start; cached for the run

It is **fire-and-forget**: failures never propagate to the workflow, and the
thread is a daemon so a worker shutdown doesn't hang on it.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger()

# Total agents in the pipeline. Verified at import time against AgentFactory's
# registered map so the number never drifts out of sync with reality.
_FALLBACK_AGENTS_TOTAL = 22


def _count_registered_agents() -> int:
    try:
        from src.workflow.agent_factory import AgentFactory
        registry = getattr(AgentFactory, "_AGENT_MAP", None) or getattr(AgentFactory, "_REGISTRY", None)
        if isinstance(registry, dict) and registry:
            return len(registry)
    except Exception:
        pass
    return _FALLBACK_AGENTS_TOTAL


def _running_token_totals() -> Dict[str, int]:
    """Sum llm_agent.* counters across all instantiated agents in this worker."""
    try:
        from src.workflow.agent_factory import AgentFactory
        cache = getattr(AgentFactory, "_INSTANCE_CACHE", None) or {}
        total = prompt = completion = 0
        for agent in cache.values():
            llm = getattr(agent, "llm_agent", None)
            if llm is None:
                continue
            total += int(getattr(llm, "total_tokens", 0) or 0)
            prompt += int(getattr(llm, "prompt_tokens", 0) or 0)
            completion += int(getattr(llm, "completion_tokens", 0) or 0)
        return {"total": total, "prompt": prompt, "completion": completion}
    except Exception:
        return {"total": 0, "prompt": 0, "completion": 0}


class MetricsAggregator:
    """Daemon thread that emits ``metrics_snapshot`` every ~500ms while running.

    Lifecycle: ``start()`` spawns the thread, ``stop()`` signals it to exit.
    The thread is daemon so a hard worker shutdown never blocks on it.
    """

    INTERVAL_SECONDS = 0.5

    def __init__(
        self,
        job_id: str,
        *,
        previous_job_id: Optional[str] = None,
        previous_metrics: Optional[Dict[str, Any]] = None,
    ):
        self.job_id = job_id
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._previous_job_id = previous_job_id
        self._previous_metrics = previous_metrics or None
        self._agents_total = _count_registered_agents()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name=f"metrics-{self.job_id}", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    # ------------------------------------------------------------------
    # internal

    def _run(self) -> None:
        try:
            from src.server.services.progress_tracker import ProgressTracker
            from src.server.services.cost_estimator import calculate_cost
            from src.server.utils.socket_emitter import get_socket_manager
            from src.config import settings

            mgr = get_socket_manager()
            tracker = ProgressTracker()

            provider = settings.llm.default_provider
            if provider == "anthropic":
                model_name = settings.llm.anthropic_model or "claude-sonnet-4"
            elif provider == "openai":
                model_name = settings.llm.openai_model or "gpt-4o"
            elif provider == "gemini":
                model_name = settings.llm.gemini_model or "gemini-1.5-pro"
            else:
                model_name = "gpt-4o"
        except Exception as e:
            logger.debug(f"MetricsAggregator: setup failed: {e}")
            return

        while not self._stop.is_set():
            try:
                progress = tracker.get_progress_with_timing(self.job_id)
                tokens = _running_token_totals()
                cost = calculate_cost(tokens["prompt"], tokens["completion"], model_name)

                payload = {
                    "job_id": self.job_id,
                    "elapsed_seconds": progress.get("elapsed_seconds") or 0,
                    "eta_seconds": progress.get("eta_seconds"),
                    "tokens_used": tokens["total"],
                    "prompt_tokens": tokens["prompt"],
                    "completion_tokens": tokens["completion"],
                    "cost_usd": round(cost, 6),
                    "quality_score": None,
                    "agents_active": 1 if progress.get("phase") in ("phase1", "phase2", "extensions") else 0,
                    "agents_total": self._agents_total,
                    "previous_job_id": self._previous_job_id,
                    "previous": self._previous_metrics,
                }
                mgr.emit("metrics_snapshot", payload, room=self.job_id)
            except Exception as e:
                logger.debug(f"MetricsAggregator tick failed for {self.job_id}: {e}")

            # Wait but be responsive to stop()
            self._stop.wait(self.INTERVAL_SECONDS)
