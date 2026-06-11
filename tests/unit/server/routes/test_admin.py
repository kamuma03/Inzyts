"""RBAC enforcement tests for the admin routes.

Confirms ``require_role(UserRole.ADMIN)`` actually blocks non-admins (the
audit flagged these endpoints as untested). DB is mocked, so no database is
needed — the real ``require_role`` dependency runs against an overridden
``verify_token`` returning users of different roles.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User, UserRole

mock_db_session = AsyncMock()


def _user(role: UserRole) -> User:
    return User(
        id=f"{role.value}-id",
        username=f"{role.value}-user",
        is_active=True,
        role=role,
    )


@pytest.fixture
def as_role():
    """Install auth + db overrides for a chosen role, cleaned up after."""

    def _install(role: UserRole):
        fastapi_app.dependency_overrides[verify_token] = lambda: _user(role)
        fastapi_app.dependency_overrides[get_db] = lambda: mock_db_session
        return TestClient(fastapi_app)

    yield _install
    fastapi_app.dependency_overrides.clear()


def test_list_users_forbidden_for_viewer(as_role):
    client = as_role(UserRole.VIEWER)
    resp = client.get("/api/v2/admin/users")
    assert resp.status_code == 403


def test_list_users_forbidden_for_analyst(as_role):
    client = as_role(UserRole.ANALYST)
    resp = client.get("/api/v2/admin/users")
    assert resp.status_code == 403


def test_create_user_forbidden_for_non_admin(as_role):
    client = as_role(UserRole.ANALYST)
    resp = client.post(
        "/api/v2/admin/users",
        json={"username": "newbie", "password": "secret123", "role": "viewer"},
    )
    assert resp.status_code == 403


def test_list_users_allowed_for_admin(as_role):
    # Mock the DB to return one user row.
    row = MagicMock()
    row.id = "u1"
    row.username = "alice"
    row.email = "alice@example.com"
    row.role = UserRole.ANALYST
    row.is_active = True
    row.created_at = datetime.now(timezone.utc)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    mock_db_session.execute = AsyncMock(return_value=result)

    client = as_role(UserRole.ADMIN)
    resp = client.get("/api/v2/admin/users")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["username"] == "alice"
    assert body[0]["role"] == "analyst"
