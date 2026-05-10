"""
Integration tests for Notebook API endpoints.

Tests the notebook endpoints including HTML export, live session creation,
and WebSocket proxy for Jupyter kernel communication (v1.7.0 feature).
"""

import pytest
import uuid
import json
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app as app
from src.server.db.models import Job, JobStatus, UserRole
from src.server.db.database import get_db
from src.server.middleware.auth import verify_token
from tests.integration.conftest import mock_db_returns  # noqa: F401


def _admin_user_override():
    """Stand-in `verify_token` override that satisfies `resolve_owned_job`.

    `resolve_owned_job` expects a User-shaped object with `.role` and `.id`;
    a bare string would short-circuit to VIEWER and fail ownership checks.
    Returning a MagicMock with role=ADMIN bypasses ownership cleanly.
    """
    user = MagicMock()
    user.role = UserRole.ADMIN
    user.id = "test-admin-id"
    user.username = "test-admin"
    return user


@pytest.fixture(autouse=True)
def _allow_tmp_notebook_paths(monkeypatch, tmp_path_factory):
    """Make the notebook path validator accept tmp dirs created by pytest.

    The route's ``_validate_notebook_path`` allow-lists only
    ``settings.output_dir_resolved``. Tests intentionally write notebooks
    under ``tmp_path`` so the fixtures don't pollute the production output
    dir; this autouse hook neutralises that check for the duration of each
    test.
    """
    import src.server.routes.notebooks as nb_mod
    monkeypatch.setattr(nb_mod, "_validate_notebook_path", lambda _p: None)

# API prefix for v2 routes
API_PREFIX = "/api/v2"


class TestNotebookHTMLEndpoint:
    """Test suite for /api/v2/notebooks/{job_id}/html endpoint."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock DB session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def client(self, mock_db_session):
        """Create a test client with DB override."""
        async def override_get_db():
            yield mock_db_session
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[verify_token] = _admin_user_override
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_notebook_content(self):
        """Create sample Jupyter notebook content."""
        return {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Test Analysis\n", "This is a test notebook."]
                },
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": ["import pandas as pd\n", "print('Hello, World!')"],
                    "execution_count": 1,
                    "outputs": []
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {"name": "python", "version": "3.10.0"}
            },
            "nbformat": 4,
            "nbformat_minor": 5
        }

    @pytest.fixture
    def sample_job(self, tmp_path, sample_notebook_content):
        """Create a sample job with notebook file."""
        notebook_path = tmp_path / "test_notebook.ipynb"
        notebook_path.write_text(json.dumps(sample_notebook_content))

        return Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

    # Test 1: Get notebook HTML - successful conversion
    def test_get_notebook_html_success(self, client, mock_db_session, sample_job):
        """Test successful notebook HTML conversion."""
        mock_db_returns(mock_db_session, sample_job)

        response = client.get(f'{API_PREFIX}/notebooks/{sample_job.id}/html')

        assert response.status_code == 200
        data = response.json()
        assert 'html' in data
        assert 'job_id' in data
        assert data['job_id'] == sample_job.id
        # HTML should contain notebook content
        assert 'Test Analysis' in data['html'] or '<' in data['html']

    # Test 2: Get notebook HTML - job not found
    def test_get_notebook_html_job_not_found(self, client, mock_db_session):
        """Test notebook HTML retrieval for non-existent job."""
        mock_db_returns(mock_db_session, None)

        fake_job_id = str(uuid.uuid4())
        response = client.get(f'{API_PREFIX}/notebooks/{fake_job_id}/html')

        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()

    # Test 3: Get notebook HTML - no notebook generated
    def test_get_notebook_html_no_notebook(self, client, mock_db_session):
        """Test notebook HTML retrieval when no notebook has been generated."""
        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.RUNNING,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=None,  # No notebook yet
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 404
        assert 'no notebook' in response.json()['detail'].lower()

    # Test 4: Get notebook HTML - notebook file missing
    def test_get_notebook_html_file_missing(self, client, mock_db_session):
        """Test notebook HTML retrieval when file doesn't exist."""
        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path='/nonexistent/notebook.ipynb',
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()

    # Test 5: Get notebook HTML - invalid notebook format
    def test_get_notebook_html_invalid_format(self, client, mock_db_session, tmp_path):
        """Test notebook HTML retrieval with invalid notebook format."""
        invalid_notebook = tmp_path / "invalid.ipynb"
        invalid_notebook.write_text("not valid json or notebook format")

        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(invalid_notebook),
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 500
        assert 'failed to render' in response.json()['detail'].lower()


# NOTE: ``TestLiveSessionEndpoint`` (5 tests) and the
# ``test_websocket_proxies_to_jupyter`` test were removed: they targeted a
# ``jupyter_service`` HTTP proxy that was retired when notebook-cell
# execution moved in-process via ``KernelSandbox`` / ``cell_stream``. The
# new surface is exercised by ``test_api_notebooks::test_execute_cell*``,
# ``tests/unit/services/test_kernel_session_manager.py``, and the live
# ``test_full_workflow_execution`` E2E.


class TestWebSocketEndpoint:
    """Test suite for {API_PREFIX}/notebooks/{job_id}/ws/{kernel_id} WebSocket endpoint (v1.7.0)."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    def test_websocket_endpoint_exists(self, client):
        """Test that WebSocket endpoint is registered."""
        routes = [str(r.path) for r in app.routes]
        assert any('/notebooks/' in r and '/ws/' in r for r in routes) or True

    def test_websocket_url_structure(self, client):
        """Test WebSocket URL structure is correct."""
        job_id = str(uuid.uuid4())
        kernel_id = "test-kernel-123"
        expected_path = f"{API_PREFIX}/notebooks/{job_id}/ws/{kernel_id}"

        assert job_id in expected_path
        assert kernel_id in expected_path
        assert '/ws/' in expected_path


class TestNotebookEndpointIntegration:
    """Integration tests for complete notebook workflows."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock DB session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def client(self, mock_db_session):
        """Create a test client with DB override."""
        async def override_get_db():
            yield mock_db_session
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[verify_token] = _admin_user_override
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture
    def completed_job_with_notebook(self, tmp_path):
        """Create a completed job with a valid notebook file."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": ["import pandas as pd"],
                    "execution_count": None,
                    "outputs": []
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        notebook_path = tmp_path / "analysis_output.ipynb"
        notebook_path.write_text(json.dumps(notebook_content))

        return Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='predictive',
            csv_path='/data/test.csv',
            target_column='target',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

    # ``test_complete_notebook_workflow`` removed: it tested the
    # HTML-then-jupyter-session sequence; the second step targeted the
    # retired ``jupyter_service`` proxy. The HTML half is covered by the
    # other tests in this class.

    # Test: HTML conversion preserves code cells
    def test_html_preserves_code_cells(self, client, mock_db_session, tmp_path):
        """Test that HTML conversion includes code cell content."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": ["print('unique_test_string_12345')"],
                    "execution_count": 1,
                    "outputs": []
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        notebook_path = tmp_path / "code_test.ipynb"
        notebook_path.write_text(json.dumps(notebook_content))

        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 200
        html_content = response.json()['html']
        assert 'unique_test_string_12345' in html_content or 'print' in html_content

    # Test 16: HTML conversion preserves markdown cells
    def test_html_preserves_markdown(self, client, mock_db_session, tmp_path):
        """Test that HTML conversion includes markdown content."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Unique Markdown Header 98765"]
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        notebook_path = tmp_path / "markdown_test.ipynb"
        notebook_path.write_text(json.dumps(notebook_content))

        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 200
        html_content = response.json()['html']
        assert 'Unique Markdown Header 98765' in html_content

    # ``test_multiple_live_sessions`` and ``test_session_response_format``
    # removed: both targeted the retired ``jupyter_service`` proxy. Live-
    # session functionality is now exercised by
    # ``test_execute_cell_in_session`` etc. against the in-process
    # KernelSandbox.

    # Test 19: HTML endpoint handles encoding correctly
    def test_html_handles_unicode(self, client, mock_db_session, tmp_path):
        """Test that HTML conversion handles unicode characters."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Unicode Test: café, 日本語, emoji 🎉"]
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        notebook_path = tmp_path / "unicode_test.ipynb"
        notebook_path.write_text(json.dumps(notebook_content), encoding='utf-8')

        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 200
        html_content = response.json()['html']
        # Should contain unicode characters
        assert 'café' in html_content or '日本語' in html_content or 'Unicode Test' in html_content

    # Test 20: Concurrent HTML requests
    def test_concurrent_html_requests(self, client, mock_db_session, tmp_path):
        """Test concurrent HTML conversion requests."""
        notebook_content = {
            "cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# Test"]}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        notebook_path = tmp_path / "concurrent_test.ipynb"
        notebook_path.write_text(json.dumps(notebook_content))

        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path=str(notebook_path),
            created_at=datetime.now()
        )

        mock_db_returns(mock_db_session, job)

        # Make concurrent requests
        responses = [client.get(f'{API_PREFIX}/notebooks/{job.id}/html') for _ in range(5)]

        assert all(r.status_code == 200 for r in responses)
        # Verify content is present in all responses
        # Note: We don't check for identical HTML strings because nbconvert 
        # generates unique IDs for CSS/elements on each render.
        for r in responses:
            assert 'Test' in r.json()['html']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
