"""OpenAPI contract tests via schemathesis.

FastAPI auto-generates an OpenAPI schema at ``/openapi.json``. Schemathesis
reads that schema and *fuzzes* every endpoint with random-but-conforming
inputs, then asserts a set of standard contract checks:

* ``status_code_conformance`` — only documented status codes returned
* ``content_type_conformance`` — Content-Type matches the spec
* ``response_schema_conformance`` — response body matches the declared
  schema
* ``not_a_server_error`` — no 5xx under any input

Bugs schemathesis routinely catches:
* endpoints that 500 on edge-case inputs (off-by-one, empty arrays, etc.)
* response schemas that drift from the actual response body
* missing or wrong ``required`` fields in request schemas

These tests run against an **in-process** FastAPI app via TestClient — no
separate server needed.

The tests are scoped to public + read-only endpoints to avoid:
* triggering rate limits during fuzzing
* needing real LLM credentials
* making destructive admin calls
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# schemathesis is gated — without it the module skips cleanly.
schemathesis = pytest.importorskip("schemathesis")

from src.server.db.database import get_db
from src.server.db.models import User, UserRole
from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token


# ---------------------------------------------------------------------------
# App harness — auth bypassed, DB stubbed, so schemathesis can actually
# reach handler bodies and exercise their schemas.
# ---------------------------------------------------------------------------


def _stub_db():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.fixture(scope="module", autouse=True)
def _harness():
    # Snapshot the existing dependency_overrides so we restore them on
    # teardown rather than wiping ALL overrides (which would corrupt other
    # test modules' fixtures that may still be active).
    saved = dict(fastapi_app.dependency_overrides)
    fastapi_app.dependency_overrides[verify_token] = lambda: User(
        id="schemathesis", username="fuzz", is_active=True, role=UserRole.ADMIN,
    )
    fastapi_app.dependency_overrides[get_db] = _stub_db
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()
        fastapi_app.dependency_overrides.update(saved)


# ---------------------------------------------------------------------------
# Build the schemathesis schema from the live FastAPI ASGI app.
# ---------------------------------------------------------------------------


schema = schemathesis.openapi.from_asgi("/openapi.json", fastapi_app)


# ---------------------------------------------------------------------------
# Fuzz read-only endpoints
# ---------------------------------------------------------------------------


# Limit to GET endpoints to keep this fast and avoid mutating fixtures.
# Mutating endpoints (POST/PUT/DELETE) need richer scaffolding — they're
# covered by the IDOR / RBAC integration suites instead.
#
# We use a positive list of just ``not_a_server_error`` because:
#   1. The fixture bypasses auth globally for testability — that breaks
#      schemathesis's negative-auth checks (IgnoredAuth /
#      MissingHeaderNotRejected) by construction, not by API bug.
#   2. The "no 5xx under any input" check is the highest-value contract
#      assertion — it catches every endpoint that crashes on edge-case
#      inputs (off-by-one params, missing optional fields, empty arrays).
#
# Future expansion: when we have a real test database that supports
# response_schema_conformance without 401/403 auth bouncing, expand this
# list to include the schema and content-type checks.
from hypothesis import settings, HealthCheck
from schemathesis import checks as _st_checks

_ENABLED_CHECKS = [_st_checks.not_a_server_error]

# Cap fuzz budget per endpoint so the suite finishes in reasonable wall
# time — 8 examples per endpoint × ~20 endpoints = ~160 runs total.
_FUZZ_SETTINGS = settings(
    max_examples=8,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@_FUZZ_SETTINGS
@schema.include(method="GET").parametrize()
def test_get_endpoints_never_500(case):
    """Every documented GET endpoint must NEVER return a 5xx status
    code, no matter what conforming-but-edge-case input is sent.

    A 5xx surfaces uncaught exceptions in the route handler — the most
    common cause of "works in dev, crashes in prod" bugs.

    Budget is intentionally tight (max_examples=8) — the goal is a
    smoke-level contract pin, not exhaustive fuzz. For deeper fuzzing,
    run ``schemathesis run`` against a live deployment.
    """
    case.call_and_validate(checks=_ENABLED_CHECKS)
