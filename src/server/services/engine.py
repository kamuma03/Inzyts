import datetime
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from src.server.celery_app import celery_app
from src.server.db.database import SessionLocal
from src.server.db.models import Job, JobStatus
from src.server.services.cost_estimator import calculate_cost
from src.config import settings
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

logger = get_logger()

# Import analysis entry point. Fail fast at module load so the worker crashes
# on startup rather than silently deferring the error to task execution time.
# The project must be installed (pip install -e .) or PYTHONPATH must include
# the project root -- do NOT manipulate sys.path at runtime.
from src.main import run_analysis  # noqa: E402

# Compiled once at module level to avoid re-compiling on every log emission.
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
# Mask credentials in database URIs (e.g. postgresql://user:pass@host).
# Captures scheme + everything up to and including the '@', replacing user:pass
# with ***:***. Also handles URI-encoded credentials and API keys in query params.
_CREDENTIAL_MASK = re.compile(r"([\w+]+://)([^@\s]+)@")
_API_KEY_MASK = re.compile(r"((?:api[_-]?key|token|secret|password|auth)\s*[=:]\s*)['\"]?[\w\-./+]+['\"]?", re.IGNORECASE)

# Path prefixes stripped from user-facing error messages to avoid leaking
# internal filesystem layout.  Covers both Unix and Windows common paths.
_PATH_PREFIXES = (
    # Unix
    "/home/", "/app/", "/root/", "/usr/", "/var/", "/tmp/",
    # Windows (case-insensitive matching handled in _sanitize_error)
    "C:\\Users\\", "C:\\Program Files\\", "C:\\Windows\\", "D:\\",
    "C:/Users/", "C:/Program Files/", "C:/Windows/", "D:/",
)


def _sanitize_error(exc: Exception) -> str:
    """Return a safe error string that omits internal filesystem paths."""
    msg = f"{type(exc).__name__}: {exc}"
    for prefix in _PATH_PREFIXES:
        if prefix.lower() in msg.lower():
            pattern = re.escape(prefix) + r"[^\s\]'\"]+"
            # lambda avoids regex interpretation of backslashes in prefix
            msg = re.sub(pattern, lambda _: f"{prefix}...", msg, flags=re.IGNORECASE)
    return msg


class SocketIOHandler(logging.Handler):
    """Logging handler that emits records to SocketIO for real-time streaming.

    Defined at module level (not inside setup_job_logging) so that:
    - The class is created once per process, not once per task invocation.
    - It is easily unit-testable in isolation.
    """

    def __init__(self, job_id: str):
        super().__init__()
        from src.server.utils.socket_emitter import get_socket_manager
        self.job_id = job_id
        self.mgr = get_socket_manager()
        try:
            from src.server.services.progress_tracker import ProgressTracker
            self._tracker: Optional["ProgressTracker"] = ProgressTracker()
        except Exception:
            self._tracker = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            clean_msg = _ANSI_ESCAPE.sub("", msg)
            # Mask credentials embedded in database URIs (e.g. postgresql://user:pass@host).
            clean_msg = _CREDENTIAL_MASK.sub(r"\1***:***@", clean_msg)
            clean_msg = _API_KEY_MASK.sub(r"\1[REDACTED]", clean_msg)

            # Truncate very long messages to prevent log flooding.
            if len(clean_msg) > 2000:
                clean_msg = clean_msg[:2000] + "... [truncated]"

            payload = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "level": record.levelname,
                "message": clean_msg,
            }

            if hasattr(record, "event"):
                structured_payload = {
                    "type": "agent_event",
                    "event": getattr(record, "event"),
                    "phase": getattr(record, "phase", None),
                    "agent": getattr(record, "agent", None),
                    "status": getattr(record, "status", None),
                    "data": payload,
                }
                self.mgr.emit("agent_event", structured_payload, room=self.job_id)

                # Update progress tracker and emit progress event
                if self._tracker:
                    try:
                        event_str = getattr(record, "event")
                        agent_str = getattr(record, "agent", None)
                        self._tracker.update_from_event(self.job_id, event_str, agent_str)
                        progress_data = self._tracker.get_progress_with_timing(self.job_id)
                        self.mgr.emit("progress", {
                            "job_id": self.job_id,
                            "progress": int(progress_data.get("progress", 0)),
                            "message": progress_data.get("message", ""),
                            "phase": progress_data.get("phase", ""),
                            "elapsed_seconds": progress_data.get("elapsed_seconds"),
                            "eta_seconds": progress_data.get("eta_seconds"),
                            "phase_timings": progress_data.get("phase_timings"),
                        }, room=self.job_id)
                    except Exception:
                        pass  # Progress tracking must not break job execution

            self.mgr.emit("log", payload, room=self.job_id)
        except Exception as e:
            logger.debug(f"SocketIO emit failed: {e}")


@dataclass
class AnalysisTaskParams:
    """Parameters for analysis task execution.

    Bundles all task parameters into a single object for cleaner function signatures.
    """

    job_id: str
    csv_path: Optional[str]
    mode: str
    target: Optional[str] = None
    question: Optional[str] = None
    title: Optional[str] = None
    dict_path: Optional[str] = None
    analysis_type: Optional[str] = None
    multi_file_input: Optional[Dict] = None
    exclude_columns: Optional[List[str]] = None
    use_cache: bool = False
    db_uri: Optional[str] = None
    api_url: Optional[str] = None
    api_headers: Optional[Dict] = None
    api_auth: Optional[Dict] = None
    json_path: Optional[str] = None

    def to_run_analysis_kwargs(self) -> Dict:
        """Convert to kwargs for run_analysis() call."""
        return {
            "csv_path": self.csv_path,
            "target_column": self.target,
            "analysis_question": self.question,
            "title": self.title,
            "mode": self.mode,
            "use_cache": self.use_cache,
            "verbose": False,
            "interactive": False,
            "data_dictionary_path": self.dict_path,
            "analysis_type": self.analysis_type,
            "multi_file_input": self.multi_file_input,
            "exclude_columns": self.exclude_columns,
            "db_uri": self.db_uri,
            "api_url": self.api_url,
            "api_headers": self.api_headers,
            "api_auth": self.api_auth,
            "json_path": self.json_path,
        }


@contextmanager
def setup_job_logging(job_id: str, log_file: Path):
    """Context manager for job-specific logging."""
    socket_handler = SocketIOHandler(job_id)
    socket_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(socket_handler)
    root_logger.addHandler(file_handler)

    try:
        yield
    finally:
        root_logger.removeHandler(socket_handler)
        root_logger.removeHandler(file_handler)
        file_handler.close()


@celery_app.task(
    bind=True,
    max_retries=0,  # LLM pipeline runs are not idempotent — fail fast on error.
)
def execution_task(self, job_id: str, csv_path: Optional[str] = None, mode: str = "exploratory", **kwargs):
    """Refactored execution task with better error handling."""
    # Reset singleton agent instances so each job starts with fresh token counters.
    # This prevents token-count cross-contamination between jobs sharing a worker process.
    from src.workflow.agent_factory import AgentFactory
    AgentFactory.reset()

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Resolve log path from settings so it works correctly in Docker
        # where the working directory may differ from the app root.
        log_base = Path(settings.log_dir).resolve()
        log_file = log_base / "jobs" / f"{job_id}.log"
        ensure_dir(log_file.parent)

        params = AnalysisTaskParams(
            job_id=job_id, csv_path=csv_path, mode=mode, **kwargs
        )

        with setup_job_logging(job_id, log_file):
            try:
                job.status = JobStatus.RUNNING  # type: ignore
                job.logs_location = str(log_file.absolute())  # type: ignore
                session.commit()

                final_state = run_analysis(**params.to_run_analysis_kwargs())

                if final_state:
                    total_tokens = getattr(final_state, "total_tokens_used", 0)
                    prompt_tokens = getattr(final_state, "prompt_tokens_used", 0)
                    completion_tokens = getattr(final_state, "completion_tokens_used", 0)

                    job.token_usage = {
                        "total": total_tokens,
                        "prompt": prompt_tokens,
                        "completion": completion_tokens,
                    }  # type: ignore

                    # Resolve the configured model name for pricing lookup.
                    provider = settings.llm.default_provider
                    if provider == "anthropic":
                        model_name = settings.llm.anthropic_model or "claude-sonnet-4"
                    elif provider == "openai":
                        model_name = settings.llm.openai_model or "gpt-4o"
                    elif provider == "gemini":
                        model_name = settings.llm.gemini_model or "gemini-1.5-pro"
                    elif provider == "ollama":
                        model_name = "ollama"
                    else:
                        model_name = "gpt-4o"

                    cost = calculate_cost(prompt_tokens, completion_tokens, model_name)
                    job.cost_estimate = {"estimated_cost_usd": round(cost, 6), "total": round(cost, 6)}  # type: ignore

                    if final_state.final_notebook_path:
                        job.status = JobStatus.COMPLETED  # type: ignore
                        job.result_path = final_state.final_notebook_path  # type: ignore
                    else:
                        job.status = JobStatus.FAILED  # type: ignore
                        job.error_message = "; ".join(
                            getattr(final_state, "errors", ["No notebook generated"])
                        )  # type: ignore
                else:
                    job.status = JobStatus.FAILED  # type: ignore
                    job.error_message = "Analysis failed to produce a final state"  # type: ignore

            except Exception as e:
                logger.error(f"Execution failed for job {job_id}", exc_info=True)
                job.status = JobStatus.FAILED  # type: ignore
                # Sanitize error message to avoid leaking internal paths to API clients.
                job.error_message = _sanitize_error(e)  # type: ignore
            finally:
                # Mark progress as complete/failed in Redis
                try:
                    from src.server.services.progress_tracker import ProgressTracker
                    tracker = ProgressTracker()
                    tracker.mark_complete(
                        job_id,
                        success=(job.status == JobStatus.COMPLETED),
                    )
                except Exception:
                    pass
                session.commit()
