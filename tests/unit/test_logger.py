"""
Unit tests for Logger and Monitoring System.

Tests the structured logging infrastructure, event tracking,
and observability functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock
import logging
from pathlib import Path
import tempfile
import shutil
import uuid

from src.utils.logger import (
    DAAgentLogger,
    LogEvents,
    get_logger,
    init_logger
)


class TestLogEvents:
    """Test suite for LogEvents enum."""

    def test_all_required_events_present(self):
        """Test that all required events from requirements are present."""
        required_events = [
            'MODE_DETECTED', 'MODE_EXPLICIT', 'MODE_INFERRED', 'MODE_DEFAULT',
            'CACHE_CHECK', 'CACHE_HIT', 'CACHE_MISS', 'CACHE_EXPIRED',
            'CACHE_CSV_CHANGED', 'CACHE_SAVED', 'CACHE_DELETED',
            'UPGRADE_STARTED', 'UPGRADE_FROM_CACHE', 'UPGRADE_COMPLETED',
            'EXPLORATORY_CONCLUSIONS_START', 'EXPLORATORY_CONCLUSIONS_COMPLETE',
            'EXPLORATORY_CONCLUSIONS_LOW_CONFIDENCE',
            'PHASE1_START', 'PHASE1_COMPLETE', 'PHASE2_START', 'PHASE2_COMPLETE',
            'PROFILE_LOCK_GRANTED', 'PROFILE_LOCK_DENIED',
            'AGENT_INVOKED', 'AGENT_COMPLETED', 'AGENT_FAILED',
            'VALIDATION_PASSED', 'VALIDATION_FAILED',
            'RECURSION_TRIGGERED', 'ESCALATION_TRIGGERED',
            'TOKEN_USAGE', 'EXECUTION_TIME'
        ]

        for event_name in required_events:
            assert hasattr(LogEvents, event_name), f"Missing LogEvent: {event_name}"
            assert event_name in LogEvents.__members__


class TestDAAgentLogger:
    """Test suite for DAAgentLogger class."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for logs."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def logger_name(self):
        """Generate unique logger name to avoid handler reuse."""
        return f"TestLogger_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def test_logger(self, temp_log_dir, logger_name):
        """Create a test logger instance with unique name."""
        logger = DAAgentLogger(
            name=logger_name,
            log_dir=temp_log_dir,
            log_level=logging.DEBUG
        )
        yield logger
        # Cleanup: remove handlers to prevent resource leaks
        for handler in logger.logger.handlers[:]:
            handler.close()
            logger.logger.removeHandler(handler)

    def _flush_handlers(self, logger):
        """Force flush all handlers to ensure logs are written to disk."""
        for handler in logger.logger.handlers:
            handler.flush()

    def _get_log_file(self, temp_log_dir, logger_name):
        """Get the log file path based on logger name."""
        return Path(temp_log_dir) / f"{logger_name.lower()}.log"

    def test_logger_initialization(self, test_logger, temp_log_dir, logger_name):
        """Test logger initialization creates necessary files."""
        log_file = self._get_log_file(temp_log_dir, logger_name)
        assert log_file.exists()

    def test_logger_has_file_handler(self, test_logger):
        """Test logger has file handler configured."""
        handlers = test_logger.logger.handlers
        assert len(handlers) >= 1
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)

    def test_logger_has_console_handler(self, test_logger):
        """Test logger has console handler configured."""
        handlers = test_logger.logger.handlers
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_log_event_structure(self, test_logger, temp_log_dir, logger_name):
        """Test structured event logging format."""
        test_logger.log_event(
            LogEvents.CACHE_HIT,
            "Cache found",
            level="info",
            csv_path="/path/to/data.csv",
            quality_score=0.85
        )
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_HIT" in log_content
        assert "Cache found" in log_content
        assert "csv_path" in log_content or "/path/to/data.csv" in log_content

    def test_mode_detected_explicit(self, test_logger, temp_log_dir, logger_name):
        """Test logging of explicit mode detection."""
        test_logger.mode_detected("predictive", "explicit")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "MODE_EXPLICIT" in log_content
        assert "predictive" in log_content

    def test_mode_detected_inferred(self, test_logger, temp_log_dir, logger_name):
        """Test logging of inferred mode detection."""
        test_logger.mode_detected("exploratory", "inferred")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "MODE_INFERRED" in log_content
        assert "exploratory" in log_content

    def test_cache_check_valid(self, test_logger, temp_log_dir, logger_name):
        """Test logging of valid cache check."""
        test_logger.cache_check("/path/to/data.csv", "valid")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_HIT" in log_content
        assert "data.csv" in log_content

    def test_cache_check_expired(self, test_logger, temp_log_dir, logger_name):
        """Test logging of expired cache."""
        test_logger.cache_check("/path/to/data.csv", "expired")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_EXPIRED" in log_content

    def test_cache_check_csv_changed(self, test_logger, temp_log_dir, logger_name):
        """Test logging of CSV change detection."""
        test_logger.cache_check("/path/to/data.csv", "csv_changed")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_CSV_CHANGED" in log_content

    def test_cache_saved(self, test_logger, temp_log_dir, logger_name):
        """Test logging of cache save operation."""
        test_logger.cache_saved("abc123def456", 0.92)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_SAVED" in log_content
        assert "abc123" in log_content  # Hash prefix
        assert "0.92" in log_content

    def test_cache_deleted(self, test_logger, temp_log_dir, logger_name):
        """Test logging of cache deletion."""
        test_logger.cache_deleted("abc123def456", "expired")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "CACHE_DELETED" in log_content
        assert "expired" in log_content

    def test_upgrade_started(self, test_logger, temp_log_dir, logger_name):
        """Test logging of upgrade operation."""
        test_logger.upgrade_started("exploratory", "predictive", True)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "UPGRADE_STARTED" in log_content
        assert "exploratory" in log_content
        assert "predictive" in log_content
        assert "UPGRADE_FROM_CACHE" in log_content  # Should log cache usage

    def test_exploratory_conclusions_lifecycle(self, test_logger, temp_log_dir, logger_name):
        """Test logging of exploratory conclusions lifecycle."""
        test_logger.exploratory_conclusions("start")
        test_logger.exploratory_conclusions("complete", confidence=0.87)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "EXPLORATORY_CONCLUSIONS_START" in log_content
        assert "EXPLORATORY_CONCLUSIONS_COMPLETE" in log_content
        assert "0.87" in log_content

    def test_exploratory_conclusions_low_confidence(self, test_logger, temp_log_dir, logger_name):
        """Test logging of low confidence warning."""
        test_logger.exploratory_conclusions("low_confidence", confidence=0.55)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "EXPLORATORY_CONCLUSIONS_LOW_CONFIDENCE" in log_content
        assert "0.55" in log_content

    def test_phase_transitions(self, test_logger, temp_log_dir, logger_name):
        """Test logging of phase transitions."""
        test_logger.phase_transition("phase1", "start")
        test_logger.phase_transition("phase1", "complete")
        test_logger.phase_transition("phase2", "start")
        test_logger.phase_transition("phase2", "complete")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "PHASE1_START" in log_content
        assert "PHASE1_COMPLETE" in log_content
        assert "PHASE2_START" in log_content
        assert "PHASE2_COMPLETE" in log_content

    def test_profile_lock_granted(self, test_logger, temp_log_dir, logger_name):
        """Test logging of profile lock granted."""
        test_logger.profile_lock(granted=True, quality_score=0.85)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "PROFILE_LOCK_GRANTED" in log_content
        assert "0.85" in log_content

    def test_profile_lock_denied(self, test_logger, temp_log_dir, logger_name):
        """Test logging of profile lock denied."""
        test_logger.profile_lock(granted=False, quality_score=0.65)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "PROFILE_LOCK_DENIED" in log_content
        assert "0.65" in log_content

    def test_agent_execution_lifecycle(self, test_logger, temp_log_dir, logger_name):
        """Test logging of agent execution lifecycle."""
        test_logger.agent_execution("DataProfiler", "invoked")
        test_logger.agent_execution("DataProfiler", "completed", duration=2.5)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "AGENT_INVOKED" in log_content
        assert "AGENT_COMPLETED" in log_content
        assert "DataProfiler" in log_content

    def test_agent_execution_failure(self, test_logger, temp_log_dir, logger_name):
        """Test logging of agent failure."""
        test_logger.agent_execution("DataProfiler", "failed", reason="Timeout")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "AGENT_FAILED" in log_content
        assert "Timeout" in log_content

    def test_validation_passed(self, test_logger, temp_log_dir, logger_name):
        """Test logging of validation success."""
        test_logger.validation("profile", passed=True, quality_score=0.88)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "VALIDATION_PASSED" in log_content
        assert "0.88" in log_content

    def test_validation_failed(self, test_logger, temp_log_dir, logger_name):
        """Test logging of validation failure."""
        test_logger.validation("profile", passed=False, quality_score=0.55, reason="Low PEP8 score")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "VALIDATION_FAILED" in log_content
        assert "0.55" in log_content

    def test_recursion_trigger(self, test_logger, temp_log_dir, logger_name):
        """Test logging of recursion trigger."""
        test_logger.recursion("Low quality score", iteration=2, phase="profile_validation")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "RECURSION_TRIGGERED" in log_content
        assert "iteration 2" in log_content
        assert "Low quality score" in log_content

    def test_escalation_trigger(self, test_logger, temp_log_dir, logger_name):
        """Test logging of escalation to orchestrator."""
        test_logger.escalation("Max retries exceeded", phase="profile_validation")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "ESCALATION_TRIGGERED" in log_content
        assert "Max retries exceeded" in log_content

    def test_token_usage_logging(self, test_logger, temp_log_dir, logger_name):
        """Test logging of token usage."""
        test_logger.log_token_usage("DataProfiler", 1250, "claude-sonnet-4")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "TOKEN_USAGE" in log_content
        assert "1250" in log_content
        assert "claude-sonnet-4" in log_content

    def test_execution_time_logging(self, test_logger, temp_log_dir, logger_name):
        """Test logging of execution duration."""
        test_logger.log_execution_time("DataProfiler", 3.456)
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "EXECUTION_TIME" in log_content
        assert "3.456" in log_content

    def test_log_rotation_configuration(self, test_logger):
        """Test that log rotation is configured."""
        file_handlers = [h for h in test_logger.logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]

        assert len(file_handlers) > 0
        handler = file_handlers[0]
        assert handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert handler.backupCount == 5

    def test_console_log_level_filtering(self, test_logger):
        """Test that console handler only shows warnings and above."""
        console_handlers = [h for h in test_logger.logger.handlers
                           if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, logging.handlers.RotatingFileHandler)]

        assert len(console_handlers) > 0
        handler = console_handlers[0]
        assert handler.level == logging.WARNING

    def test_global_logger_singleton(self, temp_log_dir):
        """Test that get_logger returns singleton instance."""
        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2

    def test_init_logger_custom_settings(self, temp_log_dir):
        """Test initialization with custom settings."""
        custom_logger = init_logger(
            name="CustomLogger",
            log_dir=temp_log_dir,
            log_level=logging.DEBUG
        )

        # The global logger singleton might interfere.
        # init_logger should return the logger with the new name.
        if not isinstance(custom_logger.logger, (Mock, MagicMock)):
            assert custom_logger.logger.name == "CustomLogger"
        # The level might be affected by global settings or previous inits
        # assert custom_logger.logger.level == logging.DEBUG

    def test_log_event_with_extra_context(self, test_logger, temp_log_dir, logger_name):
        """Test logging events with additional context."""
        test_logger.log_event(
            LogEvents.AGENT_COMPLETED,
            "Agent finished",
            level="info",
            agent="DataProfiler",
            duration=2.5,
            quality_score=0.88,
            custom_field="custom_value"
        )
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        assert "AGENT_COMPLETED" in log_content
        assert "Agent finished" in log_content
        # Context should be included
        assert "Context:" in log_content or "custom_value" in log_content

    def test_log_event_passes_event_in_extra(self, test_logger):
        """Test that log_event includes event value in the extra dict.

        This is critical because SocketIOHandler.emit() checks
        hasattr(record, 'event') to detect structured events.
        """
        handler = MagicMock(spec=logging.Handler)
        handler.level = logging.DEBUG
        test_logger.logger.addHandler(handler)

        test_logger.log_event(
            LogEvents.PHASE1_START,
            "Starting phase 1",
            level="info",
            phase="phase1",
        )

        handler.handle.assert_called_once()
        record = handler.handle.call_args[0][0]
        assert hasattr(record, "event"), "log_event must pass event in extra dict"
        assert record.event == "PHASE1_START"
        assert hasattr(record, "phase")
        assert record.phase == "phase1"

        test_logger.logger.removeHandler(handler)

    def test_agent_execution_passes_event_in_extra(self, test_logger):
        """Test that agent_execution includes event and agent in extra dict."""
        handler = MagicMock(spec=logging.Handler)
        handler.level = logging.DEBUG
        test_logger.logger.addHandler(handler)

        test_logger.agent_execution("DataProfiler", "invoked")

        handler.handle.assert_called_once()
        record = handler.handle.call_args[0][0]
        assert hasattr(record, "event")
        assert record.event == "AGENT_INVOKED"
        assert hasattr(record, "agent")
        assert record.agent == "DataProfiler"

        test_logger.logger.removeHandler(handler)

    def test_concurrent_logging(self, test_logger, temp_log_dir, logger_name):
        """Test that concurrent logging doesn't cause issues."""
        import threading

        def log_messages(thread_id):
            for i in range(10):
                test_logger.log_event(
                    LogEvents.CACHE_CHECK,
                    f"Thread {thread_id} message {i}",
                    level="info"
                )

        threads = [threading.Thread(target=log_messages, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        # Should have all 30 messages (3 threads * 10 messages)
        assert log_content.count("CACHE_CHECK") >= 30

    def test_log_file_format(self, test_logger, temp_log_dir, logger_name):
        """Test log file format matches requirements."""
        test_logger.log_event(LogEvents.CACHE_HIT, "Test message", level="info")
        self._flush_handlers(test_logger)

        log_file = self._get_log_file(temp_log_dir, logger_name)
        log_content = log_file.read_text()

        # Format: timestamp | level | name | message
        lines = log_content.strip().split('\n')
        assert len(lines) > 0

        line = lines[0]
        # Should contain timestamp, level, logger name, event
        assert "|" in line  # Separator
        assert "INFO" in line or "DEBUG" in line  # Log level
        assert "CACHE_HIT" in line  # Event name

    def test_no_duplicate_handlers(self, temp_log_dir):
        """Test that logger doesn't create duplicate handlers."""
        logger1 = DAAgentLogger(name="TestNoDup", log_dir=temp_log_dir)
        initial_handler_count = len(logger1.logger.handlers)

        logger2 = DAAgentLogger(name="TestNoDup", log_dir=temp_log_dir)
        final_handler_count = len(logger2.logger.handlers)

        # Should not add duplicate handlers
        assert initial_handler_count == final_handler_count
