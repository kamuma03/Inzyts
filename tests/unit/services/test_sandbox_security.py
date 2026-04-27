"""End-to-end security primitive tests for KernelSandbox.

These tests start REAL kernels (no jupyter_client mock) so they exercise
the actual setrlimit / proxy / timeout machinery. They are slower than
the mocked tests in ``test_sandbox_executor.py`` (~5-10s each kernel
start) but they're the only way to verify the policy actually fires.

Run with:  python -m pytest tests/unit/services/test_sandbox_security.py -v

These are intentionally tagged via the ``slow`` marker so CI can skip
them on tight feedback loops if needed.
"""

from __future__ import annotations

import pytest

from src.services.sandbox_executor import (
    ERR_TIMEOUT,
    KernelSandbox,
    SandboxPolicy,
)


pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Policy + env hardening
# ---------------------------------------------------------------------------


def test_secrets_stripped_from_kernel_env(monkeypatch):
    """Sensitive parent env vars must not reach the kernel subprocess."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leaked")
    monkeypatch.setenv("JWT_SECRET_KEY", "shouldnotreach")
    monkeypatch.setenv("INNOCENT_VAR", "ok")

    with KernelSandbox(policy=SandboxPolicy(timeout_seconds=15)) as sb:
        result = sb.execute_cell(
            "import os\n"
            "print('ANTH=', os.environ.get('ANTHROPIC_API_KEY', 'MISSING'))\n"
            "print('JWT=', os.environ.get('JWT_SECRET_KEY', 'MISSING'))\n"
            "print('OK_=', os.environ.get('INNOCENT_VAR', 'MISSING'))"
        )
    assert result.success, result.error_value
    assert "ANTH= MISSING" in result.output
    assert "JWT= MISSING" in result.output
    assert "OK_= ok" in result.output


def test_proxy_blackhole_when_egress_blocked():
    """When network_egress_blocked=True, http_proxy points at a blackhole."""
    with KernelSandbox(policy=SandboxPolicy(timeout_seconds=15)) as sb:
        result = sb.execute_cell(
            "import os\n"
            "print('PROXY=', os.environ.get('http_proxy', 'NONE'))"
        )
    assert result.success
    assert "PROXY= http://127.0.0.1:1" in result.output


def test_no_proxy_blackhole_when_egress_allowed():
    """Trusted policy leaves the proxy env alone."""
    with KernelSandbox(policy=SandboxPolicy(
        timeout_seconds=15,
        network_egress_blocked=False,
        name="trusted",
    )) as sb:
        result = sb.execute_cell(
            "import os\n"
            "print('PROXY=', os.environ.get('http_proxy', 'NONE'))"
        )
    assert result.success
    # Either NONE or whatever the parent had, but not the blackhole sentinel.
    assert "http://127.0.0.1:1" not in result.output


# ---------------------------------------------------------------------------
# Wall-clock timeout → SIGKILL
# ---------------------------------------------------------------------------


def test_timeout_kills_runaway_cell():
    """A cell that runs longer than ``timeout_seconds`` is killed and the
    result carries ``ERR_TIMEOUT`` plus ``killed_reason="timeout"``."""
    with KernelSandbox(policy=SandboxPolicy(timeout_seconds=1)) as sb:
        result = sb.execute_cell("import time; time.sleep(30)")
    assert not result.success
    assert result.error_name == ERR_TIMEOUT, result.error_name
    assert result.killed_reason == "timeout"


# ---------------------------------------------------------------------------
# Network egress: requests/urllib should fail because of the proxy blackhole
# ---------------------------------------------------------------------------


def test_urllib_egress_blocked_by_proxy_blackhole():
    """``urllib.request.urlopen`` should fail when the proxy env points
    at an unroutable address — defeats casual exfiltration."""
    with KernelSandbox(policy=SandboxPolicy(timeout_seconds=15)) as sb:
        result = sb.execute_cell(
            "import urllib.request\n"
            "try:\n"
            "    urllib.request.urlopen('http://example.com', timeout=2)\n"
            "    print('UNEXPECTED_SUCCESS')\n"
            "except Exception as e:\n"
            "    print('BLOCKED:', type(e).__name__)"
        )
    # The kernel itself succeeded (no setrlimit kill). The user code branch
    # caught the network error and printed BLOCKED:.
    assert result.success, result.error_value
    assert "BLOCKED:" in result.output
    assert "UNEXPECTED_SUCCESS" not in result.output


# ---------------------------------------------------------------------------
# Resource limits — these are best-effort because RLIMIT_NPROC is per-user
# (shared with the parent test runner) and RLIMIT_AS depends on platform.
# We only assert that EXTREMELY large allocations are rejected.
# ---------------------------------------------------------------------------


def test_memory_cap_kills_giant_allocation():
    """Allocating well above the policy's memory_mb should fail.

    Note: 1024 MB is the minimum that lets a bare ipykernel start cleanly
    (libpython + ipykernel + zmq need ~400-700 MB of virtual address
    space). We then try to allocate ~2 GB; with RLIMIT_AS enforced the
    allocation raises MemoryError before completing. A previous attempt
    at 512 MB proved RLIMIT_AS is honored — the kernel itself died at
    startup because the cap was below libpython's VAS — but that's not
    a useful test of the user-facing behavior.
    """
    policy = SandboxPolicy(memory_mb=1024, timeout_seconds=20)
    with KernelSandbox(policy=policy) as sb:
        result = sb.execute_cell(
            "try:\n"
            "    x = bytearray(2 * 1024 * 1024 * 1024)  # 2 GB\n"
            "    print('UNEXPECTED_SUCCESS', len(x))\n"
            "except (MemoryError, OverflowError) as e:\n"
            "    print('MEMORY_BLOCKED:', type(e).__name__)\n"
            "except Exception as e:\n"
            "    print('OTHER_ERROR:', type(e).__name__)"
        )
    # The kernel may have died (success=False) OR the allocation may have
    # been caught inside Python (success=True, output contains MEMORY_BLOCKED).
    # Either way, UNEXPECTED_SUCCESS must NOT appear.
    assert "UNEXPECTED_SUCCESS" not in (result.output or "")
