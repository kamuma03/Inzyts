import pytest
import os
import nbformat
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User, UserRole

# Override auth & db
mock_db_session = AsyncMock()

# The test user owns "job-nb" — used by the per-job ownership guard
# (src.server.db.queries.resolve_owned_job).
_TEST_USER_ID = "test-user-id"


def _fake_user():
    return User(
        id=_TEST_USER_ID,
        username="testuser",
        is_active=True,
        role=UserRole.ANALYST,
    )

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
    job.user_id = _TEST_USER_ID  # owned by the fake test user
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

# NOTE: tests for the legacy `/notebooks/{job_id}/session` and
# `/notebooks/{job_id}/ws/{kernel_id}` endpoints were removed in
# commit de9ca08 ("PR2: drop Jupyter Server container"). The Live
# panel uses an in-process KernelSandbox per job now — see
# tests/unit/services/test_kernel_session_manager.py for coverage.


# ════════════════════════════════════════════════════════
# Save Notebook Cells (PUT) — FR-NB-005
# ════════════════════════════════════════════════════════


def test_save_notebook_cells_success(sample_job, tmp_path):
    """Successful save rewrites the .ipynb with the supplied cells."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    payload = {
        "cells": [
            {"cell_type": "markdown", "source": "# New title"},
            {"cell_type": "code", "source": "x = 42\nprint(x)"},
        ]
    }

    with patch("src.server.routes.notebooks._OUTPUT_DIR", tmp_path):
        response = client.put("/api/v2/notebooks/job-nb/cells", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-nb"
    assert data["cell_count"] == 2
    assert data["path"] == sample_job.result_path

    # Round-trip: file on disk now matches the payload.
    nb = nbformat.read(sample_job.result_path, as_version=4)
    assert len(nb.cells) == 2
    assert nb.cells[0].cell_type == "markdown"
    assert nb.cells[0].source == "# New title"
    assert nb.cells[1].cell_type == "code"
    assert nb.cells[1].source == "x = 42\nprint(x)"


def test_save_notebook_cells_rejects_invalid_cell_type(sample_job, tmp_path):
    """Cells with cell_type other than code/markdown are rejected with 422."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    payload = {"cells": [{"cell_type": "raw", "source": "weird"}]}

    with patch("src.server.routes.notebooks._OUTPUT_DIR", tmp_path):
        response = client.put("/api/v2/notebooks/job-nb/cells", json=payload)

    assert response.status_code == 422
    assert "invalid cell_type" in response.json()["detail"].lower()


def test_save_notebook_cells_job_not_found():
    """Save returns 404 when the job doesn't exist (or isn't owned)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.put(
        "/api/v2/notebooks/missing-job/cells",
        json={"cells": [{"cell_type": "code", "source": "1"}]},
    )
    assert response.status_code == 404


def test_save_notebook_cells_no_result_path(sample_job):
    """Save returns 404 when the job has no generated notebook yet."""
    sample_job.result_path = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.put(
        "/api/v2/notebooks/job-nb/cells",
        json={"cells": [{"cell_type": "code", "source": "1"}]},
    )
    assert response.status_code == 404
    assert "No notebook generated" in response.json()["detail"]


def test_save_notebook_cells_rejects_path_outside_output_dir(sample_job, tmp_path):
    """The path validator must reject result_paths outside _OUTPUT_DIR."""
    # Point the job's notebook outside the configured output root.
    outside_path = tmp_path / "outside.ipynb"
    nb = nbformat.v4.new_notebook()
    nbformat.write(nb, str(outside_path))
    sample_job.result_path = str(outside_path)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Confine _OUTPUT_DIR to a sibling directory so `outside.ipynb` is
    # outside the allowed root.
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    with patch("src.server.routes.notebooks._OUTPUT_DIR", allowed_root):
        response = client.put(
            "/api/v2/notebooks/job-nb/cells",
            json={"cells": [{"cell_type": "code", "source": "1"}]},
        )
    assert response.status_code in (400, 403, 404)


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


# --- Kernel introspection endpoint (FR-10) ---------------------------------

def test_get_kernel_variables_no_session(sample_job):
    """No live kernel yet → kernel_active False, empty list, not a 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.services.kernel_session_manager.kernel_session_manager") as mock_ksm:
        mock_ksm.get_session.return_value = None
        response = client.get("/api/v2/notebooks/job-nb/cells/variables")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-nb"
    assert data["kernel_active"] is False
    assert data["variables"] == []


def test_get_kernel_variables_success(sample_job):
    """Live kernel → introspect_variables() rows surfaced as KernelVariable."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.services.kernel_session_manager.kernel_session_manager") as mock_ksm:
        mock_session = MagicMock()
        mock_session.introspect_variables.return_value = [
            {"name": "df", "type_name": "DataFrame", "kind": "value",
             "shape": [100, 5], "columns": ["a", "b"], "preview": "a b ..."},
            {"name": "total", "type_name": "int", "kind": "value", "preview": "42"},
            {"name": "pd", "type_name": "module", "kind": "module"},
            {"type_name": "int"},  # malformed (no name) — must be dropped
        ]
        mock_ksm.get_session.return_value = mock_session
        response = client.get("/api/v2/notebooks/job-nb/cells/variables")

    assert response.status_code == 200
    data = response.json()
    assert data["kernel_active"] is True
    names = [v["name"] for v in data["variables"]]
    assert names == ["df", "total", "pd"]  # nameless row filtered out
    df_var = data["variables"][0]
    assert df_var["shape"] == [100, 5]
    assert df_var["columns"] == ["a", "b"]


def test_get_kernel_variables_job_not_found():
    """Unowned / missing job → 404 from the ownership guard."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/notebooks/job-zzz/cells/variables")
    assert response.status_code == 404
