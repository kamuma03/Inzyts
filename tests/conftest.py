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
