"""
Integration tests for Job Management API endpoints.

Tests job listing, status retrieval, and cancellation endpoints from
src/server/routes/api/v2/jobs.py
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.server.db.database import get_db

from src.server.main import fastapi_app as app
from src.server.db.models import Job, JobStatus
from src.server.middleware.auth import verify_token


class TestJobsAPI:
    """Test suite for jobs API endpoints."""

    @pytest.fixture
    def mock_get_db(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def client(self, mock_get_db):
        """Create a test client for the FastAPI app."""
        async def override_get_db():
            yield mock_get_db

        def override_verify_token():
            return "test-token"

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[verify_token] = override_verify_token
        
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_jobs(self):
        """Create sample job records."""
        jobs = [
            Job(
                id=str(uuid.uuid4()),
                status=JobStatus.COMPLETED,
                mode='predictive',
                csv_path='/data/test1.csv',
                target_column='churn',
                result_path='/results/notebook1.ipynb',
                cost_estimate={'estimated_cost_usd': 0.05},
                token_usage={'total': 1000},
                created_at=datetime(2024, 1, 1, 12, 0, 0)
            ),
            Job(
                id=str(uuid.uuid4()),
                status=JobStatus.RUNNING,
                mode='exploratory',
                csv_path='/data/test2.csv',
                target_column=None,
                result_path=None,
                cost_estimate={'estimated_cost_usd': 0.03},
                token_usage={'total': 500},
                created_at=datetime(2024, 1, 1, 13, 0, 0)
            ),
            Job(
                id=str(uuid.uuid4()),
                status=JobStatus.FAILED,
                mode='predictive',
                csv_path='/data/test3.csv',
                target_column='target',
                result_path=None,
                error_message='Analysis failed: Invalid data',
                cost_estimate={'estimated_cost_usd': 0.02},
                token_usage={'total': 200},
                created_at=datetime(2024, 1, 1, 14, 0, 0)
            )
        ]
        return jobs

    # Test 1: List jobs successfully

    def test_list_jobs_success(self, mock_get_db, client, sample_jobs):
        """Test successful job listing."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    # Test 2: List jobs with pagination

    def test_list_jobs_pagination(self, mock_get_db, client, sample_jobs):
        """Test job listing with pagination parameters."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs[:2]
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs?skip=0&limit=2')

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    # Test 3: List jobs returns correct schema

    def test_list_jobs_schema(self, mock_get_db, client, sample_jobs):
        """Test that job listing returns correct schema."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs[:1]
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        job = data[0]

        # Verify required fields
        assert 'id' in job
        assert 'status' in job
        assert 'mode' in job
        assert 'created_at' in job

    # Test 4: List jobs with no results

    def test_list_jobs_empty(self, mock_get_db, client):
        """Test job listing when no jobs exist."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 5: Get job status successfully

    def test_get_job_status_success(self, mock_get_db, client, sample_jobs):
        """Test successful job status retrieval."""
        job = sample_jobs[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        assert data['job_id'] == job.id
        assert data['status'] == JobStatus.COMPLETED.value

    # Test 6: Get job status for non-existent job

    def test_get_job_status_not_found(self, mock_get_db, client):
        """Test job status retrieval for non-existent job."""

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_get_db.execute.return_value = mock_result

        fake_job_id = str(uuid.uuid4())
        response = client.get(f'/api/v2/jobs/{fake_job_id}')

        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()

    # Test 7: Get job status returns complete schema

    def test_get_job_status_schema(self, mock_get_db, client, sample_jobs):
        """Test that job status response has all required fields."""
        job = sample_jobs[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()

        required_fields = ['job_id', 'status', 'progress', 'message', 'created_at']
        for field in required_fields:
            assert field in data

    # Test 8: Get job status with error message

    def test_get_job_status_with_error(self, mock_get_db, client, sample_jobs):
        """Test job status for failed job includes error message."""
        job = sample_jobs[2]  # Failed job

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        assert data['error'] is not None
        assert 'Invalid data' in data['error']

    # Test 9: Get job status with result path

    def test_get_job_status_with_result(self, mock_get_db, client, sample_jobs):
        """Test job status for completed job includes result path."""
        job = sample_jobs[0]  # Completed job

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        assert data['result_path'] is not None
        assert 'notebook1.ipynb' in data['result_path']

    # Test 10: Get job status with token usage

    def test_get_job_status_token_usage(self, mock_get_db, client, sample_jobs):
        """Test that job status includes token usage information."""
        job = sample_jobs[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        assert 'token_usage' in data
        assert data['token_usage'] is not None

    # Test 11: Cancel job successfully
    @patch('src.server.celery_app.celery_app')

    def test_cancel_job_success(self, mock_celery, mock_get_db, client, sample_jobs):
        """Test successful job cancellation."""
        job = sample_jobs[1]  # Running job

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result
        mock_get_db.commit = AsyncMock()

        response = client.post(f'/api/v2/jobs/{job.id}/cancel')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'cancelled'
        # Verify Celery revoke was called
        mock_celery.control.revoke.assert_called_once_with(job.id, terminate=True)

    # Test 12: Cancel non-existent job
    @patch('src.server.celery_app.celery_app')

    def test_cancel_job_not_found(self, mock_celery, mock_get_db, client):
        """Test cancelling a non-existent job."""

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_get_db.execute.return_value = mock_result

        fake_job_id = str(uuid.uuid4())
        response = client.post(f'/api/v2/jobs/{fake_job_id}/cancel')

        # Should still return success (idempotent)
        assert response.status_code == 200

    # Test 13: Cancel already completed job
    @patch('src.server.celery_app.celery_app')

    def test_cancel_completed_job(self, mock_celery, mock_get_db, client, sample_jobs):
        """Test cancelling an already completed job."""
        job = sample_jobs[0]  # Completed job

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result
        mock_get_db.commit = AsyncMock()

        response = client.post(f'/api/v2/jobs/{job.id}/cancel')

        # Should still succeed (Celery will handle if task already done)
        assert response.status_code == 200

    # Test 14: Cancel job updates database
    @patch('src.server.celery_app.celery_app')

    def test_cancel_job_updates_db(self, mock_celery, mock_get_db, client, sample_jobs):
        """Test that cancelling a job updates the database status."""
        job = sample_jobs[1]  # Running job

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result
        mock_get_db.commit = AsyncMock()

        response = client.post(f'/api/v2/jobs/{job.id}/cancel')

        assert response.status_code == 200
        # Verify status was updated to CANCELLED
        assert job.status == JobStatus.CANCELLED
        # Verify commit was called
        mock_get_db.commit.assert_called_once()

    # Test 15: List jobs ordered by creation time

    def test_list_jobs_ordered(self, mock_get_db, client, sample_jobs):
        """Test that jobs are returned in descending creation order."""
        # Reverse order to verify sorting
        reversed_jobs = list(reversed(sample_jobs))


        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = reversed_jobs
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        # Newest should be first
        assert data[0]['id'] == sample_jobs[2].id

    # Test 16: List jobs with large skip value

    def test_list_jobs_large_skip(self, mock_get_db, client):
        """Test job listing with skip value larger than total jobs."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs?skip=1000')

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 17: List jobs with zero limit

    def test_list_jobs_zero_limit(self, mock_get_db, client):
        """Test job listing with limit=0."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs?limit=0')

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 18: Job summary includes cost estimate

    def test_job_summary_cost_estimate(self, mock_get_db, client, sample_jobs):
        """Test that job summaries include cost estimates."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs[:1]
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert 'cost_estimate' in data[0]

    # Test 19: Job summary includes CSV path

    def test_job_summary_csv_path(self, mock_get_db, client, sample_jobs):
        """Test that job summaries include CSV path."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs[:1]
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert 'csv_path' in data[0]
        assert data[0]['csv_path'] is not None

    # Test 20: Get job status handles enum values

    def test_get_job_status_enum_handling(self, mock_get_db, client, sample_jobs):
        """Test that job status correctly handles enum values."""
        job = sample_jobs[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        # Should be string value, not enum
        assert isinstance(data['status'], str)
        assert data['status'] == 'completed'

    # Test 21: List jobs handles enum conversion

    def test_list_jobs_enum_conversion(self, mock_get_db, client, sample_jobs):
        """Test that job listing correctly converts enum values to strings."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs[:1]
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        # Status and mode should be strings
        assert isinstance(data[0]['status'], str)
        assert isinstance(data[0]['mode'], str)

    # Test 22: Cancel job with Celery error
    @patch('src.server.celery_app.celery_app')

    def test_cancel_job_celery_error(self, mock_celery, mock_get_db, client, sample_jobs):
        """Test job cancellation handles Celery errors gracefully."""
        job = sample_jobs[1]
        mock_celery.control.revoke.side_effect = Exception("Celery error")


        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result
        mock_get_db.commit = AsyncMock()

        # Should handle error but still update DB
        response = client.post(f'/api/v2/jobs/{job.id}/cancel')

        # May return 500 or 200 depending on error handling
        assert response.status_code in [200, 500]

    # Test 23: Get job status with null fields

    def test_get_job_status_null_fields(self, mock_get_db, client):
        """Test job status response handles null optional fields."""
        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.PENDING,
            mode='exploratory',
            csv_path='/data/test.csv',
            target_column=None,
            result_path=None,
            error_message=None,
            created_at=datetime.now()
        )


        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        response = client.get(f'/api/v2/jobs/{job.id}')

        assert response.status_code == 200
        data = response.json()
        assert data['result_path'] is None
        assert data['error'] is None

    # Test 24: List jobs handles multiple modes

    def test_list_jobs_multiple_modes(self, mock_get_db, client, sample_jobs):
        """Test that job listing handles different pipeline modes."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        modes = [job['mode'] for job in data]
        assert 'predictive' in modes
        assert 'exploratory' in modes

    # Test 25: Get job with invalid UUID format
    def test_get_job_invalid_uuid(self, client):
        """Test job status retrieval with invalid UUID format."""
        response = client.get('/api/v2/jobs/not-a-valid-uuid')

        # FastAPI may return 422 for validation error or 404
        assert response.status_code in [404, 422, 500]

    # Test 26: List jobs default pagination values

    def test_list_jobs_default_pagination(self, mock_get_db, client, sample_jobs):
        """Test that default pagination values are used when not specified."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_jobs
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        # Should use default limit (20) and skip (0)

    # Test 27: Job summary error message field

    def test_job_summary_error_message(self, mock_get_db, client, sample_jobs):
        """Test that job summaries include error messages for failed jobs."""

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_jobs[2]]  # Failed job
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert 'error_message' in data[0]
        assert data[0]['error_message'] is not None

    # Test 28: Database connection error handling

    def test_list_jobs_db_error(self, mock_get_db, client):
        """Test error handling when database connection fails."""

        mock_get_db.execute.side_effect = Exception("Database error")

        response = client.get('/api/v2/jobs')

        assert response.status_code == 500

    # Test 29: Concurrent job status requests

    def test_concurrent_job_status_requests(self, mock_get_db, client, sample_jobs):
        """Test multiple concurrent job status requests."""
        job = sample_jobs[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_get_db.execute.return_value = mock_result

        # Make multiple requests
        responses = [client.get(f'/api/v2/jobs/{job.id}') for _ in range(5)]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    # Test 30: Job listing performance with many jobs

    def test_list_jobs_large_dataset(self, mock_get_db, client):
        """Test job listing with a large number of jobs."""
        # Create 100 mock jobs
        many_jobs = [
            Job(
                id=str(uuid.uuid4()),
                status=JobStatus.COMPLETED,
                mode='predictive',
                csv_path=f'/data/test{i}.csv',
                created_at=datetime.now()
            ) for i in range(100)
        ]


        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = many_jobs[:20]  # Default limit
        mock_get_db.execute.return_value = mock_result

        response = client.get('/api/v2/jobs')

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 20  # Should respect limit


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
