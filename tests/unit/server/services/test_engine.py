import logging
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.server.services.engine import execution_task, SocketIOHandler

@patch("src.server.services.engine.run_analysis")
@patch("src.server.services.engine.SessionLocal")
@patch("src.server.services.engine.setup_job_logging")
def test_execution_task_success(mock_setup_logging, mock_session_local, mock_run_analysis):
    # Mock the DB session
    mock_db = MagicMock()
    # It takes synchronous DB since engine is using SessionLocal
    mock_session_local.return_value.__enter__.return_value = mock_db

    # Mock the Job record
    mock_job = MagicMock()
    mock_db.get.return_value = mock_job

    # Mock AnalysisState result
    mock_final_state = MagicMock()
    mock_final_state.total_tokens_used = 100
    mock_final_state.final_notebook_path = "output.ipynb"
    mock_run_analysis.return_value = mock_final_state

    # Call execution_task synchronously
    execution_task(
        job_id="job-123",
        csv_path="/data/test.csv",
        mode="exploratory"
    )

    assert mock_job.status == "completed"
    assert mock_job.result_path == "output.ipynb"
    mock_run_analysis.assert_called_once()
    assert mock_db.commit.call_count >= 1

@patch("src.server.services.engine.setup_job_logging")
@patch("src.server.services.engine.SessionLocal")
def test_execution_task_job_not_found(mock_session_local, mock_setup_logging):
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    # Return None for the job
    mock_db.get.return_value = None

    # execution_task should safely return immediately if job doesn't exist
    result = execution_task(
        job_id="job-999",
        csv_path="/data/test.csv",
        mode="exploratory"
    )
    assert result is None

@patch("src.server.services.engine.setup_job_logging")
@patch("src.server.services.engine.run_analysis")
@patch("src.server.services.engine.SessionLocal")
def test_execution_task_failure(mock_session_local, mock_run_analysis, mock_setup_logging):
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    mock_job = MagicMock()
    mock_db.get.return_value = mock_job

    mock_run_analysis.side_effect = Exception("Graph run error")

    execution_task(
        job_id="job-error",
        csv_path="/data/test.csv",
        mode="exploratory"
    )

    assert mock_job.status == "failed"
    assert "Graph run error" in mock_job.error_message
    assert mock_db.commit.call_count >= 1


@patch("src.server.services.engine.run_analysis")
@patch("src.server.services.engine.SessionLocal")
@patch("src.server.services.engine.setup_job_logging")
def test_execution_task_threads_api_params(mock_setup_logging, mock_session_local, mock_run_analysis):
    """Verify that api_url, api_headers, api_auth, json_path are passed to run_analysis."""
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    mock_job = MagicMock()
    mock_db.get.return_value = mock_job

    mock_final_state = MagicMock()
    mock_final_state.total_tokens_used = 50
    mock_final_state.prompt_tokens_used = 0
    mock_final_state.completion_tokens_used = 0
    mock_final_state.final_notebook_path = "output.ipynb"
    mock_run_analysis.return_value = mock_final_state

    execution_task(
        job_id="job-api",
        csv_path=None,
        mode="exploratory",
        api_url="https://api.example.com/data",
        api_headers={"X-Custom": "val"},
        api_auth={"type": "bearer", "token": "tok"},
        json_path="data.items",
    )

    mock_run_analysis.assert_called_once()
    call_kwargs = mock_run_analysis.call_args[1]
    assert call_kwargs["api_url"] == "https://api.example.com/data"
    assert call_kwargs["api_headers"] == {"X-Custom": "val"}
    assert call_kwargs["api_auth"] == {"type": "bearer", "token": "tok"}
    assert call_kwargs["json_path"] == "data.items"


class TestSocketIOHandler:
    """Tests for SocketIOHandler with ProgressTracker integration."""

    @patch("src.server.services.progress_tracker.ProgressTracker")
    @patch("src.server.utils.socket_emitter.get_socket_manager")
    def test_handler_instantiates_tracker(self, mock_get_mgr, mock_tracker_cls):
        handler = SocketIOHandler("job-1")
        mock_tracker_cls.assert_called_once()
        assert handler._tracker is not None

    @patch("src.server.services.progress_tracker.ProgressTracker", side_effect=Exception("Redis down"))
    @patch("src.server.utils.socket_emitter.get_socket_manager")
    def test_handler_survives_tracker_init_failure(self, mock_get_mgr, mock_tracker_cls):
        handler = SocketIOHandler("job-1")
        assert handler._tracker is None

    @patch("src.server.services.progress_tracker.ProgressTracker")
    @patch("src.server.utils.socket_emitter.get_socket_manager")
    def test_emit_with_event_attr_sends_agent_event(self, mock_get_mgr, mock_tracker_cls):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        handler = SocketIOHandler("job-1")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="[PHASE1_START] Starting", args=None, exc_info=None,
        )
        record.event = "PHASE1_START"
        record.phase = "phase1"

        handler.emit(record)

        # Should emit agent_event
        agent_calls = [c for c in mock_mgr.emit.call_args_list if c[0][0] == "agent_event"]
        assert len(agent_calls) == 1
        payload = agent_calls[0][0][1]
        assert payload["event"] == "PHASE1_START"
        assert payload["phase"] == "phase1"

    @patch("src.server.services.progress_tracker.ProgressTracker")
    @patch("src.server.utils.socket_emitter.get_socket_manager")
    def test_emit_with_event_attr_updates_tracker_and_emits_progress(self, mock_get_mgr, mock_tracker_cls):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        mock_tracker = MagicMock()
        mock_tracker.get_progress_with_timing.return_value = {
            "progress": 10,
            "message": "Starting",
            "phase": "phase1",
            "elapsed_seconds": 5.0,
            "eta_seconds": 45.0,
            "phase_timings": {"phase1": {"elapsed": 5.0}},
        }
        mock_tracker_cls.return_value = mock_tracker

        handler = SocketIOHandler("job-1")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="[PHASE1_START] Starting", args=None, exc_info=None,
        )
        record.event = "PHASE1_START"

        handler.emit(record)

        mock_tracker.update_from_event.assert_called_once_with("job-1", "PHASE1_START", None)

        progress_calls = [c for c in mock_mgr.emit.call_args_list if c[0][0] == "progress"]
        assert len(progress_calls) == 1
        payload = progress_calls[0][0][1]
        assert payload["progress"] == 10
        assert payload["eta_seconds"] == 45.0

    @patch("src.server.services.progress_tracker.ProgressTracker")
    @patch("src.server.utils.socket_emitter.get_socket_manager")
    def test_emit_without_event_attr_skips_tracker(self, mock_get_mgr, mock_tracker_cls):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr
        mock_tracker = MagicMock()
        mock_tracker_cls.return_value = mock_tracker

        handler = SocketIOHandler("job-1")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Regular log message", args=None, exc_info=None,
        )

        handler.emit(record)

        mock_tracker.update_from_event.assert_not_called()
        # Should only emit 'log', no 'agent_event' or 'progress'
        event_names = [c[0][0] for c in mock_mgr.emit.call_args_list]
        assert "agent_event" not in event_names
        assert "progress" not in event_names
        assert "log" in event_names


@patch("src.server.services.progress_tracker.ProgressTracker")
@patch("src.server.services.engine.run_analysis")
@patch("src.server.services.engine.SessionLocal")
@patch("src.server.services.engine.setup_job_logging")
def test_execution_task_marks_progress_complete_on_success(
    mock_setup_logging, mock_session_local, mock_run_analysis, mock_tracker_cls
):
    """execution_task should call tracker.mark_complete(success=True) on completion."""
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    mock_job = MagicMock()
    mock_job.status = "completed"
    mock_db.get.return_value = mock_job

    mock_final_state = MagicMock()
    mock_final_state.total_tokens_used = 100
    mock_final_state.final_notebook_path = "output.ipynb"
    mock_run_analysis.return_value = mock_final_state

    mock_tracker = MagicMock()
    mock_tracker_cls.return_value = mock_tracker

    execution_task(job_id="job-ok", csv_path="/data/test.csv", mode="exploratory")

    mock_tracker.mark_complete.assert_called_once()
    call_kwargs = mock_tracker.mark_complete.call_args
    assert call_kwargs[1]["success"] is True or call_kwargs[0][1] is True


@patch("src.server.services.progress_tracker.ProgressTracker")
@patch("src.server.services.engine.run_analysis")
@patch("src.server.services.engine.SessionLocal")
@patch("src.server.services.engine.setup_job_logging")
def test_execution_task_marks_progress_failed_on_error(
    mock_setup_logging, mock_session_local, mock_run_analysis, mock_tracker_cls
):
    """execution_task should call tracker.mark_complete(success=False) on failure."""
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    mock_job = MagicMock()
    mock_db.get.return_value = mock_job

    mock_run_analysis.side_effect = Exception("Boom")

    mock_tracker = MagicMock()
    mock_tracker_cls.return_value = mock_tracker

    execution_task(job_id="job-err", csv_path="/data/test.csv", mode="exploratory")

    mock_tracker.mark_complete.assert_called_once()
