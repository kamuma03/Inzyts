import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.server.routes.websockets import (
    connect,
    disconnect,
    join_job,
    notify_job_update,
    notify_log,
    sio,
)

@pytest.fixture
def mock_sio_emit():
    with patch("src.server.routes.websockets.sio.emit", new_callable=AsyncMock) as mock_emit:
        yield mock_emit

@pytest.fixture
def mock_sio_enter_room():
    with patch("src.server.routes.websockets.sio.enter_room", new_callable=AsyncMock) as mock_enter:
        yield mock_enter

@pytest.fixture
def mock_sio_save_session():
    with patch("src.server.routes.websockets.sio.save_session", new_callable=AsyncMock) as mock_save:
        yield mock_save

@pytest.fixture
def mock_verify_token_async():
    with patch("src.server.routes.websockets.verify_token_async", new_callable=AsyncMock) as mock_verify:
        yield mock_verify

@pytest.fixture
def mock_async_session_maker():
    """Mock async_session_maker at the source it's imported from (local import in functions)."""
    with patch("src.server.db.database.async_session_maker") as mock_maker:
        mock_db = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_maker.return_value = mock_ctx
        yield mock_maker, mock_db

@pytest.mark.asyncio
async def test_connect_no_token(mock_verify_token_async, mock_async_session_maker):
    environ = {"QUERY_STRING": "", "headers_raw": []}
    assert await connect("sid-123", environ) is False
    mock_verify_token_async.assert_not_called()

@pytest.mark.asyncio
async def test_connect_with_header_token_invalid(mock_verify_token_async, mock_async_session_maker):
    environ = {
        "QUERY_STRING": "",
        "headers_raw": [(b"authorization", b"Bearer bad_token")]
    }
    mock_verify_token_async.return_value = None

    assert await connect("sid-123", environ) is False
    mock_verify_token_async.assert_called_once()
    assert mock_verify_token_async.call_args[0][0] == "bad_token"

@pytest.mark.asyncio
async def test_connect_with_header_token_valid(mock_verify_token_async, mock_async_session_maker, mock_sio_save_session):
    environ = {
        "QUERY_STRING": "",
        "headers_raw": [(b"authorization", b"Bearer header_token")]
    }
    mock_user = MagicMock()
    mock_user.username = "testuser"
    mock_verify_token_async.return_value = mock_user

    result = await connect("sid-123", environ)
    assert result is None
    mock_verify_token_async.assert_called_once()
    assert mock_verify_token_async.call_args[0][0] == "header_token"

@pytest.mark.asyncio
async def test_connect_with_header_token_invalid(mock_verify_token_async, mock_async_session_maker):
    # Non-Bearer authorization header: no token extracted, falls through to query string
    environ = {
        "QUERY_STRING": "",
        "headers_raw": [(b"authorization", b"Basic not_a_bearer_token")]
    }
    assert await connect("sid-123", environ) is False

@pytest.mark.asyncio
async def test_disconnect():
    await disconnect("sid-123")

@pytest.mark.asyncio
async def test_join_job_dict_data(mock_sio_enter_room, mock_sio_emit, mock_async_session_maker):
    _, mock_db = mock_async_session_maker
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "job-123"  # job exists
    mock_db.execute = AsyncMock(return_value=mock_result)

    data = {"job_id": "job-123"}
    await join_job("sid-123", data)

    mock_sio_enter_room.assert_called_once_with("sid-123", "job-123")
    mock_sio_emit.assert_called_once_with("log", "Connected to log stream for job-123", room="job-123")

@pytest.mark.asyncio
async def test_join_job_string_data(mock_sio_enter_room, mock_sio_emit, mock_async_session_maker):
    _, mock_db = mock_async_session_maker
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "job-456"
    mock_db.execute = AsyncMock(return_value=mock_result)

    data = "job-456"
    await join_job("sid-456", data)

    mock_sio_enter_room.assert_called_once_with("sid-456", "job-456")
    mock_sio_emit.assert_called_once_with("log", "Connected to log stream for job-456", room="job-456")

@pytest.mark.asyncio
async def test_notify_job_update(mock_sio_emit):
    data = {"status": "running", "progress": 50}
    await notify_job_update("job-789", data)

    mock_sio_emit.assert_called_once_with("progress", data, room="job-789")

@pytest.mark.asyncio
async def test_notify_log(mock_sio_emit):
    message = "Processing phase 1"
    await notify_log("job-999", message)

    mock_sio_emit.assert_called_once_with("log", message, room="job-999")
