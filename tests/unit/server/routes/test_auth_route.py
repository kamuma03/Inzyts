"""
Tests for the auth login endpoint (src/server/routes/auth.py).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status

from src.server.routes.auth import router, login_for_access_token
from src.server.db.models import User


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_request():
    req = MagicMock()
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


@pytest.fixture
def mock_form():
    form = MagicMock()
    form.username = "admin"
    form.password = "admin_password"
    return form


@pytest.fixture
def fake_user():
    from src.server.middleware.auth import get_password_hash
    from src.server.db.models import UserRole
    return User(
        id="user-1",
        username="admin",
        hashed_password=get_password_hash("admin_password"),
        is_active=True,
        role=UserRole.ADMIN,
    )


# ---------------------------------------------------------------------------
# Successful login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.routes.auth.record_audit", new_callable=AsyncMock)
@patch("src.server.routes.auth.settings")
@patch("src.server.routes.auth.create_access_token", return_value="fake_jwt_token")
async def test_login_success(mock_create_token, mock_settings, mock_audit, mock_db, mock_request, mock_form, fake_user):
    mock_settings.jwt_access_token_expire_minutes = 30

    # Simulate user found in DB
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    response = await login_for_access_token(request=mock_request, form_data=mock_form, db=mock_db)

    assert response["access_token"] == "fake_jwt_token"
    assert response["token_type"] == "bearer"
    assert response["role"] == "admin"
    assert response["username"] == "admin"


# ---------------------------------------------------------------------------
# Invalid password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.routes.auth.record_audit", new_callable=AsyncMock)
@patch("src.server.routes.auth.settings")
async def test_login_wrong_password(mock_settings, mock_audit, mock_db, mock_request, fake_user):
    mock_settings.admin_username = "admin"

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    form = MagicMock()
    form.username = "admin"
    form.password = "wrong_password"

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await login_for_access_token(request=mock_request, form_data=form, db=mock_db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# User not found (and not first boot)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.routes.auth.record_audit", new_callable=AsyncMock)
@patch("src.server.routes.auth.settings")
async def test_login_user_not_found(mock_settings, mock_audit, mock_db, mock_request):
    mock_settings.admin_username = "admin"

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    form = MagicMock()
    form.username = "nonexistent_user"
    form.password = "whatever"

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await login_for_access_token(request=mock_request, form_data=form, db=mock_db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# First boot auto-creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.routes.auth.record_audit", new_callable=AsyncMock)
@patch("src.server.routes.auth.settings")
@patch("src.server.routes.auth.create_access_token", return_value="new_admin_token")
@patch("src.server.routes.auth.get_password_hash", return_value="hashed_pw")
async def test_first_boot_admin_creation(mock_hash, mock_create_token, mock_settings, mock_audit, mock_db, mock_request):
    mock_settings.admin_username = "admin"
    mock_settings.admin_password = "admin_password"
    mock_settings.jwt_access_token_expire_minutes = 30

    # First query: user not found
    mock_result_no_user = MagicMock()
    mock_result_no_user.scalars.return_value.first.return_value = None

    # Second query: count = 0
    mock_result_count = MagicMock()
    mock_result_count.scalar.return_value = 0

    mock_db.execute.side_effect = [mock_result_no_user, mock_result_count]
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    form = MagicMock()
    form.username = "admin"
    form.password = "admin_password"

    # Need to patch verify_password to return True for the newly created user
    with patch("src.server.routes.auth.verify_password", return_value=True):
        response = await login_for_access_token(request=mock_request, form_data=form, db=mock_db)

    assert response["access_token"] == "new_admin_token"
    mock_db.add.assert_called_once()


# ---------------------------------------------------------------------------
# First boot race condition (IntegrityError)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.server.routes.auth.record_audit", new_callable=AsyncMock)
@patch("src.server.routes.auth.settings")
@patch("src.server.routes.auth.create_access_token", return_value="race_token")
@patch("src.server.routes.auth.get_password_hash", return_value="hashed_pw")
async def test_first_boot_race_condition(mock_hash, mock_create_token, mock_settings, mock_audit, mock_db, mock_request):
    from sqlalchemy.exc import IntegrityError
    from src.server.middleware.auth import get_password_hash as real_hash
    from src.server.db.models import UserRole

    mock_settings.admin_username = "admin"
    mock_settings.admin_password = "admin_password"
    mock_settings.jwt_access_token_expire_minutes = 30

    # existing_user after the race resolves
    existing_user = User(
        id="user-race",
        username="admin",
        hashed_password=real_hash("admin_password"),
        is_active=True,
        role=UserRole.ADMIN,
    )

    # First query: user not found
    mock_result_no_user = MagicMock()
    mock_result_no_user.scalars.return_value.first.return_value = None

    # Second query: count = 0
    mock_result_count = MagicMock()
    mock_result_count.scalar.return_value = 0

    # After rollback + re-query: user now exists
    mock_result_found = MagicMock()
    mock_result_found.scalars.return_value.first.return_value = existing_user

    mock_db.execute.side_effect = [mock_result_no_user, mock_result_count, mock_result_found]
    mock_db.commit = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()

    form = MagicMock()
    form.username = "admin"
    form.password = "admin_password"

    with patch("src.server.routes.auth.verify_password", return_value=True):
        response = await login_for_access_token(request=mock_request, form_data=form, db=mock_db)

    assert response["access_token"] == "race_token"
    mock_db.rollback.assert_awaited_once()
