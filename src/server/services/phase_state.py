"""Per-job phase + sub-step + agent state for the Command Center pipeline rail.

Maintained in Redis so it survives across worker processes and is queryable
by the SocketIOHandler (in the worker) and the metrics aggregator alike.

Top-level phases mirror the actual workflow:
  * phase1 = Data Understanding (Profiling / Codegen / Validate sub-steps)
  * extensions = optional pre-Phase-2 enrichment for forecasting/comparative/diagnostic
  * phase2 = Analysis & Modeling (Strategy / Codegen / Validate sub-steps)

Each agent name (e.g. "DataProfiler", "StrategyAgent") is bucketed into the
right (phase, sub_step) by ``_AGENT_LOCATION``. Unknown agents are bucketed
into the "other" sub-step of the closest phase so they still surface in the UI.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import redis

from src.utils.logger import get_logger

logger = get_logger()


# Agent → (phase_id, sub_step_id) attribution.
# Unknown agents land in ("phase1", "other") by default so nothing is dropped.
_AGENT_LOCATION: Dict[str, Tuple[str, str]] = {
    # Phase 1 — Data Understanding
    "DataProfiler": ("phase1", "profiling"),
    "ProfileCodeGenerator": ("phase1", "codegen"),
    "ProfileValidatorAgent": ("phase1", "validate"),
    "Orchestrator": ("phase1", "profiling"),
    "DataMerger": ("phase1", "profiling"),
    "SQLExtractionAgent": ("phase1", "profiling"),
    "APIExtractionAgent": ("phase1", "profiling"),
    # Extensions
    "ForecastingExtensionAgent": ("extensions", "extensions"),
    "ComparativeExtensionAgent": ("extensions", "extensions"),
    "DiagnosticExtensionAgent": ("extensions", "extensions"),
    # Phase 2 — Analysis & Modeling
    "StrategyAgent": ("phase2", "strategy"),
    "ForecastingStrategyAgent": ("phase2", "strategy"),
    "ComparativeStrategyAgent": ("phase2", "strategy"),
    "DiagnosticStrategyAgent": ("phase2", "strategy"),
    "SegmentationStrategyAgent": ("phase2", "strategy"),
    "DimensionalityStrategyAgent": ("phase2", "strategy"),
    "AnalysisCodeGenerator": ("phase2", "codegen"),
    "AnalysisValidator": ("phase2", "validate"),
    "ExploratoryConclusionsAgent": ("phase2", "validate"),
}


# Sub-step ordering per phase, used to render the rail consistently.
_PHASE_TEMPLATE: Dict[str, Dict[str, Any]] = {
    "phase1": {
        "name": "Phase 1: Data Understanding",
        "steps": [
            {"id": "profiling", "name": "Profiling"},
            {"id": "codegen", "name": "Code Generation"},
            {"id": "validate", "name": "Validation"},
        ],
    },
    "extensions": {
        "name": "Extensions",
        "steps": [
            {"id": "extensions", "name": "Mode-specific enrichment"},
        ],
    },
    "phase2": {
        "name": "Phase 2: Analysis & Modeling",
        "steps": [
            {"id": "strategy", "name": "Strategy"},
            {"id": "codegen", "name": "Code Generation"},
            {"id": "validate", "name": "Validation"},
        ],
    },
}


@dataclass
class _AgentState:
    name: str
    status: str = "queued"  # queued / running / done / failed
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class _SubStepState:
    id: str
    name: str
    status: str = "queued"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    agents: Dict[str, _AgentState] = field(default_factory=dict)


@dataclass
class _PhaseState:
    id: str
    name: str
    status: str = "queued"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    retries: int = 0
    steps: Dict[str, _SubStepState] = field(default_factory=dict)


def _new_phase_state() -> Dict[str, _PhaseState]:
    out: Dict[str, _PhaseState] = {}
    for pid, tmpl in _PHASE_TEMPLATE.items():
        steps = {s["id"]: _SubStepState(id=s["id"], name=s["name"]) for s in tmpl["steps"]}
        out[pid] = _PhaseState(id=pid, name=tmpl["name"], steps=steps)
    return out


class PhaseStateTracker:
    """Track and serialise per-job phase/sub-step/agent state.

    State is held in Redis as a JSON blob keyed by job_id. The blob is small
    (≈3 phases × ≈3 sub-steps × ≈5 agents) so re-serialising on every event
    is cheap.
    """

    REDIS_KEY_PREFIX = "job_phase_state"
    TTL_SECONDS = 86400  # 24h, matches ProgressTracker

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"{self.REDIS_KEY_PREFIX}:{job_id}"

    def _load(self, job_id: str) -> Dict[str, _PhaseState]:
        raw = self._redis.get(self._key(job_id))
        if not raw:
            return _new_phase_state()
        try:
            data = json.loads(raw)
            phases = _new_phase_state()
            for pid, p in data.items():
                if pid not in phases:
                    continue
                phases[pid].status = p.get("status", "queued")
                phases[pid].started_at = p.get("started_at")
                phases[pid].finished_at = p.get("finished_at")
                phases[pid].retries = p.get("retries", 0)
                for s in p.get("steps", []):
                    sid = s.get("id")
                    if sid in phases[pid].steps:
                        st = phases[pid].steps[sid]
                        st.status = s.get("status", "queued")
                        st.started_at = s.get("started_at")
                        st.finished_at = s.get("finished_at")
                        for a in s.get("agents", []):
                            st.agents[a["name"]] = _AgentState(
                                name=a["name"],
                                status=a.get("status", "queued"),
                                started_at=a.get("started_at"),
                                finished_at=a.get("finished_at"),
                            )
            return phases
        except Exception as e:
            logger.warning(f"PhaseStateTracker load failed for {job_id}: {e}")
            return _new_phase_state()

    def _store(self, job_id: str, phases: Dict[str, _PhaseState]) -> None:
        payload = self._serialize(phases)
        try:
            self._redis.set(self._key(job_id), json.dumps(payload), ex=self.TTL_SECONDS)
        except Exception as e:
            logger.debug(f"PhaseStateTracker store failed: {e}")

    @staticmethod
    def _serialize(phases: Dict[str, _PhaseState]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for pid, p in phases.items():
            out[pid] = {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "started_at": p.started_at,
                "finished_at": p.finished_at,
                "retries": p.retries,
                "steps": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status,
                        "started_at": s.started_at,
                        "finished_at": s.finished_at,
                        "agents": [
                            {
                                "name": a.name,
                                "status": a.status,
                                "started_at": a.started_at,
                                "finished_at": a.finished_at,
                            }
                            for a in s.agents.values()
                        ],
                    }
                    for s in p.steps.values()
                ],
            }
        return out

    def snapshot(self, job_id: str) -> List[Dict[str, Any]]:
        """Return the public-facing snapshot list for the WS payload."""
        phases = self._load(job_id)
        serial = self._serialize(phases)
        return list(serial.values())

    def update_from_event(
        self, job_id: str, event: str, agent: Optional[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """Mutate state for a single agent event. Returns the new snapshot
        if the state actually changed, or None for a no-op."""
        if not agent:
            return None
        loc = _AGENT_LOCATION.get(agent)
        if loc is None:
            return None
        phase_id, step_id = loc

        phases = self._load(job_id)
        phase = phases.get(phase_id)
        if not phase:
            return None
        step = phase.steps.get(step_id)
        if not step:
            return None

        agent_state = step.agents.get(agent) or _AgentState(name=agent)
        now = time.time()

        changed = False
        if event in ("AGENT_INVOKED", "AGENT_STARTED"):
            if agent_state.status != "running":
                agent_state.status = "running"
                agent_state.started_at = now
                agent_state.finished_at = None
                changed = True
            if step.status != "running":
                step.status = "running"
                step.started_at = step.started_at or now
                changed = True
            if phase.status != "running":
                phase.status = "running"
                phase.started_at = phase.started_at or now
                changed = True
        elif event == "AGENT_COMPLETED":
            if agent_state.status != "done":
                agent_state.status = "done"
                agent_state.finished_at = now
                changed = True
        elif event == "AGENT_FAILED":
            if agent_state.status != "failed":
                agent_state.status = "failed"
                agent_state.finished_at = now
                changed = True
            if step.status != "failed":
                step.status = "failed"
                changed = True

        # Update sub-step: if every agent registered to it is done, mark step done.
        if step.agents and all(a.status == "done" for a in step.agents.values()):
            if step.status != "done":
                step.status = "done"
                step.finished_at = now
                changed = True

        # Update phase: every sub-step done → phase done.
        if phase.steps and all(s.status == "done" for s in phase.steps.values()):
            if phase.status != "done":
                phase.status = "done"
                phase.finished_at = now
                changed = True

        step.agents[agent] = agent_state
        phase.steps[step_id] = step
        phases[phase_id] = phase

        if not changed:
            return None

        self._store(job_id, phases)
        return list(self._serialize(phases).values())

    def clear(self, job_id: str) -> None:
        try:
            self._redis.delete(self._key(job_id))
        except Exception:
            pass
