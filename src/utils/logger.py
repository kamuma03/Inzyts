"""
Structured logging infrastructure for Inzyts v0.10.0
Implements LOG_EVENTS from requirements Section 11.2 (lines 1533-1562)
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from enum import Enum
from src.config import settings


class LogEvents(str, Enum):
    """
    Structured log events for monitoring and observability.
    Based on requirements Section 11.2, lines 1535-1562.
    """

    # Pipeline Mode Events
    MODE_DETECTED = "MODE_DETECTED"
    MODE_EXPLICIT = "MODE_EXPLICIT"
    MODE_INFERRED = "MODE_INFERRED"
    MODE_DEFAULT = "MODE_DEFAULT"

    # Cache Events
    CACHE_CHECK = "CACHE_CHECK"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    CACHE_EXPIRED = "CACHE_EXPIRED"
    CACHE_CSV_CHANGED = "CACHE_CSV_CHANGED"
    CACHE_SAVED = "CACHE_SAVED"
    CACHE_DELETED = "CACHE_DELETED"

    # Upgrade Events
    UPGRADE_STARTED = "UPGRADE_STARTED"
    UPGRADE_FROM_CACHE = "UPGRADE_FROM_CACHE"
    UPGRADE_COMPLETED = "UPGRADE_COMPLETED"

    # Exploratory Conclusions Events
    EXPLORATORY_CONCLUSIONS_START = "EXPLORATORY_CONCLUSIONS_START"
    EXPLORATORY_CONCLUSIONS_COMPLETE = "EXPLORATORY_CONCLUSIONS_COMPLETE"
    EXPLORATORY_CONCLUSIONS_LOW_CONFIDENCE = "EXPLORATORY_CONCLUSIONS_LOW_CONFIDENCE"

    # Phase Events
    PHASE1_START = "PHASE1_START"
    PHASE1_COMPLETE = "PHASE1_COMPLETE"
    PHASE2_START = "PHASE2_START"
    PHASE2_COMPLETE = "PHASE2_COMPLETE"
    PROFILE_LOCK_GRANTED = "PROFILE_LOCK_GRANTED"
    PROFILE_LOCK_DENIED = "PROFILE_LOCK_DENIED"

    # Agent Events
    AGENT_INVOKED = "AGENT_INVOKED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"

    # Validation Events
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RECURSION_TRIGGERED = "RECURSION_TRIGGERED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"

    # Performance Events
    TOKEN_USAGE = "TOKEN_USAGE"
    EXECUTION_TIME = "EXECUTION_TIME"


class DAAgentLogger:
    """
    Centralized logger for Inzyts system.
    Provides structured logging with event types and context.
    """

    def __init__(
        self,
        name: str = "Inzyts",
        log_dir: str = "logs",
        log_level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """
        Initialize logger with file and console handlers.

        Args:
            name: Logger name
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_bytes: Max size per log file before rotation
            backup_count: Number of backup files to keep
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        # Create logs directory
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_path / f"{name.lower()}.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_event(self, event: LogEvents, message: str, level: str = "info", **kwargs):
        """
        Log a structured event with context.

        Args:
            event: Event type from LogEvents enum
            message: Human-readable message
            level: Log level (debug, info, warning, error, critical)
            **kwargs: Additional context to include in log
        """
        context = f"[{event.value}] {message}"
        if kwargs:
            context += f" | Context: {kwargs}"

        log_func = getattr(self.logger, level.lower())
        # Include 'event' so SocketIOHandler can detect structured events
        kwargs["event"] = event.value
        log_func(context, extra=kwargs)

    def mode_detected(self, mode: str, detection_method: str):
        """Log pipeline mode detection."""
        if detection_method == "explicit":
            event = LogEvents.MODE_EXPLICIT
        elif detection_method == "inferred":
            event = LogEvents.MODE_INFERRED
        elif detection_method == "default":
            event = LogEvents.MODE_DEFAULT
        else:
            event = LogEvents.MODE_DETECTED

        initial_log = (
            f"Multi-Agent Data Analysis System ({settings.app_version})\n{'=' * 50}"
        )
        self.logger.info(
            initial_log
        )  # Log the initial banner as a regular info message

        self.log_event(
            event,
            f"Pipeline mode set to {mode}",
            level="info",
            mode=mode,
            method=detection_method,
        )

    def cache_check(self, csv_path: str, status: str):
        """Log cache check result."""
        if status == "valid":
            event = LogEvents.CACHE_HIT
            level = "info"
        elif status == "not_found":
            event = LogEvents.CACHE_MISS
            level = "info"
        elif status == "expired":
            event = LogEvents.CACHE_EXPIRED
            level = "info"
        elif status == "csv_changed":
            event = LogEvents.CACHE_CSV_CHANGED
            level = "warning"
        else:
            event = LogEvents.CACHE_CHECK
            level = "debug"

        self.log_event(
            event,
            f"Cache check for {Path(csv_path).name}: {status}",
            level=level,
            csv_path=csv_path,
            cache_status=status,
        )

    def cache_saved(self, csv_hash: str, quality_score: float):
        """Log cache save operation."""
        self.log_event(
            LogEvents.CACHE_SAVED,
            f"Profile cached with hash {csv_hash[:8]}... (quality: {quality_score:.2f})",
            level="info",
            csv_hash=csv_hash,
            quality_score=quality_score,
        )

    def cache_deleted(self, csv_hash: str, reason: str):
        """Log cache deletion."""
        self.log_event(
            LogEvents.CACHE_DELETED,
            f"Cache deleted for {csv_hash[:8]}... (reason: {reason})",
            level="info",
            csv_hash=csv_hash,
            reason=reason,
        )

    def upgrade_started(self, from_mode: str, to_mode: str, using_cache: bool):
        """Log upgrade operation start."""
        self.log_event(
            LogEvents.UPGRADE_STARTED,
            f"Upgrading from {from_mode} to {to_mode}",
            level="info",
            from_mode=from_mode,
            to_mode=to_mode,
            using_cache=using_cache,
        )

        if using_cache:
            self.log_event(
                LogEvents.UPGRADE_FROM_CACHE,
                "Using cached profile for upgrade",
                level="info",
            )

    def exploratory_conclusions(self, status: str, confidence: Optional[float] = None):
        """Log exploratory conclusions generation."""
        if status == "start":
            self.log_event(
                LogEvents.EXPLORATORY_CONCLUSIONS_START,
                "Generating exploratory conclusions",
                level="info",
            )
        elif status == "complete":
            self.log_event(
                LogEvents.EXPLORATORY_CONCLUSIONS_COMPLETE,
                f"Exploratory conclusions generated (confidence: {confidence:.2f})"
                if confidence
                else "Exploratory conclusions generated",
                level="info",
                confidence=confidence,
            )
        elif status == "low_confidence":
            self.log_event(
                LogEvents.EXPLORATORY_CONCLUSIONS_LOW_CONFIDENCE,
                f"Low confidence in conclusions: {confidence:.2f}",
                level="warning",
                confidence=confidence,
            )

    def phase_transition(self, phase: str, status: str):
        """Log phase transitions."""
        event_map = {
            ("phase1", "start"): LogEvents.PHASE1_START,
            ("phase1", "complete"): LogEvents.PHASE1_COMPLETE,
            ("phase2", "start"): LogEvents.PHASE2_START,
            ("phase2", "complete"): LogEvents.PHASE2_COMPLETE,
        }

        event = event_map.get((phase, status))
        if event:
            self.log_event(
                event, f"{phase.upper()} {status}", level="info", phase=phase
            )

    def profile_lock(self, granted: bool, quality_score: float):
        """Log profile lock decision."""
        event = (
            LogEvents.PROFILE_LOCK_GRANTED if granted else LogEvents.PROFILE_LOCK_DENIED
        )
        self.log_event(
            event,
            f"Profile Lock {'GRANTED' if granted else 'DENIED'} (quality: {quality_score:.2f})",
            level="info" if granted else "warning",
            granted=granted,
            quality_score=quality_score,
        )

    def agent_execution(self, agent_name: str, status: str, **kwargs):
        """Log agent execution events."""
        event_map = {
            "invoked": LogEvents.AGENT_INVOKED,
            "completed": LogEvents.AGENT_COMPLETED,
            "failed": LogEvents.AGENT_FAILED,
        }

        event = event_map.get(status)
        if event:
            self.log_event(
                event,
                f"Agent '{agent_name}' {status}",
                level="info" if status != "failed" else "error",
                agent=agent_name,
                **kwargs,
            )

    def validation(self, phase: str, passed: bool, quality_score: float, **kwargs):
        """Log validation results."""
        event = LogEvents.VALIDATION_PASSED if passed else LogEvents.VALIDATION_FAILED
        self.log_event(
            event,
            f"{phase} validation {'PASSED' if passed else 'FAILED'} (quality: {quality_score:.2f})",
            level="info" if passed else "warning",
            phase=phase,
            passed=passed,
            quality_score=quality_score,
            **kwargs,
        )

    def recursion(self, reason: str, iteration: int, phase: str):
        """Log recursion trigger."""
        self.log_event(
            LogEvents.RECURSION_TRIGGERED,
            f"Recursion triggered in {phase} (iteration {iteration}): {reason}",
            level="info",
            phase=phase,
            iteration=iteration,
            reason=reason,
        )

    def escalation(self, reason: str, phase: str):
        """Log escalation to orchestrator."""
        self.log_event(
            LogEvents.ESCALATION_TRIGGERED,
            f"Escalation triggered in {phase}: {reason}",
            level="warning",
            phase=phase,
            reason=reason,
        )

    def log_token_usage(self, component: str, tokens: int, model: str):
        """Log token usage."""
        self.log_event(
            LogEvents.TOKEN_USAGE,
            f"Token Usage [{component}]: {tokens} (Model: {model})",
            level="info",
            component=component,
            tokens=tokens,
            model=model,
        )

    def log_execution_time(self, component: str, duration_seconds: float):
        """Log execution duration."""
        self.log_event(
            LogEvents.EXECUTION_TIME,
            f"Execution Time [{component}]: {duration_seconds:.3f}s",
            level="info",
            component=component,
            duration=duration_seconds,
        )

    def _log_proxy(self, method_name: str, msg: str, **kwargs):
        """Helper to proxy log calls to underlying logger handles standard args."""
        # Extract standard logging arguments
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", False)
        stacklevel = kwargs.pop("stacklevel", 1)
        extra = kwargs.pop("extra", {})

        # Merge remaining kwargs into extra
        # This preserves the behavior of treating unknown kwargs as context
        if kwargs:
            extra.update(kwargs)

        log_func = getattr(self.logger, method_name)
        log_func(
            msg,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def info(self, msg: str, **kwargs):
        """Proxy for logger.info."""
        self._log_proxy("info", msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Proxy for logger.warning."""
        self._log_proxy("warning", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """Proxy for logger.error."""
        self._log_proxy("error", msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        """Proxy for logger.debug."""
        self._log_proxy("debug", msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        """Proxy for logger.critical."""
        self._log_proxy("critical", msg, **kwargs)


# Global logger instance
_logger: Optional[DAAgentLogger] = None


def get_logger() -> DAAgentLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = DAAgentLogger()
    return _logger


def init_logger(
    name: str = "Inzyts", log_dir: str = "logs", log_level: int = logging.INFO
) -> DAAgentLogger:
    """Initialize the global logger with custom settings."""
    global _logger
    _logger = DAAgentLogger(name=name, log_dir=log_dir, log_level=log_level)
    return _logger
