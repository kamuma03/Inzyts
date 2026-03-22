"""
Unit tests for KernelSessionManager.

Tests the persistent kernel session management service
including session lifecycle, TTL expiry, and cleanup.
"""

import threading
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.services.kernel_session_manager import (
    KernelSession,
    KernelSessionManager,
    DEFAULT_TTL_SECONDS,
)


class TestKernelSession:
    """Test individual kernel session behavior."""

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_session_creation(self, mock_executor_class):
        """Test that a session can be created."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded 100 rows x 5 columns\ncol1    int64\ncol2    object"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.start()

        assert session._initialized is True
        assert "col1" in session.df_context
        mock_executor.execute_cell.assert_called_once()

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_session_execute(self, mock_executor_class):
        """Test code execution in a session."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "hello"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.executor = mock_executor
        session.executor.kc = MagicMock()  # kernel client present

        result = session.execute("print('hello')")
        assert result.success is True

    def test_session_is_expired_false(self):
        """Test that a fresh session is not expired."""
        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        assert session.is_expired() is False

    def test_session_is_expired_true(self):
        """Test that an old session is expired."""
        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.last_activity = time.time() - (DEFAULT_TTL_SECONDS + 1)
        assert session.is_expired() is True

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_session_shutdown(self, mock_executor_class):
        """Test session shutdown."""
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.executor = mock_executor

        session.shutdown()

        mock_executor.shutdown.assert_called_once()
        assert session.executor is None


class TestKernelSessionManager:
    """Test the manager singleton and session operations."""

    def setup_method(self):
        """Reset the singleton for each test."""
        # Reset the singleton state
        KernelSessionManager._instance = None
        # Create a fresh manager and use an RLock so that get_or_create_session
        # (which calls cleanup_expired while already holding the lock) doesn't deadlock.
        mgr = KernelSessionManager()
        mgr._session_lock = threading.RLock()
        # Prevent the cleanup daemon thread from starting during tests.
        mgr._running = True

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_get_or_create_session(self, mock_executor_class):
        """Test creating a new session."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded 100 rows"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        session = manager.get_or_create_session("job-1", "/data/test.csv")

        assert session is not None
        assert session.job_id == "job-1"
        assert manager.active_session_count() == 1

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_get_existing_session(self, mock_executor_class):
        """Test retrieving an existing session."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded 100 rows"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        session1 = manager.get_or_create_session("job-1", "/data/test.csv")
        session2 = manager.get_or_create_session("job-1", "/data/test.csv")

        assert session1 is session2  # Same session reused

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_get_session_nonexistent(self, mock_executor_class):
        """Test getting a session that doesn't exist."""
        manager = KernelSessionManager()
        session = manager.get_session("nonexistent-job")

        assert session is None

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_close_session(self, mock_executor_class):
        """Test closing a specific session."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        manager.get_or_create_session("job-1", "/data/test.csv")
        assert manager.active_session_count() == 1

        manager.close_session("job-1")
        assert manager.active_session_count() == 0

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_cleanup_expired(self, mock_executor_class):
        """Test cleanup of expired sessions."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        session = manager.get_or_create_session("expired-job", "/data/test.csv")
        session.last_activity = time.time() - (DEFAULT_TTL_SECONDS + 100)

        manager.cleanup_expired()
        assert manager.active_session_count() == 0

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_shutdown_all(self, mock_executor_class):
        """Test shutting down all sessions."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        manager.get_or_create_session("job-1", "/data/test1.csv")
        manager.get_or_create_session("job-2", "/data/test2.csv")

        assert manager.active_session_count() == 2

        manager.shutdown_all()
        assert manager.active_session_count() == 0

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_get_context(self, mock_executor_class):
        """Test getting dataframe context from a session."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Loaded 100 rows x 3 columns\nage      int64\nname    object\nsalary  float64"
        mock_executor.execute_cell.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        manager = KernelSessionManager()
        manager.get_or_create_session("ctx-job", "/data/test.csv")

        context = manager.get_context("ctx-job")
        assert "age" in context
        assert "int64" in context

    def test_get_context_nonexistent(self):
        """Test getting context for nonexistent session returns empty."""
        manager = KernelSessionManager()
        context = manager.get_context("ghost-job")
        assert context == ""


class TestKernelSessionIntrospect:
    """Test the kernel session introspect method."""

    def setup_method(self):
        KernelSessionManager._instance = None
        mgr = KernelSessionManager()
        mgr._session_lock = threading.RLock()
        mgr._running = True

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_introspect_returns_context(self, mock_executor_class):
        """Test that introspect returns variable info from the kernel."""
        mock_executor = MagicMock()
        mock_executor.kc = MagicMock()  # kernel client present

        # Mock introspection execution
        mock_introspect_result = MagicMock()
        mock_introspect_result.success = True
        mock_introspect_result.output = "df: DataFrame shape=(100, 5)\nmodel: RandomForestClassifier"
        mock_executor.execute_cell.return_value = mock_introspect_result
        mock_executor_class.return_value = mock_executor

        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.executor = mock_executor

        context = session.introspect()
        assert "DataFrame" in context
        assert "RandomForest" in context

    @patch('src.services.kernel_session_manager.SandboxExecutor')
    def test_introspect_fallback_on_failure(self, mock_executor_class):
        """Test that introspect falls back to df_context on failure."""
        mock_executor = MagicMock()
        mock_executor.kc = MagicMock()
        mock_executor.execute_cell.side_effect = Exception("Kernel crash")
        mock_executor_class.return_value = mock_executor

        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.executor = mock_executor
        session.df_context = "col1: int64"

        context = session.introspect()
        assert context == "col1: int64"

    def test_introspect_no_executor(self):
        """Test that introspect returns df_context when no executor."""
        session = KernelSession(job_id="test-job", csv_path="/data/test.csv")
        session.executor = None
        session.df_context = "col1: float64"

        context = session.introspect()
        assert context == "col1: float64"

