"""Regression tests for the H-3 fix: ``/analyze``, ``/files/upload``, and
``/files/upload_batch`` require Analyst+ role.

Before the fix the README claimed these required Analyst+ but the code
just used ``verify_token``, so any authenticated user (including a
viewer) could:

* spend LLM budget by starting analyses,
* upload files to the worker's filesystem,
* fill the audit log with their actions.

These tests verify the documented contract by issuing real HTTP requests
through ``TestClient`` with three different role contexts (viewer,
analyst, admin) and checking the response status:

* viewer: 403 Forbidden
* analyst: NOT 403 (request reaches the handler — may still 4xx for
  unrelated reasons but the role gate is the contract under test)
* admin: NOT 403 (admins inherit analyst-level permissions)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.server.db.database import get_db
from src.server.db.models import User, UserRole
from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def client(db):
    fastapi_app.dependency_overrides[get_db] = lambda: db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def _set_user(role: UserRole) -> None:
    fastapi_app.dependency_overrides[verify_token] = lambda: User(
        id=f"user-{role.value}",
        username=f"u-{role.value}",
        is_active=True,
        role=role,
    )


# ---------------------------------------------------------------------------
# /analyze — POST
# ---------------------------------------------------------------------------


# Payload with no data source — handler returns 400 ("must provide at least one
# data source"). We pick this rather than ``csv_path: '/no/such/file.csv'`` so
# the path-traversal guard (which also returns 403!) doesn't shadow the RBAC
# check we're trying to verify.
_NO_SOURCE_PAYLOAD = {
    "mode": "exploratory",
    "question": "what?",
}


def test_analyze_rejects_viewer(client):
    """Viewer-role JWT must not reach the /analyze handler.

    The README and SECURITY.md document this as Analyst+. A regression
    here means viewer-role users can spend LLM budget on the platform.
    """
    _set_user(UserRole.VIEWER)
    response = client.post("/api/v2/analyze", json=_NO_SOURCE_PAYLOAD)
    assert response.status_code == 403, (
        f"Viewer hitting /analyze got {response.status_code} — H-3 regression. "
        f"Body: {response.text[:200]}"
    )


def test_analyze_allows_analyst(client):
    """Analyst-role JWT must reach the handler.

    The handler may then return 400 (file not found) or 5xx (mocked DB) —
    we don't care, we're verifying the role gate doesn't block."""
    _set_user(UserRole.ANALYST)
    response = client.post("/api/v2/analyze", json=_NO_SOURCE_PAYLOAD)
    assert response.status_code != 403, (
        f"Analyst was blocked at /analyze (got 403) — H-3 misconfigured."
    )


def test_analyze_allows_admin(client):
    """Admins inherit analyst-level access via the role hierarchy."""
    _set_user(UserRole.ADMIN)
    response = client.post("/api/v2/analyze", json=_NO_SOURCE_PAYLOAD)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# /files/upload — POST multipart
# ---------------------------------------------------------------------------


def _post_upload(client):
    return client.post(
        "/api/v2/files/upload",
        files={"file": ("test.csv", b"a,b\n1,2\n", "text/csv")},
    )


def test_upload_rejects_viewer(client):
    """File uploads write to the worker's filesystem and consume disk —
    viewers must not be able to do this."""
    _set_user(UserRole.VIEWER)
    response = _post_upload(client)
    assert response.status_code == 403


def test_upload_allows_analyst(client, tmp_path):
    """Analysts can upload."""
    _set_user(UserRole.ANALYST)
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = _post_upload(client)
    assert response.status_code != 403


def test_upload_allows_admin(client, tmp_path):
    """Admins can upload."""
    _set_user(UserRole.ADMIN)
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = _post_upload(client)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# /files/upload_batch — POST multipart with multiple files
# ---------------------------------------------------------------------------


def _post_upload_batch(client):
    files = [
        ("files", ("a.csv", b"a,b\n1,2\n", "text/csv")),
        ("files", ("b.csv", b"c,d\n3,4\n", "text/csv")),
    ]
    return client.post("/api/v2/files/upload_batch", files=files)


def test_upload_batch_rejects_viewer(client):
    """Batch upload is the same threat surface as single upload — same
    role requirement."""
    _set_user(UserRole.VIEWER)
    response = _post_upload_batch(client)
    assert response.status_code == 403


def test_upload_batch_allows_analyst(client, tmp_path):
    _set_user(UserRole.ANALYST)
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = _post_upload_batch(client)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Negative: viewer-OK endpoints stay open to viewers
# ---------------------------------------------------------------------------


def test_viewer_can_call_suggest_mode(client):
    """`/suggest-mode` is a viewer-OK endpoint (read-only inference). The
    H-3 fix tightened only the mutating routes — make sure we didn't
    accidentally tighten too much."""
    _set_user(UserRole.VIEWER)
    response = client.post(
        "/api/v2/suggest-mode",
        json={"question": "predict churn", "target_column": "Churn"},
    )
    assert response.status_code != 403


def test_viewer_can_get_auth_me(client):
    """`/auth/me` returns the viewer's own profile — no role gate."""
    _set_user(UserRole.VIEWER)
    response = client.get("/api/v2/auth/me")
    assert response.status_code == 200
