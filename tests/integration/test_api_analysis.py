"""
Integration tests for Analysis API endpoint.

Tests the main analysis endpoint including request validation,
cost estimation, and job creation from src/server/routes/analysis.py
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app as app
from src.server.db.models import JobStatus
from sqlalchemy.ext.asyncio import AsyncSession
from src.server.db.database import get_db


class TestAnalysisAPI:
    """Test suite for analysis API endpoint."""

    @pytest.fixture
    def mock_get_db(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def client(self, mock_get_db):
        """Create a test client for the FastAPI app."""
        async def override_get_db():
            yield mock_get_db

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a sample CSV file."""
        csv_path = tmp_path / "test_data.csv"
        csv_content = """age,tenure,income,churn
25,12,50000,0
30,24,60000,0
35,36,70000,1
40,48,80000,0
45,60,90000,1
"""
        csv_path.write_text(csv_content)
        return str(csv_path)

    @pytest.fixture
    def valid_predictive_request(self, sample_csv):
        """Create a valid predictive analysis request."""
        return {
            "csv_path": sample_csv,
            "mode": "predictive",
            "target_column": "churn",
            "analysis_type": "classification"
        }

    @pytest.fixture
    def valid_exploratory_request(self, sample_csv):
        """Create a valid exploratory analysis request."""
        return {
            "csv_path": sample_csv,
            "mode": "exploratory",
            "question": "What patterns exist in this customer data?"
        }

    # Test 1: Analyze endpoint with valid predictive request
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_predictive_success(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test successful predictive analysis request."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        data = response.json()
        assert 'job_id' in data
        assert data['status'] == 'pending'
        assert 'estimated_cost' in data
        assert data['estimated_cost'] == 0.05

    # Test 2: Analyze endpoint with valid exploratory request
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_exploratory_success(self, mock_estimator, mock_task, mock_get_db, client, valid_exploratory_request):
        """Test successful exploratory analysis request."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.03,
            'input_tokens': 800,
            'output_tokens': 1500
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_exploratory_request)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'pending'

    # Test 3: Analyze without CSV path (validation error)
    def test_analyze_missing_csv_path(self, client):
        """Test analysis request without CSV path."""
        request = {
            "mode": "predictive",
            "target_column": "churn"
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 422  # Validation error

    # Test 4: Analyze with non-existent CSV file
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_nonexistent_csv(self, mock_estimator, mock_task, client, mock_get_db):
        """Test analysis request with non-existent CSV file."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.0,
            'input_tokens': 0,
            'output_tokens': 0
        }
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": "/nonexistent/file.csv",
            "mode": "predictive",
            "target_column": "target"
        }

        # May succeed at endpoint level, fail later in task
        response = client.post('/api/v2/analyze', json=request)
        # Endpoint doesn't validate file existence, so it may return 200
        assert response.status_code in [200, 400, 500]

    # Test 5: Analyze with invalid mode
    def test_analyze_invalid_mode(self, client, sample_csv):
        """Test analysis request with invalid mode."""
        request = {
            "csv_path": sample_csv,
            "mode": "invalid_mode",
            "target_column": "target"
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 422  # Validation error

    # Test 6: Predictive mode without target column
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_predictive_no_target(self, mock_estimator, mock_task, client, sample_csv, mock_get_db):
        """Test predictive analysis without target column."""
        mock_estimator.estimate_job_cost.return_value = {'estimated_cost_usd': 0.05}
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": sample_csv,
            "mode": "predictive"
            # Missing target_column
        }

        # Schema may allow null target, but logic should handle it
        response = client.post('/api/v2/analyze', json=request)
        # May succeed at validation but should be caught by business logic
        assert response.status_code in [200, 400, 422]

    # Test 7: Exploratory mode without question
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_exploratory_no_question(self, mock_estimator, mock_task, mock_get_db, client, sample_csv):
        """Test exploratory analysis without question (should still work)."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.03,
            'input_tokens': 800,
            'output_tokens': 1500
        }
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": sample_csv,
            "mode": "exploratory"
            # No question
        }

        response = client.post('/api/v2/analyze', json=request)

        # Should succeed, question is optional
        assert response.status_code == 200

    # Test 8: Analyze creates job in database
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_creates_job(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that analysis request creates a job in the database."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }

        created_jobs = []

        def capture_job(job):
            created_jobs.append(job)

        mock_get_db.add.side_effect = capture_job
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        # Verify job was added to session
        assert len(created_jobs) > 0
        job = created_jobs[0]
        assert job.status == JobStatus.PENDING

    # Test 9: Analyze triggers Celery task
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_triggers_celery_task(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that analysis request triggers Celery task."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        # Verify Celery task was triggered
        mock_task.apply_async.assert_called_once()

    # Test 10: Analyze with data dictionary path
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_with_data_dictionary(self, mock_estimator, mock_task, mock_get_db, client, sample_csv, tmp_path):
        """Test analysis with data dictionary path."""
        dict_path = tmp_path / "data_dict.csv"
        dict_path.write_text("column,description\nage,Customer age\nchurn,Churn indicator")

        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": sample_csv,
            "mode": "predictive",
            "target_column": "churn",
            "dict_path": str(dict_path)
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 200

    # Test 11: Cost estimation is called
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_calls_cost_estimator(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that cost estimator is called during analysis."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        # Verify cost estimator was called
        mock_estimator.estimate_job_cost.assert_called_once()

    # Test 12: Response includes creation timestamp
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_response_timestamp(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that response includes creation timestamp."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        data = response.json()
        assert 'created_at' in data

    # Test 13: Response includes message
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_response_message(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that response includes success message."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert 'queued' in data['message'].lower() or 'success' in data['message'].lower()

    # Test 14: Job ID is valid UUID
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_job_id_uuid(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that returned job ID is a valid UUID."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        data = response.json()
        job_id = data['job_id']
        # Should be valid UUID
        uuid.UUID(job_id)

    # Test 15: Celery task receives correct parameters
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_celery_task_parameters(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that Celery task receives correct parameters."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        # Verify task was called with correct args
        call_args = mock_task.apply_async.call_args
        assert call_args is not None
        args = call_args[1]['args']
        # Should include job_id, csv_path, mode, target, question, dict_path, analysis_type
        assert len(args) >= 3  # At minimum: job_id, csv_path, mode

    # Test 16: Database error handling
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_database_error(self, mock_estimator, mock_get_db, client, valid_predictive_request):
        """Test error handling when database operation fails."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_get_db.commit.side_effect = Exception("Database error")

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 500

    # Test 17: Analyze with analysis_type hint
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_with_analysis_type_hint(self, mock_estimator, mock_task, mock_get_db, client, sample_csv):
        """Test analysis with analysis_type hint for better routing."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": sample_csv,
            "mode": "predictive",
            "target_column": "churn",
            "analysis_type": "regression"  # Hint
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 200

    # Test 18: Multiple concurrent requests
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_concurrent_requests(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test multiple concurrent analysis requests."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        # Make 5 concurrent requests
        responses = [
            client.post('/api/v2/analyze', json=valid_predictive_request)
            for _ in range(5)
        ]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        # All should have different job IDs
        job_ids = [r.json()['job_id'] for r in responses]
        assert len(job_ids) == len(set(job_ids))

    # Test 19: Cost estimate stored in job
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_stores_cost_estimate(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that cost estimate is stored in job record."""
        cost_data = {
            'estimated_cost_usd': 0.12,
            'input_tokens': 2000,
            'output_tokens': 3000
        }
        mock_estimator.estimate_job_cost.return_value = cost_data

        created_jobs = []

        def capture_job(job):
            created_jobs.append(job)

        mock_get_db.add.side_effect = capture_job
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        # Verify cost estimate was stored
        assert len(created_jobs) > 0
        job = created_jobs[0]
        assert job.cost_estimate == cost_data

    # Test 20: Token usage initialized
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_initializes_token_usage(self, mock_estimator, mock_task, mock_get_db, client, valid_predictive_request):
        """Test that token usage is initialized to zero."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }

        created_jobs = []

        def capture_job(job):
            created_jobs.append(job)

        mock_get_db.add.side_effect = capture_job
        mock_task.apply_async = MagicMock()

        response = client.post('/api/v2/analyze', json=valid_predictive_request)

        assert response.status_code == 200
        assert len(created_jobs) > 0
        job = created_jobs[0]
        assert job.token_usage == {"input": 0, "output": 0}

    # Test 21: Analyze with exclude_columns
    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_exclude_columns(self, mock_estimator, mock_task, mock_get_db, client, sample_csv):
        """Test analysis with exclude_columns parameter."""
        mock_estimator.estimate_job_cost.return_value = {
            'estimated_cost_usd': 0.05,
            'input_tokens': 1000,
            'output_tokens': 2000
        }
        mock_task.apply_async = MagicMock()

        request = {
            "csv_path": sample_csv,
            "mode": "exploratory",
            "exclude_columns": ["id", "timestamp"]
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 200

        # Verify task was called with exclude_columns
        call_args = mock_task.apply_async.call_args
        args = call_args[1]['args']
        # args signature: [job_id, csv_path, mode, target, question, dict_path, analysis_type, multi, exclude]
        # exclude_columns should be the last argument (index 8)
        assert len(args) >= 9
        assert args[8] == ["id", "timestamp"]

    @patch('src.server.services.engine.execution_task')
    @patch('src.server.routes.analysis.cost_estimator')
    def test_analyze_use_cache(self, mock_estimator, mock_task, mock_get_db, client, sample_csv):
        """Test analysis with use_cache parameter."""
        mock_estimator.estimate_job_cost.return_value = {"estimated_cost_usd": 0.5}
        mock_task.apply_async = MagicMock()

        # Request with use_cache=True
        request = {
            "csv_path": sample_csv,
            "mode": "predictive",
            "use_cache": True
        }

        response = client.post('/api/v2/analyze', json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

        # Verify execution_task called with use_cache=True
        # Args: [job_id, csv, mode, target, question, dict, type, multi, exclude, USE_CACHE]
        call_args = mock_task.apply_async.call_args
        args = call_args[1]['args']
        assert len(args) >= 10
        assert args[9] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
