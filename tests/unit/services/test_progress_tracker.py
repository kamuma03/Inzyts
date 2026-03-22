"""
Unit tests for ProgressTracker service.

Tests the Redis-backed progress tracking, timing, ETA calculation,
and database persistence.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.server.services.progress_tracker import ProgressTracker, EVENT_PROGRESS_MAP


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with in-memory hash storage."""
    store = {}

    def hset(key, *args, mapping=None, **kwargs):
        if key not in store:
            store[key] = {}
        if mapping:
            store[key].update({k: str(v) for k, v in mapping.items()})
        elif len(args) >= 2:
            # Positional form: hset(key, field, value)
            store[key][str(args[0])] = str(args[1])

    def hgetall(key):
        return dict(store.get(key, {}))

    def hexists(key, field):
        return field in store.get(key, {})

    def expire(key, ttl):
        pass

    redis_mock = MagicMock()
    redis_mock.hset = MagicMock(side_effect=hset)
    redis_mock.hgetall = MagicMock(side_effect=hgetall)
    redis_mock.hexists = MagicMock(side_effect=hexists)
    redis_mock.expire = MagicMock(side_effect=expire)

    return redis_mock, store


@pytest.fixture
def tracker(mock_redis):
    """Create a ProgressTracker with mocked Redis."""
    redis_mock, _ = mock_redis
    with patch("src.server.services.progress_tracker.redis.Redis.from_url", return_value=redis_mock):
        t = ProgressTracker()
    return t


class TestEventProgressMap:
    """Tests for the event-to-progress mapping configuration."""

    def test_progress_values_monotonically_increase(self):
        """Key milestones should have increasing progress values."""
        ordered_events = [
            "MODE_DETECTED",
            "PHASE1_START",
            "PHASE1_COMPLETE",
            "PHASE2_START",
            "PHASE2_COMPLETE",
        ]
        prev = 0
        for event in ordered_events:
            progress, _ = EVENT_PROGRESS_MAP[event]
            assert progress > prev, f"{event} progress {progress} not > {prev}"
            prev = progress

    def test_all_mode_events_have_same_progress(self):
        """All MODE_* events should map to 5%."""
        for key in ["MODE_DETECTED", "MODE_EXPLICIT", "MODE_INFERRED", "MODE_DEFAULT"]:
            assert EVENT_PROGRESS_MAP[key][0] == 5

    def test_validation_failed_below_validation_passed(self):
        """VALIDATION_FAILED should have lower progress than VALIDATION_PASSED."""
        assert EVENT_PROGRESS_MAP["VALIDATION_FAILED"][0] < EVENT_PROGRESS_MAP["VALIDATION_PASSED"][0]


class TestProgressTracker:
    """Tests for ProgressTracker methods."""

    def test_get_progress_defaults_when_empty(self, tracker):
        """get_progress returns defaults for unknown job."""
        result = tracker.get_progress("unknown-job")
        assert result["progress"] == "0"
        assert result["message"] == "Queued"

    def test_set_progress_stores_values(self, tracker, mock_redis):
        _, store = mock_redis
        tracker.set_progress("job-1", 50, "Half done", "phase2")

        data = tracker.get_progress("job-1")
        assert data["progress"] == "50"
        assert data["message"] == "Half done"
        assert data["phase"] == "phase2"

    def test_set_progress_stores_started_at_on_first_call(self, tracker, mock_redis):
        _, store = mock_redis
        tracker.set_progress("job-1", 10, "Starting", "phase1")

        key = tracker._key("job-1")
        assert "started_at" in store.get(key, {})

    def test_set_progress_does_not_overwrite_started_at(self, tracker, mock_redis):
        _, store = mock_redis
        tracker.set_progress("job-1", 10, "Starting", "phase1")

        key = tracker._key("job-1")
        first_started = store[key]["started_at"]

        tracker.set_progress("job-1", 50, "Midway", "phase2")
        assert store[key]["started_at"] == first_started

    def test_set_progress_tracks_phase_timing(self, tracker, mock_redis):
        _, store = mock_redis
        tracker.set_progress("job-1", 10, "Profiling", "phase1")

        phase_key = tracker._phase_key("job-1")
        assert "phase1_start" in store.get(phase_key, {})
        assert "phase1_latest" in store.get(phase_key, {})

    def test_update_from_event_known_event(self, tracker):
        """Known event updates progress."""
        tracker.update_from_event("job-1", "PHASE1_START")
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == 10

    def test_update_from_event_agent_specific(self, tracker):
        """Agent-specific events use EVENT:AgentName lookup."""
        tracker.update_from_event("job-1", "AGENT_INVOKED", agent="DataProfiler")
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == 15
        assert "Profiling" in data["message"]

    def test_update_from_event_prevents_backward(self, tracker):
        """Progress should not go backward."""
        tracker.update_from_event("job-1", "PHASE1_COMPLETE")
        data1 = tracker.get_progress("job-1")
        assert int(data1["progress"]) == 38

        # PHASE1_START has lower progress (10) — should not regress
        tracker.update_from_event("job-1", "PHASE1_START")
        data2 = tracker.get_progress("job-1")
        assert int(data2["progress"]) == 38

    def test_update_from_event_unknown_event_is_noop(self, tracker):
        """Unknown events should be silently ignored."""
        tracker.update_from_event("job-1", "UNKNOWN_EVENT")
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == 0

    def test_update_from_event_fallback_to_base_event(self, tracker):
        """Agent events with unknown agent should fall back to base event if mapped."""
        tracker.update_from_event("job-1", "VALIDATION_PASSED", agent="SomeAgent")
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == 75

    @patch.object(ProgressTracker, "_persist_to_db")
    def test_update_from_event_persists_to_db(self, mock_persist, tracker):
        """update_from_event should call _persist_to_db when progress advances."""
        tracker.update_from_event("job-1", "PHASE1_START")
        mock_persist.assert_called_once_with("job-1", 10, "Starting data profiling...", "phase1")

    @patch.object(ProgressTracker, "_persist_to_db")
    def test_update_from_event_no_persist_on_no_advance(self, mock_persist, tracker):
        """No DB persistence when progress doesn't advance."""
        tracker.update_from_event("job-1", "PHASE1_COMPLETE")
        mock_persist.reset_mock()

        tracker.update_from_event("job-1", "PHASE1_START")
        mock_persist.assert_not_called()

    def test_mark_complete_success(self, tracker):
        tracker.mark_complete("job-1", success=True)
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == 100
        assert data["phase"] == "done"

    def test_mark_complete_failure(self, tracker):
        tracker.mark_complete("job-1", success=False)
        data = tracker.get_progress("job-1")
        assert int(data["progress"]) == -1
        assert data["phase"] == "error"

    def test_get_progress_with_timing_elapsed(self, tracker, mock_redis):
        """Timing data should include elapsed seconds."""
        _, store = mock_redis
        # Manually set started_at to simulate elapsed time
        key = tracker._key("job-1")
        store[key] = {
            "progress": "50",
            "message": "Midway",
            "phase": "phase2",
            "started_at": str(time.time() - 30),
            "updated_at": str(time.time()),
        }

        result = tracker.get_progress_with_timing("job-1")
        assert result["progress"] == 50
        assert result["elapsed_seconds"] >= 29  # allow some slack
        assert result["elapsed_seconds"] <= 32

    def test_get_progress_with_timing_eta(self, tracker, mock_redis):
        """ETA should be calculated via linear extrapolation."""
        _, store = mock_redis
        now = time.time()
        key = tracker._key("job-1")
        store[key] = {
            "progress": "50",
            "message": "Midway",
            "phase": "phase2",
            "started_at": str(now - 60),  # 60s elapsed at 50%
            "updated_at": str(now),
        }

        result = tracker.get_progress_with_timing("job-1")
        # At 50% in 60s, total estimated 120s, remaining ~60s
        assert result["eta_seconds"] is not None
        assert 55 <= result["eta_seconds"] <= 65

    def test_get_progress_with_timing_no_eta_when_too_early(self, tracker, mock_redis):
        """ETA should be None when progress <= 5%."""
        _, store = mock_redis
        key = tracker._key("job-1")
        store[key] = {
            "progress": "5",
            "message": "Starting",
            "phase": "phase1",
            "started_at": str(time.time() - 10),
            "updated_at": str(time.time()),
        }

        result = tracker.get_progress_with_timing("job-1")
        assert result["eta_seconds"] is None

    def test_get_progress_with_timing_phase_timings(self, tracker, mock_redis):
        """Phase timings should be returned from Redis phase keys."""
        _, store = mock_redis
        now = time.time()
        key = tracker._key("job-1")
        store[key] = {
            "progress": "50",
            "message": "Midway",
            "phase": "phase2",
            "started_at": str(now - 60),
            "updated_at": str(now),
        }
        phase_key = tracker._phase_key("job-1")
        store[phase_key] = {
            "phase1_start": str(now - 60),
            "phase1_latest": str(now - 30),
            "phase2_start": str(now - 30),
            "phase2_latest": str(now),
        }

        result = tracker.get_progress_with_timing("job-1")
        assert "phase1" in result["phase_timings"]
        assert "phase2" in result["phase_timings"]
        assert 28 <= result["phase_timings"]["phase1"]["elapsed"] <= 32
        assert 28 <= result["phase_timings"]["phase2"]["elapsed"] <= 32

    def test_persist_to_db_creates_job_progress_row(self, tracker):
        """_persist_to_db should insert a JobProgress row."""
        mock_session = MagicMock()
        with patch("src.server.db.database.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            tracker._persist_to_db("job-1", 50, "Midway", "phase2")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.job_id == "job-1"
        assert added.progress == 50

    def test_persist_to_db_handles_error_gracefully(self, tracker):
        """_persist_to_db should not raise even if DB write fails."""
        with patch("src.server.db.database.SessionLocal", side_effect=Exception("DB down")):
            # Should not raise
            tracker._persist_to_db("job-1", 50, "Midway", "phase2")
