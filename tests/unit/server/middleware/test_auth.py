import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.server.middleware.auth import (
    verify_token,
    verify_token_sync,
    verify_token_async,
    verify_password,
    get_password_hash,
    create_access_token,
    check_system_token,
    decode_token,
)
from src.server.db.models import User


# ---------------------------------------------------------------------------
# verify_token (async FastAPI dependency)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_token_no_credentials():
    """No credentials at all → 401."""
    mock_db = AsyncMock()
    mock_request = MagicMock()
    with pytest.raises(HTTPException) as excinfo:
        await verify_token(request=mock_request, credentials=None, db=mock_db)
    assert excinfo.value.status_code == 401
    assert "No credentials provided" in excinfo.value.detail


@pytest.mark.asyncio
@patch("src.server.middleware.auth.verify_token_async", new_callable=AsyncMock)
async def test_verify_token_invalid_token(mock_verify_async):
    """Token present but invalid → 401."""
    mock_verify_async.return_value = None
    mock_db = AsyncMock()
    mock_request = MagicMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad_token")

    with pytest.raises(HTTPException) as excinfo:
        await verify_token(request=mock_request, credentials=credentials, db=mock_db)
    assert excinfo.value.status_code == 401
    assert "Could not validate credentials" in excinfo.value.detail


@pytest.mark.asyncio
@patch("src.server.middleware.auth.verify_token_async", new_callable=AsyncMock)
async def test_verify_token_valid_token(mock_verify_async):
    """Valid token → returns User object."""
    fake_user = User(id=1, username="alice", is_active=True)
    mock_verify_async.return_value = fake_user
    mock_db = AsyncMock()
    mock_request = MagicMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="good_token")

    result = await verify_token(request=mock_request, credentials=credentials, db=mock_db)
    assert result.username == "alice"
    mock_verify_async.assert_awaited_once_with("good_token", mock_db)


# ---------------------------------------------------------------------------
# verify_token_sync
# ---------------------------------------------------------------------------

@patch("src.server.middleware.auth.settings")
def test_verify_token_sync_system_token_valid(mock_settings):
    """System API token matches → returns User-like object."""
    mock_settings.api_token = "sys_secret"
    result = verify_token_sync("sys_secret")
    assert result is not None
    assert result.username == "system"


@patch("src.server.middleware.auth.settings")
def test_verify_token_sync_no_match_no_db(mock_settings):
    """Token doesn't match system token and no DB → None."""
    mock_settings.api_token = "sys_secret"
    mock_settings.jwt_secret_key = "test_key"
    mock_settings.jwt_algorithm = "HS256"
    result = verify_token_sync("random_garbage")
    assert result is None


@patch("src.server.middleware.auth.settings")
def test_verify_token_sync_jwt_with_db(mock_settings):
    """Valid JWT + DB session → returns user from DB."""
    mock_settings.api_token = ""
    mock_settings.jwt_secret_key = "test_key"
    mock_settings.jwt_algorithm = "HS256"

    token = create_access_token({"sub": "bob"})

    fake_user = User(id=2, username="bob", is_active=True)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = fake_user

    result = verify_token_sync(token, db=mock_db)
    assert result is not None
    assert result.username == "bob"


# ---------------------------------------------------------------------------
# check_system_token
# ---------------------------------------------------------------------------

@patch("src.server.middleware.auth.settings")
def test_check_system_token_match(mock_settings):
    mock_settings.api_token = "the_token"
    user = check_system_token("the_token")
    assert user is not None
    assert user.username == "system"


@patch("src.server.middleware.auth.settings")
def test_check_system_token_no_match(mock_settings):
    mock_settings.api_token = "the_token"
    assert check_system_token("wrong") is None


@patch("src.server.middleware.auth.settings")
def test_check_system_token_none_configured(mock_settings):
    mock_settings.api_token = None
    assert check_system_token("anything") is None


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------

@patch("src.server.middleware.auth.settings")
def test_decode_token_valid(mock_settings):
    mock_settings.jwt_secret_key = "secret"
    mock_settings.jwt_algorithm = "HS256"
    token = create_access_token({"sub": "testuser"})
    assert decode_token(token) == "testuser"


@patch("src.server.middleware.auth.settings")
def test_decode_token_invalid(mock_settings):
    mock_settings.jwt_secret_key = "secret"
    mock_settings.jwt_algorithm = "HS256"
    assert decode_token("not.a.jwt") is None


# ---------------------------------------------------------------------------
# verify_password / get_password_hash
# ---------------------------------------------------------------------------

def test_password_hash_roundtrip():
    hashed = get_password_hash("my_password")
    assert verify_password("my_password", hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_bad_hash():
    """Malformed hash → returns False, doesn't crash."""
    assert verify_password("anything", "not_a_valid_bcrypt_hash") is False


# ---------------------------------------------------------------------------
# verify_token_async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.middleware.auth.settings")
async def test_verify_token_async_system_token(mock_settings):
    mock_settings.api_token = "sys"
    mock_db = AsyncMock()
    user = await verify_token_async("sys", mock_db)
    assert user is not None
    assert user.username == "system"


@pytest.mark.asyncio
@patch("src.server.middleware.auth.settings")
async def test_verify_token_async_jwt_user(mock_settings):
    mock_settings.api_token = ""
    mock_settings.jwt_secret_key = "k"
    mock_settings.jwt_algorithm = "HS256"

    token = create_access_token({"sub": "charlie"})

    fake_user = User(id=3, username="charlie", is_active=True)
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    user = await verify_token_async(token, mock_db)
    assert user.username == "charlie"


@pytest.mark.asyncio
@patch("src.server.middleware.auth.settings")
async def test_verify_token_async_inactive_user(mock_settings):
    mock_settings.api_token = ""
    mock_settings.jwt_secret_key = "k"
    mock_settings.jwt_algorithm = "HS256"

    token = create_access_token({"sub": "inactive"})

    fake_user = User(id=4, username="inactive", is_active=False)
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    user = await verify_token_async(token, mock_db)
    assert user is None
