"""
Root conftest — starts a Redis container for integration tests that hit
rate-limited FastAPI routes.

Redis is started at collection time (before test modules are imported)
so that the rate limiter, which connects lazily on first request,
finds a live Redis instance.
"""

import os
import socket
import subprocess
import time
import atexit

_REDIS_PORT = 6399  # Non-default port to avoid collisions
_REDIS_URL = f"redis://localhost:{_REDIS_PORT}/0"
_CONTAINER_NAME = "inzyts-test-redis"


def _port_open(port: int, timeout: float = 1.0) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("localhost", port))
        sock.close()
        return True
    except (OSError, socket.error):
        return False


def _ensure_redis() -> None:
    """Start a Redis Docker container if one isn't already running."""
    if _port_open(_REDIS_PORT):
        return

    subprocess.run(["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True)
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", _CONTAINER_NAME,
            "-p", f"{_REDIS_PORT}:6379",
            "redis:7-alpine",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return  # Docker unavailable; tests will fail with a clear Redis error

    # Wait up to 10s for Redis to accept connections
    for _ in range(20):
        if _port_open(_REDIS_PORT):
            atexit.register(
                lambda: subprocess.run(
                    ["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True
                )
            )
            return
        time.sleep(0.5)


# Start Redis and point the REDIS_URL env var at it BEFORE any app code is imported.
# The rate_limiter module reads REDIS_URL at import time.
_ensure_redis()
os.environ.setdefault("REDIS_URL", _REDIS_URL)


# ---------------------------------------------------------------------------
# Test-isolation safety net for FastAPI ``dependency_overrides``.
# ---------------------------------------------------------------------------
#
# Many test files set per-test overrides via ``app.dependency_overrides[...]``
# and reset them in teardown via ``app.dependency_overrides.clear()``. The
# ``clear()`` pattern wipes EVERYTHING, including overrides set by
# session-scoped fixtures or other concurrently-active test fixtures —
# producing flaky cross-suite failures when running ``pytest tests/``.
#
# The fixture below snapshots the baseline state at session start and
# restores it after each test, so a misbehaving ``clear()`` only affects
# the current test rather than leaking into the rest of the suite.

import pytest


@pytest.fixture(autouse=True)
def _snapshot_dependency_overrides():
    """Snapshot fastapi_app.dependency_overrides before each test and
    restore the snapshot on teardown.

    Runs autouse so individual test files don't need to opt in. Imports
    inside the fixture so we don't pay the FastAPI app-load cost during
    pytest collection (only during fixture setup of tests that touch
    HTTP routes — others see a no-op).
    """
    try:
        from src.server.main import fastapi_app
    except Exception:
        # Pure-Python tests that don't import the FastAPI app should
        # still work — the safety net is a no-op for them.
        yield
        return

    saved = dict(fastapi_app.dependency_overrides)
    try:
        yield
    finally:
        # Whatever the test (or its fixture's teardown) did to overrides,
        # snap back to the pre-test state. This is a belt-and-braces
        # complement to per-file fixtures that already clear().
        fastapi_app.dependency_overrides.clear()
        fastapi_app.dependency_overrides.update(saved)
