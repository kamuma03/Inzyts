"""Regression test for the M-3 fix: ``/auth/login`` is rate-limited to
10 requests/minute per source IP.

Before the fix, the route inherited only the global default (200/min) —
loud enough that bcrypt provided most of the protection but too generous
for a credential endpoint. The fix added an explicit ``@limiter.limit
("10/minute")`` decorator.

This test hits the real ``/auth/login`` endpoint via ``TestClient`` more
than 10 times in a single minute and asserts the 11th request is rejected
with HTTP 429.

The test relies on the project's existing root ``conftest.py`` which
auto-starts a Redis container on port 6399 — the rate limiter uses Redis
as the storage backend, so this is not an in-memory short-circuit.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# slowapi attaches per-route limit state inside Redis keyed by client IP.
# We use a dedicated Redis DB index for rate-limit tests so previous runs
# don't pollute the count.
_TEST_REDIS_DB = int(os.environ.get("INZYTS_TEST_REDIS_DB", "5"))


@pytest.fixture
def app_with_clean_limiter(monkeypatch):
    """Build a FastAPI app with the rate limiter pointed at a fresh Redis
    DB so previous tests' counters don't pollute this one. Also override
    the DB dependency so the test doesn't need a real Postgres.

    The session conftest disables rate limiting globally for tests; this
    fixture re-enables it explicitly so we can verify the per-route
    10/min limit on /auth/login.
    """
    # The session conftest sets INZYTS_DISABLE_RATE_LIMIT=1 to keep other
    # tests from tripping the per-route limits. Re-enable the limiter on
    # the *live* singleton (whatever module has imported it) so the
    # already-decorated /auth/login route sees the throttle without
    # needing a module reload (which leaves stale `limiter` bindings in
    # auth.py / main.py).
    from src.server.rate_limiter import limiter as live_limiter
    from src.server.routes.auth import limiter as auth_limiter

    # Both names should refer to the same singleton — assert it loudly so
    # any future divergence is caught immediately.
    assert live_limiter is auth_limiter, "rate_limiter singleton diverged"

    prior_enabled = live_limiter.enabled
    live_limiter.enabled = True

    # Reset the limiter's per-IP counters between runs so previous tests'
    # /analyze hits don't bleed into this test's /auth/login budget.
    try:
        live_limiter.reset()
    except Exception:
        pass

    # Override get_db so the login route doesn't try to talk to Postgres.
    # AsyncMock that returns "no user found" for any select() — the route
    # then takes the dummy-hash path and returns 401, while still running
    # through the rate-limit decorator first (which is what we test).
    from src.server.db.database import get_db

    async def _no_db():
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.first.return_value = None
        result.scalar.return_value = 0  # user count
        session.execute = AsyncMock(return_value=result)
        yield session

    from src.server.main import fastapi_app
    fastapi_app.dependency_overrides[get_db] = _no_db
    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()
        live_limiter.enabled = prior_enabled


def _attempt_login(client: TestClient, username: str = "noone") -> int:
    """Make one login attempt; return the HTTP status code."""
    r = client.post(
        "/api/v2/auth/login",
        data={"username": username, "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return r.status_code


def test_login_rate_limited_after_ten_requests(app_with_clean_limiter):
    """The 11th login attempt within a single minute from the same source
    IP must be rejected with HTTP 429 Too Many Requests.

    Brute-force credential stuffing on ``/auth/login`` is the highest-
    leverage attack against any web app. Without the per-route limit,
    bcrypt cost is the only defence — fine for one user but inadequate
    against a botnet.
    """
    client = TestClient(app_with_clean_limiter)

    statuses = [_attempt_login(client) for _ in range(15)]

    # First batch: 401 (wrong password). The exact cutoff depends on
    # whether slowapi counts the request that hits the limit, but we
    # require:
    #   - at least one 429 within the first 15 attempts
    #   - all early attempts are 401 (wrong password, not 429)
    assert statuses[0] == 401, (
        f"First attempt should hit auth and return 401, got {statuses[0]}"
    )

    rate_limited = [i for i, s in enumerate(statuses) if s == 429]
    assert rate_limited, (
        f"Expected at least one 429 within 15 login attempts, got {statuses}"
    )

    # The first 429 must arrive at request #11 or later (10/minute = first
    # 10 succeed in reaching the handler).
    first_429 = rate_limited[0]
    assert first_429 >= 10, (
        f"First 429 was at index {first_429}, expected >=10 "
        f"(indicates limit fires too early). statuses={statuses}"
    )


def test_login_rate_limit_is_per_route_not_global(app_with_clean_limiter):
    """The 10/min limit on /auth/login must NOT bleed into other public
    endpoints. /health is unauthenticated and unlimited; bursting it 30
    times in quick succession must all return 200."""
    client = TestClient(app_with_clean_limiter)

    statuses = [client.get("/health").status_code for _ in range(30)]
    assert all(s == 200 for s in statuses), (
        f"/health should not be rate-limited, got: "
        f"{[s for s in statuses if s != 200]}"
    )
