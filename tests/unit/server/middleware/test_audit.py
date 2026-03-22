import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.server.middleware.audit import (
    record_audit,
    _classify_action,
    _client_ip,
)


# ---------------------------------------------------------------------------
# _classify_action
# ---------------------------------------------------------------------------

def test_classify_action_login():
    assert _classify_action("POST", "/api/v2/auth/login") == "login"


def test_classify_action_upload():
    assert _classify_action("POST", "/api/v2/files/upload") == "upload_file"


def test_classify_action_analyze():
    assert _classify_action("POST", "/api/v2/analyze") == "start_analysis"


def test_classify_action_cancel():
    assert _classify_action("POST", "/api/v2/jobs/abc123/cancel") == "cancel_job"


def test_classify_action_create_user():
    assert _classify_action("POST", "/api/v2/admin/users") == "create_user"


def test_classify_action_update_user():
    assert _classify_action("PUT", "/api/v2/admin/users/123") == "update_user"


def test_classify_action_delete_user():
    assert _classify_action("DELETE", "/api/v2/admin/users/123") == "delete_user"


def test_classify_action_list_users():
    assert _classify_action("GET", "/api/v2/admin/users") == "list_users"


def test_classify_action_audit_logs():
    assert _classify_action("GET", "/api/v2/admin/audit-logs") == "view_audit_logs"


def test_classify_action_fallback():
    result = _classify_action("GET", "/api/v2/some/path")
    assert result == "get_path"


# ---------------------------------------------------------------------------
# _client_ip
# ---------------------------------------------------------------------------

def test_client_ip_forwarded():
    request = MagicMock()
    request.headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
    # Direct client must be a trusted proxy for X-Forwarded-For to be used
    request.client.host = "127.0.0.1"
    assert _client_ip(request) == "1.2.3.4"


def test_client_ip_direct():
    request = MagicMock()
    request.headers = {}
    request.client.host = "127.0.0.1"
    assert _client_ip(request) == "127.0.0.1"


def test_client_ip_no_client():
    request = MagicMock()
    request.headers = {}
    request.client = None
    assert _client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# record_audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.middleware.audit.async_session_maker")
async def test_record_audit_persists_entry(mock_session_maker):
    """record_audit creates a session, adds an AuditLog, and commits."""
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    from src.server.db.models import User
    fake_user = User(id="u1", username="testuser", is_active=True)

    await record_audit(
        action="login",
        user=fake_user,
        ip_address="10.0.0.1",
        status_code=200,
    )

    mock_session.add.assert_called_once()
    added_obj = mock_session.add.call_args[0][0]
    assert added_obj.action == "login"
    assert added_obj.user_id == "u1"
    assert added_obj.username == "testuser"
    assert added_obj.ip_address == "10.0.0.1"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.server.middleware.audit.async_session_maker")
async def test_record_audit_handles_db_error(mock_session_maker):
    """record_audit silently handles DB errors (never breaks request flow)."""
    # Make the context manager itself raise
    cm = AsyncMock()
    cm.__aenter__.side_effect = Exception("DB down")
    mock_session_maker.return_value = cm

    # Should NOT raise
    await record_audit(action="login", username="test")
