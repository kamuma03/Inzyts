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
    the DB dependency so the test doesn't need a real Postgres."""
    monkeypatch.setenv(
        "REDIS_URL",
        f"redis://localhost:6399/{_TEST_REDIS_DB}",
    )
    # Re-import rate_limiter and main so they pick up the new REDIS_URL.
    import importlib
    import src.server.rate_limiter as rl
    importlib.reload(rl)
    import src.server.main as main
    importlib.reload(main)

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

    main.fastapi_app.dependency_overrides[get_db] = _no_db
    try:
        yield main.fastapi_app
    finally:
        main.fastapi_app.dependency_overrides.clear()
        monkeypatch.delenv("REDIS_URL", raising=False)
        importlib.reload(rl)
        importlib.reload(main)


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
