"""Unit tests for the Command Center phase-state tracker."""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.server.services.phase_state import PhaseStateTracker


@pytest.fixture
def mock_redis():
    """In-memory Redis stub that supports get/set/delete."""
    store: Dict[str, str] = {}

    def get(key):
        return store.get(key)

    def setm(key, value, ex=None):
        store[key] = value

    def delete(key):
        store.pop(key, None)

    redis_mock = MagicMock()
    redis_mock.get.side_effect = get
    redis_mock.set.side_effect = setm
    redis_mock.delete.side_effect = delete
    return redis_mock


@pytest.fixture
def tracker(mock_redis):
    with patch("redis.Redis.from_url", return_value=mock_redis):
        yield PhaseStateTracker()


def test_initial_snapshot_has_three_phases(tracker):
    snapshot = tracker.snapshot("job-1")
    ids = [p["id"] for p in snapshot]
    assert ids == ["phase1", "extensions", "phase2"]
    assert all(p["status"] == "queued" for p in snapshot)


def test_unknown_agent_is_a_noop(tracker):
    result = tracker.update_from_event("job-1", "AGENT_INVOKED", "TotallyMadeUp")
    assert result is None
    snapshot = tracker.snapshot("job-1")
    # Still all queued.
    assert all(p["status"] == "queued" for p in snapshot)


def test_data_profiler_invoked_marks_phase1_running(tracker):
    snapshot = tracker.update_from_event("job-1", "AGENT_INVOKED", "DataProfiler")
    assert snapshot is not None
    phase1 = next(p for p in snapshot if p["id"] == "phase1")
    assert phase1["status"] == "running"
    profiling = next(s for s in phase1["steps"] if s["id"] == "profiling")
    assert profiling["status"] == "running"
    agent = next(a for a in profiling["agents"] if a["name"] == "DataProfiler")
    assert agent["status"] == "running"
    assert agent["started_at"] is not None


def test_completed_event_marks_step_done_when_only_agent(tracker):
    tracker.update_from_event("job-1", "AGENT_INVOKED", "DataProfiler")
    snapshot = tracker.update_from_event("job-1", "AGENT_COMPLETED", "DataProfiler")
    assert snapshot is not None
    phase1 = next(p for p in snapshot if p["id"] == "phase1")
    profiling = next(s for s in phase1["steps"] if s["id"] == "profiling")
    assert profiling["status"] == "done"


def test_failed_event_marks_step_failed(tracker):
    tracker.update_from_event("job-1", "AGENT_INVOKED", "AnalysisCodeGenerator")
    snapshot = tracker.update_from_event("job-1", "AGENT_FAILED", "AnalysisCodeGenerator")
    assert snapshot is not None
    phase2 = next(p for p in snapshot if p["id"] == "phase2")
    codegen = next(s for s in phase2["steps"] if s["id"] == "codegen")
    assert codegen["status"] == "failed"


def test_extensions_bucket_is_isolated(tracker):
    snapshot = tracker.update_from_event("job-1", "AGENT_INVOKED", "ForecastingExtensionAgent")
    assert snapshot is not None
    ext = next(p for p in snapshot if p["id"] == "extensions")
    assert ext["status"] == "running"
    phase1 = next(p for p in snapshot if p["id"] == "phase1")
    assert phase1["status"] == "queued"


def test_no_change_returns_none(tracker):
    tracker.update_from_event("job-1", "AGENT_INVOKED", "DataProfiler")
    second = tracker.update_from_event("job-1", "AGENT_INVOKED", "DataProfiler")
    assert second is None  # already running, no state change


def test_clear_resets_state(tracker):
    tracker.update_from_event("job-1", "AGENT_INVOKED", "DataProfiler")
    tracker.clear("job-1")
    snapshot = tracker.snapshot("job-1")
    assert all(p["status"] == "queued" for p in snapshot)
