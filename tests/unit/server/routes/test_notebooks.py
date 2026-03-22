import pytest
import os
import nbformat
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User

# Override auth & db
mock_db_session = AsyncMock()

def _fake_user():
    return User(id="test-user-id", username="testuser", is_active=True)

@pytest.fixture(autouse=True)
def apply_dependency_overrides():
    fastapi_app.dependency_overrides[verify_token] = _fake_user
    fastapi_app.dependency_overrides[get_db] = lambda: mock_db_session
    yield
    fastapi_app.dependency_overrides.clear()

client = TestClient(fastapi_app)

@pytest.fixture
def sample_notebook(tmp_path):
    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_markdown_cell("Hello World"))
    nb_path = tmp_path / "test.ipynb"
    nbformat.write(nb, str(nb_path))
    return str(nb_path)

@pytest.fixture
def sample_job(sample_notebook):
    job = MagicMock()
    job.id = "job-nb"
    job.result_path = sample_notebook
    return job

def test_get_notebook_html_success(sample_job, tmp_path):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.server.routes.notebooks._OUTPUT_DIR", tmp_path):
        response = client.get("/api/v2/notebooks/job-nb/html")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-nb"
    assert "Hello World" in data["html"]

def test_get_notebook_html_not_found():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/notebooks/job-999/html")
    assert response.status_code == 404

def test_get_notebook_html_no_result_path(sample_job):
    sample_job.result_path = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/notebooks/job-nb/html")
    assert response.status_code == 404
    assert "No notebook generated" in response.json()["detail"]

def test_get_notebook_html_file_missing(sample_job, tmp_path):
    sample_job.result_path = str(tmp_path / "missing.ipynb")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.server.routes.notebooks._OUTPUT_DIR", tmp_path):
        response = client.get("/api/v2/notebooks/job-nb/html")
    assert response.status_code == 404
    assert "Notebook file not found" in response.json()["detail"]

def test_create_live_session_success():
    with patch("src.server.routes.notebooks.jupyter_service") as mock_jupyter:
        mock_jupyter.get_status = AsyncMock(return_value={"status": "online"})
        mock_jupyter.create_kernel = AsyncMock(return_value="kernel-123")

        # The endpoint also takes a db session and does not query it for session creation
        mock_db_session.execute = AsyncMock()

        response = client.post("/api/v2/notebooks/job-nb/session")
        assert response.status_code == 200
        assert response.json() == {"job_id": "job-nb", "kernel_id": "kernel-123", "status": "ready"}

def test_create_live_session_unreachable():
    with patch("src.server.routes.notebooks.jupyter_service") as mock_jupyter:
        mock_jupyter.get_status = AsyncMock(return_value={"status": "unreachable"})

        response = client.post("/api/v2/notebooks/job-nb/session")
        assert response.status_code == 503

def test_websocket_endpoint():
    """Test websocket proxy endpoint.

    The source uses verify_token_async (async, requires DB) for websocket auth.
    We mock both verify_token_async and async_session_maker to bypass real DB.
    """
    async def mock_proxy_func(websocket, kernel_id):
        await websocket.close()

    mock_user = MagicMock()
    mock_user.username = "testuser"

    with patch("src.server.routes.notebooks.jupyter_service") as mock_jupyter, \
         patch("src.server.routes.notebooks.verify_token_async", new_callable=AsyncMock, return_value=mock_user), \
         patch("src.server.db.database.async_session_maker") as mock_session_maker:

        mock_jupyter.proxy_websocket = AsyncMock(side_effect=mock_proxy_func)

        # Mock the async context manager for async_session_maker
        mock_db = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        with client.websocket_connect("/api/v2/notebooks/job-nb/ws/kernel-123?token=test-token") as websocket:
            pass

        mock_jupyter.proxy_websocket.assert_called_once()
        args, _ = mock_jupyter.proxy_websocket.call_args
        assert args[1] == "kernel-123"


# ════════════════════════════════════════════════════════
# Follow-Up Analysis Tests
# ════════════════════════════════════════════════════════

def test_ask_followup_success(sample_job):
    """Test successful follow-up question processing."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    sample_job.csv_path = "/data/test.csv"
    sample_job.mode = "segmentation"
    sample_job.question = None

    # Mock DB execute to return job, then empty history
    mock_history = MagicMock()
    mock_history.scalars.return_value.all.return_value = []

    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_history])
    mock_db_session.add = MagicMock()
    mock_db_session.commit = AsyncMock()

    with patch("src.services.kernel_session_manager.kernel_session_manager") as mock_ksm, \
         patch("src.workflow.agent_factory.AgentFactory") as mock_factory:
        # Mock kernel session
        mock_session = MagicMock()
        mock_session.df_context = "col1: int64\ncol2: object"
        mock_session.introspect.return_value = "df: DataFrame shape=(100, 5)"
        mock_ksm.get_or_create_session.return_value = mock_session

        # Mock agent via factory
        mock_agent = MagicMock()
        mock_agent.ask.return_value = {
            "success": True,
            "summary": "Cluster 2 is the largest.",
            "question_type": "drill-down",
            "cells": [
                {"cell_type": "markdown", "source": "## Analysis"},
                {"cell_type": "code", "source": "print('hello')"},
            ],
        }
        mock_factory.get_agent.return_value = mock_agent

        # Mock code execution
        exec_result = MagicMock()
        exec_result.output = "hello"
        exec_result.images = []
        mock_session.execute.return_value = exec_result

        response = client.post(
            "/api/v2/notebooks/job-nb/ask",
            json={"question": "Why is Cluster 2 the largest?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Cluster 2" in data["summary"]
    assert len(data["cells"]) == 2


def test_ask_followup_job_not_found():
    """Test follow-up returns 404 for nonexistent job."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.post(
        "/api/v2/notebooks/job-999/ask",
        json={"question": "What happened?"},
    )
    assert response.status_code == 404


def test_get_conversation_history_success(sample_job):
    """Test loading conversation history."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job

    # Mock conversation messages
    from datetime import datetime, timezone
    msg1 = MagicMock()
    msg1.role = "user"
    msg1.content = "Why is it low?"
    msg1.cells = None
    msg1.created_at = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

    msg2 = MagicMock()
    msg2.role = "assistant"
    msg2.content = "Because of missing data."
    msg2.cells = [{"cell_type": "markdown", "source": "## Explanation"}]
    msg2.created_at = datetime(2026, 2, 26, 10, 0, 5, tzinfo=timezone.utc)

    mock_history = MagicMock()
    mock_history.scalars.return_value.all.return_value = [msg1, msg2]

    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_history])

    response = client.get("/api/v2/notebooks/job-nb/conversation")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-nb"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["cells"] is not None


def test_get_conversation_history_empty(sample_job):
    """Test loading conversation history when no messages exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job

    mock_history = MagicMock()
    mock_history.scalars.return_value.all.return_value = []

    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_history])

    response = client.get("/api/v2/notebooks/job-nb/conversation")
    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
