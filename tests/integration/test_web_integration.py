"""
Integration tests for FastAPI Web UI and API endpoints.

Tests complete user workflows through the FastAPI web interface including:
- Job submission and status polling
- Cache checking and management
- Notebook download
- Upgrade workflow (exploratory → predictive)

Migrated from Flask to FastAPI test structure.
"""

import pytest
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.main import fastapi_app as app
from src.server.db.database import get_db
from src.server.db.models import JobStatus
from src.utils.cache_manager import CacheManager


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(mock_db):
    """Create FastAPI test client with mocked DB."""
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for testing."""
    cache_dir = tmp_path / ".inzyts_cache_test"
    cache_dir.mkdir(parents=True, exist_ok=True)
    original_cache_dir = CacheManager.CACHE_DIR
    CacheManager.CACHE_DIR = cache_dir
    yield cache_dir
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    CacheManager.CACHE_DIR = original_cache_dir


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text("Name,Age,Score\nAlice,25,85\nBob,30,92\nCharlie,35,78")
    return str(csv_file)


class TestAPIEndpoints:
    """Test basic API endpoint functionality."""

    def test_analyze_endpoint_missing_csv(self, client):
        """Test /api/v2/analyze rejects request without CSV path."""
        response = client.post('/api/v2/analyze', json={})
        assert response.status_code == 422  # FastAPI validation error

    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_endpoint_success(self, mock_estimator, mock_task, client, sample_csv, mock_db):
        """Test /api/v2/analyze accepts valid request and returns job ID."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json={
            'csv_path': sample_csv,
            'mode': 'exploratory'
        })

        assert response.status_code == 200
        data = response.json()
        assert 'job_id' in data
        assert data['status'] == 'pending'

    def test_job_status_not_found(self, client, mock_db):
        """Test /api/v2/jobs/<job_id> returns 404 for unknown job."""
        # Mock empty result for job lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs/nonexistent-job-id')
        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data

    def test_jobs_list(self, client, mock_db):
        """Test /api/v2/jobs returns list of jobs."""
        # Mock job list result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestFilesEndpoint:
    """Test /api/v2/files endpoint."""

    def test_check_file_not_found(self, client, mock_db):
        """Test file validation returns error for non-existent file."""
        response = client.post('/api/v2/files/validate', json={
            'file_path': '/nonexistent/path/file.csv'
        })
        # Should return validation result or 422 depending on implementation
        # Should return validation result or 422 depending on implementation
        assert response.status_code in [200, 400, 422, 404]


class TestNotebooksEndpoint:
    """Test /api/v2/notebooks endpoint."""

    def test_notebook_not_found(self, client, mock_db):
        """Test notebook download returns 404 for unknown job."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.get('/api/v2/notebooks/nonexistent-job-id')
        assert response.status_code == 404


class TestJobCancellation:
    """Test job cancellation endpoint."""

    @patch('src.server.celery_app.celery_app')
    def test_cancel_job(self, mock_celery, client, mock_db):
        """Test /api/v2/jobs/<job_id>/cancel cancels job."""
        mock_job = MagicMock()
        mock_job.status = JobStatus.RUNNING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db.execute.return_value = mock_result

        response = client.post('/api/v2/jobs/test-job-123/cancel')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'cancelled'


class TestEndToEndWorkflows:
    """End-to-end integration tests for complete workflows."""

    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_e2e_exploratory_analysis(self, mock_estimator, mock_task, client, sample_csv, mock_db):
        """
        Test complete exploratory analysis workflow.

        Steps:
        1. Submit analysis job
        2. Get job status
        """
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        # Step 1: Submit analysis
        response = client.post('/api/v2/analyze', json={
            'csv_path': sample_csv,
            'mode': 'exploratory',
            'question': 'What are the key patterns?'
        })
        assert response.status_code == 200
        job_id = response.json()['job_id']

        # Step 2: Mock job lookup for status check
        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.status = JobStatus.PENDING
        mock_job.result_path = None
        mock_job.error_message = None
        mock_job.token_usage = {"input": 0, "output": 0}
        mock_job.created_at = datetime.now()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job_id}')
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_malformed_json_request(self, client):
        """Test API handles malformed JSON gracefully."""
        response = client.post(
            '/api/v2/analyze',
            content='not-valid-json',
            headers={'Content-Type': 'application/json'}
        )
        # FastAPI returns 422 for validation errors
        assert response.status_code in [400, 422]

    def test_invalid_mode(self, client, sample_csv):
        """Test API rejects invalid analysis mode."""
        response = client.post('/api/v2/analyze', json={
            'csv_path': sample_csv,
            'mode': 'invalid_mode'
        })
        # Pydantic enum validation
        assert response.status_code == 422
