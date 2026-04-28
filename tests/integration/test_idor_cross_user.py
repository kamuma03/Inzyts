"""Regression tests for the C-1 fix: per-job endpoints enforce
owner-or-admin access via ``src.server.db.queries.resolve_owned_job``.

Before the fix, every endpoint in ``notebooks.py``, ``reports.py``,
``metrics.py``, and the WebSocket ``join_job`` handler checked auth but
NOT ownership. A viewer-role user could:

* download any analyst's notebook (`/notebooks/{id}/download`)
* read structured cells / conversation history
* execute arbitrary code in another user's live kernel via
  ``/notebooks/{id}/cells/execute``
* join the Socket.IO room for any job and read its log stream

These tests use ``TestClient`` to drive the real FastAPI app with an
overridden auth dependency. We swap the authenticated user between
requests to simulate two different sessions hitting the same job.

The test asserts:

1. The owner can hit each endpoint successfully (200/204/400 — i.e. no
   ownership rejection).
2. A non-admin user with a different ``id`` gets **404** on the same
   request (we deliberately use 404 not 403 to avoid id enumeration).
3. An admin can hit any endpoint regardless of ownership.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import nbformat
import pytest
from fastapi.testclient import TestClient

from src.server.db.database import get_db
from src.server.db.models import Job, User, UserRole
from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token


# ---------------------------------------------------------------------------
# Auth + DB scaffolding
# ---------------------------------------------------------------------------


_OWNER_ID = "owner-uuid"
_OTHER_ID = "other-uuid"


def _user(uid: str, role: UserRole = UserRole.ANALYST) -> User:
    return User(id=uid, username=f"user-{uid}", is_active=True, role=role)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def owned_job(tmp_path):
    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_markdown_cell("# Owned"))
    path = tmp_path / "owned.ipynb"
    nbformat.write(nb, str(path))
    job = MagicMock(spec=Job)
    job.id = "job-owned"
    job.user_id = _OWNER_ID
    job.result_path = str(path)
    job.csv_path = None
    job.mode = "exploratory"
    job.title = "Owned analysis"
    job.question = "what?"
    job.executive_summary = None
    return job


@pytest.fixture
def auth_as():
    """Returns a helper to switch the authenticated user on demand."""
    def _set(user: User):
        fastapi_app.dependency_overrides[verify_token] = lambda: user
    yield _set
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def db_returning(mock_db, owned_job, tmp_path):
    """Wire the DB dependency to return ``owned_job`` for any select()."""
    fastapi_app.dependency_overrides[get_db] = lambda: mock_db
    result = MagicMock()
    result.scalar_one_or_none.return_value = owned_job
    mock_db.execute = AsyncMock(return_value=result)

    # Also patch _OUTPUT_DIR so the path-traversal guard accepts notebooks
    # under tmp_path (used by the downstream notebook routes).
    p1 = patch("src.server.routes.notebooks._OUTPUT_DIR", tmp_path)
    p2 = patch("src.server.routes.reports._OUTPUT_DIR", tmp_path)
    p1.start()
    p2.start()
    yield mock_db
    p1.stop()
    p2.stop()


@pytest.fixture
def client():
    return TestClient(fastapi_app)


# ---------------------------------------------------------------------------
# Endpoints under test — owner can read
# ---------------------------------------------------------------------------


_OWNER_GETS = [
    "/api/v2/notebooks/job-owned/html",
    "/api/v2/notebooks/job-owned/download",
    "/api/v2/notebooks/job-owned/cells",
    "/api/v2/notebooks/job-owned/conversation",
    "/api/v2/reports/job-owned/executive-summary",
    "/api/v2/reports/job-owned/pii-scan",
    "/api/v2/reports/job-owned/export?format=html",
]


@pytest.mark.parametrize("path", _OWNER_GETS)
def test_owner_can_read_their_own_job(client, auth_as, db_returning, path):
    """Owner of a job must be able to read every per-job endpoint.

    We don't assert exactly 200 for every endpoint because some require
    additional setup (e.g. report export needs the exporter). We only
    assert NOT 404 — the ownership guard didn't block."""
    auth_as(_user(_OWNER_ID))

    # /conversation needs the second select to return an empty list.
    if path.endswith("/conversation"):
        # First execute returns the job, second returns the messages.
        history = MagicMock()
        history.scalars.return_value.all.return_value = []
        first = MagicMock()
        first.scalar_one_or_none.return_value = db_returning  # placeholder
        # Reset side effect — execute is hit twice in /conversation.
        db_returning.execute = AsyncMock(side_effect=[
            _make_result(db_returning_job=True),
            history,
        ])

    response = client.get(path)
    # Ownership guard should not reject. Real handler may still 5xx for
    # mock-related reasons (e.g. report exporter not initialised); we
    # only check that the rejection-by-404 path didn't fire.
    assert response.status_code != 404, (
        f"Owner got 404 on {path}: {response.text}"
    )


# Helper since /conversation calls execute twice.
def _make_result(db_returning_job: bool):
    r = MagicMock()
    r.scalar_one_or_none.return_value = MagicMock(spec=Job, user_id=_OWNER_ID)
    return r


# ---------------------------------------------------------------------------
# Endpoints under test — non-owner gets 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _OWNER_GETS)
def test_non_owner_gets_404(client, auth_as, db_returning, path):
    """A different authenticated user (NOT admin) hitting the same job
    must receive 404 — not 403, not 200, not 5xx. 404 prevents id
    enumeration; 403 would leak existence."""
    auth_as(_user(_OTHER_ID))  # different user, same analyst role

    response = client.get(path)
    assert response.status_code == 404, (
        f"Non-owner viewing {path} got {response.status_code} — IDOR regression "
        f"or wrong status code. Body: {response.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Admin bypass
# ---------------------------------------------------------------------------


def test_admin_can_read_any_job(client, auth_as, db_returning):
    """Admins must bypass the ownership check (mirrors REST behaviour for
    the audit logs / user mgmt routes)."""
    auth_as(_user("admin-uuid", role=UserRole.ADMIN))

    response = client.get("/api/v2/notebooks/job-owned/cells")
    # Could be 200 or 5xx (notebook IO mocked imperfectly), but MUST NOT
    # be 404 — admins bypass ownership.
    assert response.status_code != 404, (
        f"Admin got 404 on owned job — admin bypass regression"
    )


# ---------------------------------------------------------------------------
# Mutating endpoints — non-owner POSTs also get 404
# ---------------------------------------------------------------------------


_NON_OWNER_POSTS = [
    ("/api/v2/notebooks/job-owned/cells/execute", {"code": "print(1)"}),
    ("/api/v2/notebooks/job-owned/cells/restart", None),
    ("/api/v2/notebooks/job-owned/cells/interrupt", None),
    (
        "/api/v2/notebooks/job-owned/cells/edit",
        {"cell_index": 0, "current_code": "x", "instruction": "do it"},
    ),
    ("/api/v2/notebooks/job-owned/ask", {"question": "why?"}),
]


@pytest.mark.parametrize("path,body", _NON_OWNER_POSTS)
def test_non_owner_cannot_mutate_others_job(
    client, auth_as, db_returning, path, body
):
    """The most dangerous IDOR — execute arbitrary code in another user's
    kernel. A non-owner POST to any of these mutation endpoints must 404."""
    auth_as(_user(_OTHER_ID))

    if body is None:
        response = client.post(path)
    else:
        response = client.post(path, json=body)

    assert response.status_code == 404, (
        f"Non-owner POST to {path} got {response.status_code} — IDOR "
        f"regression. Body: {response.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Legacy NULL user_id jobs are admin-only
# ---------------------------------------------------------------------------


def test_legacy_null_user_id_jobs_invisible_to_non_admin(client, auth_as, mock_db):
    """Jobs created before the ``user_id`` column was added have NULL
    user_id. The ownership helper treats those as admin-only — non-admins
    see them as 404 (matching the list-query filter behaviour)."""
    legacy = MagicMock(spec=Job)
    legacy.id = "job-legacy"
    legacy.user_id = None
    legacy.result_path = "/output/legacy.ipynb"

    fastapi_app.dependency_overrides[get_db] = lambda: mock_db
    result = MagicMock()
    result.scalar_one_or_none.return_value = legacy
    mock_db.execute = AsyncMock(return_value=result)

    auth_as(_user(_OTHER_ID))  # any non-admin
    response = client.get("/api/v2/notebooks/job-legacy/cells")
    assert response.status_code == 404
