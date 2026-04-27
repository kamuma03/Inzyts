"""Hardened sandbox kernel execution for LLM-generated code.

This module wraps ``jupyter_client`` with explicit security policy:

* Resource limits applied via ``setrlimit`` in the child process before exec
  — memory, CPU time, process count, file-descriptor count, max file size.
  Belt-and-braces with the worker container's Docker memory limit.
* New process group (``os.setsid``) so the parent can ``SIGKILL`` the whole
  kernel + any subprocesses it spawned on timeout. The kernel may ignore
  ``interrupt_kernel`` (Python's signal handlers can swallow SIGINT during
  C extension calls) but cannot ignore SIGKILL.
* Working directory confinement to a per-job tmpdir. The kernel still has
  read access to the worker's bind mounts (source tree, output, datasets)
  but its ``cwd`` and any relative-path operations are scoped.
* Network egress is blocked at the worker container level (see worker
  entrypoint) — this module does not own that policy but documents it as
  a required precondition for the production policy.

Two public surfaces:

* ``KernelSandbox`` — the new policy-aware class. Use this for any new code.
* ``SandboxExecutor`` — preserved as a thin backward-compatible wrapper so
  ``cell_edit_agent`` and the re-run flow work unchanged.
"""

from __future__ import annotations

import os
import queue
import resource
import shutil
import signal
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import jupyter_client

from src.utils.logger import get_logger

logger = get_logger()

MAX_IMAGE_SIZE = int(5 * 1024 * 1024)  # 5MB limit for image/png base64 payloads
MAX_OUTPUT_LEN = 1500
MAX_TRACEBACK_LEN = 2000

# Sentinel error names used in audit/telemetry so the caller can tell apart
# user-code failures from sandbox-policy enforcement.
ERR_TIMEOUT = "SandboxTimeoutKill"
ERR_KERNEL_DEAD = "SandboxKernelDead"
ERR_INIT = "SandboxInitError"
ERR_SYSTEM = "SandboxSystemError"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SandboxPolicy:
    """Resource and isolation limits applied to a kernel sandbox.

    Limits are applied in the *child* process via ``preexec_fn``. They are
    Linux-specific via ``setrlimit``; on macOS most apply, on Windows they
    silently no-op (production runs on Linux in Docker).
    """

    # Memory cap in MB. Triggers MemoryError in the kernel when reached.
    memory_mb: int = 2048
    # CPU seconds per kernel process (RLIMIT_CPU). Hard limit kills the kernel.
    cpu_seconds: int = 300
    # Wall-clock timeout per cell. Enforced by the parent — on overrun we
    # SIGKILL the kernel's process group.
    timeout_seconds: int = 60
    # Max child processes the kernel can fork (RLIMIT_NPROC). Stops fork bombs.
    max_processes: int = 64
    # Max open file descriptors (RLIMIT_NOFILE).
    max_open_files: int = 256
    # Max single-file write size in MB (RLIMIT_FSIZE). Stops "fill the disk".
    max_file_size_mb: int = 100
    # Working directory for the kernel. If None, a per-instance tmpdir is
    # created and cleaned up on shutdown. Pass an explicit dir if the caller
    # needs to inspect outputs.
    working_dir: Optional[str] = None
    # Block network egress at the kernel-process level. Sets http_proxy /
    # https_proxy / no_proxy env vars to a blackhole, defeating ``requests``,
    # ``urllib``, ``httpx``, ``pip``, and most other libraries that respect
    # standard proxy env vars.
    #
    # Threat-model note: a determined attacker using raw sockets via ctypes
    # bypasses this. The production-grade defence is a network-layer egress
    # block (iptables in the worker container, or an egress-only proxy
    # sidecar). See docs/architecture.md "Threat Model".
    network_egress_blocked: bool = True
    # Tag included in audit logs so it's easy to filter test runs etc.
    name: str = "production"


PRODUCTION_POLICY = SandboxPolicy()
"""Default — what production runs use."""

DEVELOPMENT_POLICY = SandboxPolicy(
    memory_mb=4096,
    cpu_seconds=600,
    timeout_seconds=300,
    max_processes=128,
    name="development",
)
"""Looser limits for local development against larger datasets."""


def _build_preexec_fn(policy: SandboxPolicy) -> Callable[[], None]:
    """Build the ``preexec_fn`` closure applied in the kernel child process.

    Runs after ``fork()`` and before ``execve()``. Each ``setrlimit`` call is
    individually wrapped — we'd rather lose one limit than fail kernel start.
    """
    memory_bytes = policy.memory_mb * 1024 * 1024
    file_size_bytes = policy.max_file_size_mb * 1024 * 1024
    cpu_secs = policy.cpu_seconds
    nproc = policy.max_processes
    nofile = policy.max_open_files

    def _apply() -> None:
        # New session/process group so the parent owns it for SIGKILL.
        try:
            os.setsid()
        except OSError:
            pass

        for rlimit_name, rlimit_const, value in (
            ("RLIMIT_AS", getattr(resource, "RLIMIT_AS", None), memory_bytes),
            ("RLIMIT_CPU", getattr(resource, "RLIMIT_CPU", None), cpu_secs),
            ("RLIMIT_NPROC", getattr(resource, "RLIMIT_NPROC", None), nproc),
            ("RLIMIT_NOFILE", getattr(resource, "RLIMIT_NOFILE", None), nofile),
            ("RLIMIT_FSIZE", getattr(resource, "RLIMIT_FSIZE", None), file_size_bytes),
        ):
            if rlimit_const is None:
                continue
            try:
                resource.setrlimit(rlimit_const, (value, value))
            except (ValueError, OSError):
                # Limit not supported on this platform — fall through.
                pass

    return _apply


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


def truncate_str(text: str, max_len: int = MAX_OUTPUT_LEN) -> str:
    """Truncate a string to max_len, keeping head and tail with a marker between."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if len(text) > max_len:
        half = max_len // 2
        return text[:half] + "\n\n...[TRUNCATED_FOR_SIZE]...\n\n" + text[-half:]
    return text


@dataclass
class ExecutionResult:
    """Result of a single cell execution.

    Pre-existing public shape preserved for callers (cell_edit_agent etc.).
    """

    success: bool = True
    output: str = ""
    error_name: Optional[str] = None
    error_value: Optional[str] = None
    traceback: List[str] = field(default_factory=list)
    execution_count: Optional[int] = None
    images: List[str] = field(default_factory=list)
    # Telemetry — added by KernelSandbox; old SandboxExecutor users can ignore.
    duration_ms: int = 0
    killed_reason: Optional[str] = None  # set when policy enforcement fires


# ---------------------------------------------------------------------------
# Kernel sandbox
# ---------------------------------------------------------------------------


class KernelSandbox:
    """A jupyter_client kernel managed under an explicit ``SandboxPolicy``.

    Lifecycle: construction starts the kernel; ``execute_cell()`` runs code
    with policy enforcement; ``shutdown()`` cleans up. Use as a context
    manager when possible.
    """

    def __init__(
        self,
        policy: SandboxPolicy = PRODUCTION_POLICY,
        kernel_name: str = "python3",
    ):
        self.policy = policy
        self.kernel_name = kernel_name
        self.km: Optional[Any] = None
        self.kc: Optional[Any] = None
        self._working_dir: Optional[str] = policy.working_dir
        self._working_dir_owned: bool = False
        self._start_kernel()

    # -- lifecycle -----------------------------------------------------------

    def _build_kernel_env(self) -> Dict[str, str]:
        """Build the env vars passed to the kernel subprocess.

        Inherits the parent's env, then layers on policy-driven overrides:
        a blackhole proxy if egress is blocked. Always cleared so the
        kernel doesn't accidentally reuse the parent's auth tokens.
        """
        env = dict(os.environ)
        # Strip obvious credentials so a leaky kernel can't echo them back.
        for sensitive in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "JUPYTER_TOKEN",
            "INZYTS_API_TOKEN",
            "JWT_SECRET_KEY",
            "POSTGRES_PASSWORD",
            "ADMIN_PASSWORD",
            "INZYTS__LLM__ANTHROPIC_API_KEY",
            "INZYTS__LLM__OPENAI_API_KEY",
            "INZYTS__LLM__GEMINI_API_KEY",
            "INZYTS__JUPYTER__TOKEN",
        ):
            env.pop(sensitive, None)

        if self.policy.network_egress_blocked:
            # Point standard proxy env vars at an unroutable blackhole. Any
            # library that honors these (requests, urllib, httpx, pip, etc.)
            # will fail to reach the network. ``no_proxy`` left empty so
            # nothing escapes the proxy.
            blackhole = "http://127.0.0.1:1"
            env["http_proxy"] = blackhole
            env["HTTP_PROXY"] = blackhole
            env["https_proxy"] = blackhole
            env["HTTPS_PROXY"] = blackhole
            env["all_proxy"] = blackhole
            env["ALL_PROXY"] = blackhole
            env["no_proxy"] = ""
            env["NO_PROXY"] = ""
        return env

    def _start_kernel(self) -> None:
        if not self._working_dir:
            self._working_dir = tempfile.mkdtemp(prefix="inzyts-kernel-")
            self._working_dir_owned = True
        os.makedirs(self._working_dir, exist_ok=True)

        preexec = _build_preexec_fn(self.policy)
        kernel_env = self._build_kernel_env()

        try:
            # ``preexec_fn`` and ``env`` flow through
            # jupyter_client.manager.start_new_kernel →
            # KernelManager.start_kernel → launch_kernel → subprocess.Popen.
            try:
                self.km, self.kc = jupyter_client.manager.start_new_kernel(
                    kernel_name=self.kernel_name,
                    cwd=self._working_dir,
                    preexec_fn=preexec,
                    env=kernel_env,
                )
            except TypeError:
                # Older jupyter_client builds don't forward preexec_fn —
                # the fallback path provides isolation only at the container
                # level. Loud warning so this is investigated.
                logger.error(
                    "jupyter_client did not accept preexec_fn — RESOURCE LIMITS NOT APPLIED. "
                    "Upgrade jupyter_client or audit the launcher path."
                )
                self.km, self.kc = jupyter_client.manager.start_new_kernel(
                    kernel_name=self.kernel_name,
                    cwd=self._working_dir,
                    env=kernel_env,
                )
            logger.info(
                f"KernelSandbox started (policy={self.policy.name}, "
                f"egress_blocked={self.policy.network_egress_blocked}, "
                f"cwd={self._working_dir})"
            )
        except Exception as e:
            logger.error(f"Failed to start KernelSandbox: {e}")
            self.shutdown()
            raise RuntimeError(f"Sandbox kernel initialization failed: {e}") from e

    def shutdown(self) -> None:
        if self.kc:
            try:
                self.kc.stop_channels()
            except Exception:
                pass
            self.kc = None
        if self.km:
            try:
                self.km.shutdown_kernel(now=True)
            except Exception:
                pass
            self.km = None
        if self._working_dir_owned and self._working_dir and os.path.isdir(self._working_dir):
            shutil.rmtree(self._working_dir, ignore_errors=True)
        logger.info("KernelSandbox shut down.")

    def __enter__(self) -> "KernelSandbox":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()

    # -- execution -----------------------------------------------------------

    def _killpg(self) -> None:
        """SIGKILL the kernel's process group — used on timeout."""
        if not self.km or not getattr(self.km, "has_kernel", False):
            return
        kernel = getattr(self.km, "kernel", None)
        pid = getattr(kernel, "pid", None) if kernel else None
        if not pid:
            return
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def execute_cell(self, code: str) -> ExecutionResult:
        """Execute one cell and return a structured result.

        Wall-clock timeout is enforced by the parent: when exceeded we SIGKILL
        the kernel's process group, mark the result as ``ERR_TIMEOUT``, and
        leave it to the caller (or a kernel pool) to restart the kernel.
        """
        result = ExecutionResult()
        output_parts: List[str] = []
        started_at = time.time()

        if not self.kc:
            result.success = False
            result.error_name = ERR_KERNEL_DEAD
            result.error_value = "Kernel client not initialized."
            result.duration_ms = 0
            return result

        try:
            msg_id = self.kc.execute(code)

            while True:
                elapsed = time.time() - started_at
                if elapsed > self.policy.timeout_seconds:
                    result.success = False
                    result.error_name = ERR_TIMEOUT
                    result.error_value = (
                        f"Cell execution exceeded {self.policy.timeout_seconds}s. "
                        "Kernel was force-killed."
                    )
                    result.killed_reason = "timeout"
                    logger.warning(
                        f"KernelSandbox timeout after {self.policy.timeout_seconds}s — SIGKILL"
                    )
                    self._killpg()
                    break

                try:
                    msg = self.kc.get_iopub_msg(timeout=0.1)
                except queue.Empty:
                    time.sleep(0.01)
                    continue

                if msg["parent_header"].get("msg_id") != msg_id:
                    continue

                msg_type = msg["header"]["msg_type"]
                content = msg["content"]

                if msg_type == "status":
                    if content["execution_state"] == "idle":
                        break
                elif msg_type == "stream":
                    if content["name"] == "stdout":
                        output_parts.append(content["text"])
                    elif content["name"] == "stderr":
                        output_parts.append(f"[STDERR] {content['text']}")
                elif msg_type in ("execute_result", "display_data"):
                    data = content.get("data", {})
                    if "image/png" in data:
                        img_data = data["image/png"]
                        if len(img_data) > MAX_IMAGE_SIZE:
                            logger.warning(
                                f"Skipped image of size {len(img_data)} > MAX_IMAGE_SIZE"
                            )
                        else:
                            result.images.append(img_data)
                    if "text/plain" in data:
                        output_parts.append(data["text/plain"])
                elif msg_type == "error":
                    result.success = False
                    result.error_name = content["ename"]
                    result.error_value = content["evalue"]
                    result.traceback = content["traceback"]

            # Drain shell channel for the final reply (carries execution_count).
            try:
                reply = self.kc.get_shell_msg(timeout=2)
                if reply["parent_header"].get("msg_id") == msg_id:
                    reply_content = reply["content"]
                    if reply_content["status"] == "error" and not result.error_name:
                        result.success = False
                        result.error_name = reply_content.get("ename")
                        result.error_value = reply_content.get("evalue")
                        result.traceback = reply_content.get("traceback", [])
                    result.execution_count = reply_content.get("execution_count")
            except queue.Empty:
                pass

        except Exception as e:
            logger.error(f"KernelSandbox execution crashed: {e}")
            result.success = False
            result.error_name = ERR_SYSTEM
            result.error_value = str(e)

        # Truncate to keep telemetry / LLM retry payloads bounded.
        result.output = truncate_str("".join(output_parts))
        if result.error_value:
            result.error_value = truncate_str(result.error_value)
        if result.traceback:
            tb_str = "\n".join(result.traceback)
            result.traceback = [truncate_str(tb_str, max_len=MAX_TRACEBACK_LEN)]

        result.duration_ms = int((time.time() - started_at) * 1000)
        return result

    # -- introspection -------------------------------------------------------

    @property
    def working_dir(self) -> Optional[str]:
        return self._working_dir

    def is_alive(self) -> bool:
        return bool(self.km and getattr(self.km, "is_alive", lambda: False)())

    def restart(self) -> None:
        """Restart the underlying kernel. Used by the live notebook UI."""
        if self.km:
            try:
                self.km.restart_kernel(now=True)
                logger.info("KernelSandbox restarted")
            except Exception as e:
                logger.warning(f"KernelSandbox restart failed: {e}")


# ---------------------------------------------------------------------------
# Backwards-compatible wrapper
# ---------------------------------------------------------------------------


class SandboxExecutor:
    """Backwards-compatible facade for the old API.

    Existing call sites (``cell_edit_agent.py``, the re-run flow) keep working
    against this class. New code should use :class:`KernelSandbox` directly.
    """

    def __init__(self, kernel_name: str = "python3", execution_timeout: int = 60):
        # Honour the legacy timeout parameter while keeping the rest of the
        # production policy.
        policy = SandboxPolicy(
            timeout_seconds=execution_timeout,
            memory_mb=PRODUCTION_POLICY.memory_mb,
            cpu_seconds=max(PRODUCTION_POLICY.cpu_seconds, execution_timeout * 2),
            max_processes=PRODUCTION_POLICY.max_processes,
            max_open_files=PRODUCTION_POLICY.max_open_files,
            max_file_size_mb=PRODUCTION_POLICY.max_file_size_mb,
            name="legacy_compat",
        )
        self._sandbox = KernelSandbox(policy=policy, kernel_name=kernel_name)

    @property
    def km(self) -> Any:
        return self._sandbox.km

    @property
    def kc(self) -> Any:
        return self._sandbox.kc

    def execute_cell(self, code: str) -> ExecutionResult:
        return self._sandbox.execute_cell(code)

    def shutdown(self) -> None:
        self._sandbox.shutdown()

    def __enter__(self) -> "SandboxExecutor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
