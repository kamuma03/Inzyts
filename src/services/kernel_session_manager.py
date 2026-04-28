"""
Kernel Session Manager - Manages persistent Jupyter kernel sessions for interactive editing.

Keeps kernels alive after job completion so users can iteratively edit cells
without re-running the full analysis pipeline. Sessions expire after an idle TTL.
"""

import threading
import time
from typing import Dict, Optional, Any, List

from src.services.sandbox_executor import SandboxExecutor, ExecutionResult
from src.utils.logger import get_logger

logger = get_logger()

# Default idle timeout in seconds (30 minutes)
DEFAULT_TTL_SECONDS = 30 * 60


class KernelSession:
    """Represents a single active kernel session tied to a job."""

    def __init__(self, job_id: str, csv_path: str):
        self.job_id = job_id
        self.csv_path = csv_path
        self.executor: Optional[SandboxExecutor] = None
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
        self.df_context: str = ""
        self._initialized: bool = False

    def start(self) -> None:
        """Start the kernel and load the dataset."""
        # Pass the CSV path to the kernel via subprocess env (NOT by mutating
        # the worker's own os.environ — that would leak the most-recent job's
        # path into every subsequent request handler in the same process).
        # Using env still avoids the code-injection risk of interpolating a
        # crafted filename into the bootstrap source.
        self.executor = SandboxExecutor(
            execution_timeout=120,
            extra_env={"_INZYTS_KERNEL_CSV_PATH": self.csv_path},
        )

        bootstrap_code = """
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os
import warnings
warnings.filterwarnings('ignore')

# Load the dataset from environment variable (safe — no code injection)
_csv_path = os.environ.get("_INZYTS_KERNEL_CSV_PATH", "")
if not os.path.exists(_csv_path):
    _base = os.path.basename(_csv_path)
    _upload_dir = os.environ.get("UPLOAD_DIR", "data/uploads")
    if os.path.exists(_base):
        _csv_path = _base
    elif os.path.exists(os.path.join(_upload_dir, _base)):
        _csv_path = os.path.join(_upload_dir, _base)

try:
    df = pd.read_csv(_csv_path)
except Exception:
    try:
        df = pd.read_csv(_csv_path, sep=None, engine='python')
    except Exception:
        df = pd.read_csv(_csv_path, sep=None, engine='python', encoding='latin-1')

print(f"Loaded {len(df)} rows x {len(df.columns)} columns")
print(df.dtypes.to_string())
"""
        result = self.executor.execute_cell(bootstrap_code)
        if result.success and result.output:
            # Extract dtypes info from output for context
            lines = result.output.strip().split("\n")
            if len(lines) > 1:
                self.df_context = "\n".join(lines[1:])  # Skip the "Loaded X rows" line
            else:
                self.df_context = result.output
        elif not result.success:
            logger.error(
                f"Kernel bootstrap failed for job {self.job_id}: "
                f"{result.error_name}: {result.error_value}"
            )
            self._initialized = False
            raise RuntimeError(f"Kernel bootstrap failed: {result.error_value}")

        self._initialized = True
        logger.info(f"Kernel session started for job {self.job_id}")

    def execute(self, code: str) -> ExecutionResult:
        """Execute code in this session's kernel."""
        if not self.executor or not self.executor.kc:
            raise RuntimeError("Kernel not initialized")

        self.last_activity = time.time()
        return self.executor.execute_cell(code)

    def execute_streaming(self, code: str, on_output) -> ExecutionResult:
        """Execute code with per-message callbacks for streaming UI updates.

        ``on_output`` is invoked synchronously with each Jupyter IOPub event
        in nbformat shape — see KernelSandbox.execute_cell_streaming.
        """
        if not self.executor or not self.executor.kc:
            raise RuntimeError("Kernel not initialized")

        self.last_activity = time.time()
        # The wrapper SandboxExecutor exposes the inner KernelSandbox as
        # ._sandbox; reach through for the streaming method.
        sandbox = getattr(self.executor, "_sandbox", None)
        if sandbox and hasattr(sandbox, "execute_cell_streaming"):
            return sandbox.execute_cell_streaming(code, on_output=on_output)
        # Fallback for any executor that doesn't expose streaming.
        return self.executor.execute_cell(code)

    def is_expired(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
        """Check if the session has been idle beyond the TTL."""
        return (time.time() - self.last_activity) > ttl_seconds

    def introspect(self) -> str:
        """Capture current kernel variable state for follow-up context.

        Executes a lightweight snippet that lists user-defined variables,
        their types, and DataFrame column info. Returns a compact summary.
        """
        if not self.executor or not self.executor.kc:
            return self.df_context  # Fallback to bootstrap context

        introspect_code = """
import sys as _sys
_ignore = {'__builtins__', '__name__', '__doc__', '__package__', '__loader__',
           '__spec__', '_sys', '_ignore', '_lines', '_info', '_csv_path',
           '_base', 'warnings', 'os', 'In', 'Out', 'get_ipython', 'exit', 'quit'}
_lines = []
for _name, _obj in sorted(locals().items()):
    if _name.startswith('_') or _name in _ignore:
        continue
    _info = type(_obj).__name__
    if hasattr(_obj, 'shape'):
        _info += f" shape={_obj.shape}"
    elif hasattr(_obj, '__len__'):
        try:
            _info += f" len={len(_obj)}"
        except Exception:
            pass
    _lines.append(f"{_name}: {_info}")
print("\\n".join(_lines[:50]))
"""
        try:
            result = self.executor.execute_cell(introspect_code)
            if result.success and result.output:
                return result.output.strip()
        except Exception as e:
            logger.warning(f"Kernel introspection failed for job {self.job_id}: {e}")

        return self.df_context  # Fallback

    def restart(self) -> None:
        """Restart the underlying kernel.

        Used by the Live panel's "Restart kernel" control. Tears down the
        current executor and re-bootstraps the dataset so subsequent cells
        start from a known clean state.
        """
        if self.executor:
            try:
                self.executor.shutdown()
            except Exception as e:
                logger.warning(f"Restart shutdown raised for job {self.job_id}: {e}")
            self.executor = None
        self._initialized = False
        self.last_activity = time.time()
        # Re-run the same bootstrap that ``start`` did so the dataset is
        # available again. Caller is responsible for handling any failure.
        self.start()
        logger.info(f"Kernel session restarted for job {self.job_id}")

    def interrupt(self) -> None:
        """Send an interrupt to the running cell, if any.

        Best-effort: routes through the underlying kernel's interrupt
        mechanism. For hard kills on a runaway cell, the wall-clock
        timeout in ``SandboxPolicy`` will SIGKILL the process group.
        """
        if not self.executor or not self.executor.km:
            return
        try:
            self.executor.km.interrupt_kernel()
            logger.info(f"Interrupted kernel for job {self.job_id}")
        except Exception as e:
            logger.warning(f"Interrupt failed for job {self.job_id}: {e}")

    def shutdown(self) -> None:
        """Shutdown the kernel."""
        if self.executor:
            self.executor.shutdown()
            self.executor = None
        logger.info(f"Kernel session closed for job {self.job_id}")


class KernelSessionManager:
    """
    Singleton manager for persistent kernel sessions.

    Thread-safe management of kernel sessions keyed by job_id.
    Includes automatic cleanup of expired sessions.
    """

    MAX_SESSIONS = 20  # Prevent unbounded kernel process creation

    _instance: Optional["KernelSessionManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "KernelSessionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: Dict[str, KernelSession] = {}
                    cls._instance._session_lock = threading.Lock()
                    cls._instance._cleanup_thread: Optional[threading.Thread] = None
                    cls._instance._running = False
        return cls._instance

    def start_cleanup_daemon(self) -> None:
        """Start the background cleanup thread."""
        if self._running:
            return

        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="kernel-session-cleanup"
        )
        self._cleanup_thread.start()
        logger.info("Kernel session cleanup daemon started")

    def _cleanup_loop(self) -> None:
        """Periodically clean up expired sessions."""
        while self._running:
            try:
                self.cleanup_expired()
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")
            time.sleep(60)  # Check every minute

    def get_or_create_session(self, job_id: str, csv_path: str) -> KernelSession:
        """
        Get an existing session or create a new one for a job.

        Args:
            job_id: The job identifier.
            csv_path: Path to the CSV file for this job.

        Returns:
            An active KernelSession.
        """
        with self._session_lock:
            if job_id in self._sessions:
                session = self._sessions[job_id]
                if not session.is_expired():
                    session.last_activity = time.time()
                    return session
                else:
                    # Expired — shut it down and create a new one
                    session.shutdown()

            # Enforce session limit to prevent resource exhaustion.
            # If at capacity after cleanup, evict the oldest idle session (LRU).
            self.cleanup_expired()
            if len(self._sessions) >= self.MAX_SESSIONS:
                oldest_id = min(
                    self._sessions,
                    key=lambda jid: self._sessions[jid].last_activity,
                )
                logger.warning(
                    f"MAX_SESSIONS ({self.MAX_SESSIONS}) reached — "
                    f"evicting oldest idle session: {oldest_id}"
                )
                self._sessions[oldest_id].shutdown()
                del self._sessions[oldest_id]

            # Create new session
            session = KernelSession(job_id=job_id, csv_path=csv_path)
            session.start()
            self._sessions[job_id] = session

            # Start cleanup daemon if not already running
            if not self._running:
                self.start_cleanup_daemon()

            return session

    def get_session(self, job_id: str) -> Optional[KernelSession]:
        """Get an existing session without creating a new one."""
        with self._session_lock:
            session = self._sessions.get(job_id)
            if session and not session.is_expired():
                return session
            return None

    def execute_cell(self, job_id: str, code: str) -> ExecutionResult:
        """
        Execute code in a job's kernel session.

        Args:
            job_id: The job identifier.
            code: Python code to execute.

        Returns:
            ExecutionResult with output and error info.

        Raises:
            RuntimeError: If no session exists for this job.
        """
        session = self.get_session(job_id)
        if not session:
            raise RuntimeError(f"No active kernel session for job {job_id}")
        return session.execute(code)

    def get_context(self, job_id: str) -> str:
        """Get the dataframe context for a job's session."""
        session = self.get_session(job_id)
        if session:
            return session.df_context
        return ""

    def close_session(self, job_id: str) -> None:
        """Explicitly close a session."""
        with self._session_lock:
            session = self._sessions.pop(job_id, None)
            if session:
                session.shutdown()

    def restart_session(self, job_id: str) -> Optional[KernelSession]:
        """Restart the kernel for an existing session, preserving the entry.

        Returns the (now-restarted) session, or None if no session exists.
        """
        with self._session_lock:
            session = self._sessions.get(job_id)
            if session:
                session.restart()
                return session
            return None

    def interrupt_session(self, job_id: str) -> bool:
        """Best-effort interrupt of the currently-running cell."""
        session = self.get_session(job_id)
        if not session:
            return False
        session.interrupt()
        return True

    def cleanup_expired(self) -> None:
        """Remove all expired sessions."""
        with self._session_lock:
            expired_ids = [
                jid for jid, session in self._sessions.items() if session.is_expired()
            ]
            for jid in expired_ids:
                self._sessions[jid].shutdown()
                del self._sessions[jid]
                logger.info(f"Cleaned up expired kernel session for job {jid}")

    def active_session_count(self) -> int:
        """Return the number of active sessions."""
        with self._session_lock:
            return len(self._sessions)

    def shutdown_all(self) -> None:
        """Shutdown all sessions (for graceful app shutdown)."""
        self._running = False
        with self._session_lock:
            for session in self._sessions.values():
                session.shutdown()
            self._sessions.clear()
        logger.info("All kernel sessions shutdown")


# Module-level singleton accessor
kernel_session_manager = KernelSessionManager()
