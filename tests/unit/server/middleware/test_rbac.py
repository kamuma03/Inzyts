import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.server.middleware.auth import (
    require_role,
    verify_token,
    ROLE_HIERARCHY,
)
from src.server.db.models import User, UserRole


# ---------------------------------------------------------------------------
# ROLE_HIERARCHY sanity
# ---------------------------------------------------------------------------

def test_role_hierarchy_ordering():
    assert ROLE_HIERARCHY[UserRole.ADMIN] > ROLE_HIERARCHY[UserRole.ANALYST]
    assert ROLE_HIERARCHY[UserRole.ANALYST] > ROLE_HIERARCHY[UserRole.VIEWER]


# ---------------------------------------------------------------------------
# require_role — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_role_admin_passes():
    """Admin user passes an admin-only check."""
    admin_user = User(id="1", username="admin", is_active=True, role=UserRole.ADMIN)
    checker = require_role(UserRole.ADMIN)
    result = await checker(user=admin_user)
    assert result.username == "admin"


@pytest.mark.asyncio
async def test_require_role_admin_hierarchy():
    """Admin user passes an analyst-level check (hierarchy)."""
    admin_user = User(id="1", username="admin", is_active=True, role=UserRole.ADMIN)
    checker = require_role(UserRole.ANALYST)
    result = await checker(user=admin_user)
    assert result.username == "admin"


@pytest.mark.asyncio
async def test_require_role_viewer_denied_admin():
    """Viewer user fails an admin-only check → 403."""
    viewer_user = User(id="2", username="viewer", is_active=True, role=UserRole.VIEWER)
    checker = require_role(UserRole.ADMIN)
    with pytest.raises(HTTPException) as excinfo:
        await checker(user=viewer_user)
    assert excinfo.value.status_code == 403
    assert "Insufficient permissions" in excinfo.value.detail


@pytest.mark.asyncio
async def test_require_role_analyst_denied_admin():
    """Analyst user fails an admin-only check → 403."""
    analyst_user = User(id="3", username="analyst", is_active=True, role=UserRole.ANALYST)
    checker = require_role(UserRole.ADMIN)
    with pytest.raises(HTTPException) as excinfo:
        await checker(user=analyst_user)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_analyst_passes_analyst():
    """Analyst user passes an analyst-level check."""
    analyst_user = User(id="3", username="analyst", is_active=True, role=UserRole.ANALYST)
    checker = require_role(UserRole.ANALYST)
    result = await checker(user=analyst_user)
    assert result.username == "analyst"


@pytest.mark.asyncio
async def test_require_role_viewer_passes_viewer():
    """Viewer user passes a viewer-level check."""
    viewer_user = User(id="2", username="viewer", is_active=True, role=UserRole.VIEWER)
    checker = require_role(UserRole.VIEWER)
    result = await checker(user=viewer_user)
    assert result.username == "viewer"


@pytest.mark.asyncio
async def test_require_role_no_role_defaults_viewer():
    """User with no role attribute defaults to viewer level."""
    user = User(id="4", username="noflag", is_active=True)
    # If role column is None (e.g., old row), should default to viewer
    user.role = None  # type: ignore
    checker = require_role(UserRole.VIEWER)
    result = await checker(user=user)
    assert result.username == "noflag"


# ---------------------------------------------------------------------------
# check_system_token includes admin role
# ---------------------------------------------------------------------------

@patch("src.server.middleware.auth.settings")
def test_system_token_has_admin_role(mock_settings):
    from src.server.middleware.auth import check_system_token
    mock_settings.api_token = "sys_token"
    user = check_system_token("sys_token")
    assert user is not None
    assert user.role == UserRole.ADMIN


# ---------------------------------------------------------------------------
# verify_token sets request.state.audit_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.middleware.auth.verify_token_async", new_callable=AsyncMock)
async def test_verify_token_sets_audit_user(mock_verify_async):
    """verify_token stashes the user on request.state for audit middleware."""
    fake_user = User(id="1", username="alice", is_active=True, role=UserRole.ANALYST)
    mock_verify_async.return_value = fake_user
    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="good_token")

    # Create a mock request with state
    mock_request = MagicMock()
    mock_request.state = MagicMock()

    result = await verify_token(request=mock_request, credentials=credentials, db=mock_db)
    assert result.username == "alice"
    assert mock_request.state.audit_user == fake_user
