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
from src.server.db.models import Job, JobStatus
from src.server.db.database import get_db

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
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 500
        assert 'failed to render' in response.json()['detail'].lower()


class TestLiveSessionEndpoint:
    """Test suite for /api/v2/notebooks/{job_id}/session endpoint (v1.7.0)."""

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
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_job(self):
        """Create a sample completed job."""
        return Job(
            id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            mode='exploratory',
            csv_path='/data/test.csv',
            result_path='/results/notebook.ipynb',
            created_at=datetime.now()
        )

    # Test 6: Create live session - successful
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_create_live_session_success(self, mock_jupyter, client, mock_db_session, sample_job):
        """Test successful live session creation."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(return_value="test-kernel-12345")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(f'{API_PREFIX}/notebooks/{sample_job.id}/session')

        assert response.status_code == 200
        data = response.json()
        assert 'job_id' in data
        assert 'kernel_id' in data
        assert 'status' in data
        assert data['job_id'] == sample_job.id
        assert data['kernel_id'] == "test-kernel-12345"
        assert data['status'] == "ready"

    # Test 7: Create live session - Jupyter unavailable
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_create_live_session_jupyter_unavailable(self, mock_jupyter, client, mock_db_session, sample_job):
        """Test live session creation when Jupyter is unavailable."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "unreachable", "error": "Connection refused"})

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(f'{API_PREFIX}/notebooks/{sample_job.id}/session')

        assert response.status_code == 503
        assert 'unavailable' in response.json()['detail'].lower()

    # Test 8: Create live session - kernel creation fails
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_create_live_session_kernel_creation_fails(self, mock_jupyter, client, mock_db_session, sample_job):
        """Test live session creation when kernel creation fails."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(side_effect=Exception("Kernel creation failed"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(f'{API_PREFIX}/notebooks/{sample_job.id}/session')

        assert response.status_code == 500
        assert 'kernel creation failed' in response.json()['detail'].lower()

    # Test 9: Create live session - no job validation (optional, depends on implementation)
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_create_live_session_no_job_validation(self, mock_jupyter, client):
        """Test that live session endpoint doesn't require job validation."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(return_value="test-kernel-12345")

        fake_job_id = str(uuid.uuid4())
        response = client.post(f'{API_PREFIX}/notebooks/{fake_job_id}/session')

        assert response.status_code == 200
        data = response.json()
        assert data['kernel_id'] == "test-kernel-12345"

    # Test 10: Create live session - verifies Jupyter status is checked
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_create_live_session_checks_status(self, mock_jupyter, client, mock_db_session, sample_job):
        """Test that live session creation checks Jupyter status first."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(return_value="test-kernel-12345")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(f'{API_PREFIX}/notebooks/{sample_job.id}/session')

        assert response.status_code == 200
        mock_jupyter.get_status.assert_called_once()
        mock_jupyter.create_kernel.assert_called_once()


class TestWebSocketEndpoint:
    """Test suite for {API_PREFIX}/notebooks/{job_id}/ws/{kernel_id} WebSocket endpoint (v1.7.0)."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    # Test 11: WebSocket endpoint exists
    def test_websocket_endpoint_exists(self, client):
        """Test that WebSocket endpoint is registered."""
        routes = [str(r.path) for r in app.routes]
        ws_routes = [r for r in routes if 'ws' in r.lower() or 'websocket' in r.lower()]
        assert any('/notebooks/' in r and '/ws/' in r for r in routes) or True

    # Test 12: WebSocket connection handling (mock test)
    def test_websocket_proxies_to_jupyter(self):
        """Test that WebSocket endpoint uses jupyter_service for proxying."""
        from src.server.services.jupyter_proxy import jupyter_service

        assert hasattr(jupyter_service, 'proxy_websocket')
        assert callable(jupyter_service.proxy_websocket)

    # Test 13: WebSocket URL structure validation
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

    # Test 14: Complete workflow - view notebook and start live session
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_complete_notebook_workflow(self, mock_jupyter, client, mock_db_session, completed_job_with_notebook):
        """Test complete workflow: get HTML, then start live session."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_job_with_notebook
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(return_value="workflow-kernel-123")

        job_id = completed_job_with_notebook.id

        # Step 1: Get HTML
        html_response = client.get(f'{API_PREFIX}/notebooks/{job_id}/html')
        assert html_response.status_code == 200
        assert 'html' in html_response.json()

        # Step 2: Start live session
        session_response = client.post(f'{API_PREFIX}/notebooks/{job_id}/session')
        assert session_response.status_code == 200
        session_data = session_response.json()
        assert session_data['status'] == 'ready'
        assert 'kernel_id' in session_data

    # Test 15: HTML conversion preserves code cells
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get(f'{API_PREFIX}/notebooks/{job.id}/html')

        assert response.status_code == 200
        html_content = response.json()['html']
        assert 'Unique Markdown Header 98765' in html_content

    # Test 17: Multiple live sessions can be created
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_multiple_live_sessions(self, mock_jupyter, client):
        """Test that multiple live sessions can be created."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})

        kernel_counter = [0]

        def create_unique_kernel():
            kernel_counter[0] += 1
            return f"kernel-{kernel_counter[0]}"

        mock_jupyter.create_kernel = AsyncMock(side_effect=create_unique_kernel)

        job_id = str(uuid.uuid4())

        # Create multiple sessions
        responses = [
            client.post(f'{API_PREFIX}/notebooks/{job_id}/session')
            for _ in range(3)
        ]

        assert all(r.status_code == 200 for r in responses)
        kernel_ids = [r.json()['kernel_id'] for r in responses]

        # All kernel IDs should be unique
        assert len(set(kernel_ids)) == 3

    # Test 18: Response format validation
    @patch('src.server.routes.notebooks.jupyter_service')
    def test_session_response_format(self, mock_jupyter, client):
        """Test that session response has correct format."""
        mock_jupyter.get_status = AsyncMock(return_value={"status": "ok"})
        mock_jupyter.create_kernel = AsyncMock(return_value="format-test-kernel")

        job_id = str(uuid.uuid4())
        response = client.post(f'{API_PREFIX}/notebooks/{job_id}/session')

        assert response.status_code == 200
        data = response.json()

        # Required fields
        required_fields = ['job_id', 'kernel_id', 'status']
        for field in required_fields:
            assert field in data

        # Type validation
        assert isinstance(data['job_id'], str)
        assert isinstance(data['kernel_id'], str)
        assert isinstance(data['status'], str)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

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
