"""Conftest for the contracts/ test suite.

Two adjustments relative to the root conftest:

1. **Opts out of the ``_snapshot_dependency_overrides`` autouse fixture**
   because the contracts harness manages overrides at module scope.

2. **Replaces the FastAPI lifespan with a no-op** so the schemathesis
   tests don't try to connect to a real Postgres on every run. Without
   this, the lifespan retries the DB 15 times × 2s = 30s per test ×
   19 tests = ~10 minutes of pure DB-retry timeout.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


@pytest.fixture(autouse=True)
def _snapshot_dependency_overrides():
    """No-op override — the contracts harness manages overrides itself."""
    yield


@pytest.fixture(autouse=True, scope="session")
def _disable_fastapi_lifespan():
    """Replace the app's lifespan with a no-op so schemathesis can fuzz
    without triggering the real DB-connection retry loop.

    Schemathesis's ``from_asgi`` shim drives the ASGI lifecycle, including
    the lifespan startup/shutdown events. Our production lifespan tries
    to connect to Postgres and retries 15 times — fine in production,
    catastrophic for fast unit-style fuzzing in CI.
    """
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    from src.server.main import fastapi_app
    original = fastapi_app.router.lifespan_context
    fastapi_app.router.lifespan_context = _noop_lifespan
    try:
        yield
    finally:
        fastapi_app.router.lifespan_context = original
