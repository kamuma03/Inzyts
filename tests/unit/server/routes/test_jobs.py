import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import Job, JobStatus, User

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
def sample_job():
    from datetime import timezone
    job = MagicMock()
    job.id = "job-123"
    job.status = JobStatus.COMPLETED
    job.mode = "exploratory"
    job.created_at = datetime.now(timezone.utc)
    job.cost_estimate = {}
    job.token_usage = {}
    job.result_path = "/results/job-123.ipynb"
    job.csv_path = "/data/test.csv"
    job.error_message = None
    job.logs_location = None
    job.user_id = "test-user-id"
    return job

def test_list_jobs(sample_job):
    mock_result = MagicMock()
    # the db.execute(...) returns an object whose scalars().all() we need
    mock_result.scalars.return_value.all.return_value = [sample_job]
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "job-123"
    assert data[0]["status"] == "completed"
    assert data[0]["token_usage"] == {}

def test_get_job_status_success(sample_job):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/jobs/job-123")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-123"
    assert data["status"] == "completed"
    assert data["progress"] == 100

def test_get_job_status_not_found():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/jobs/job-999")
    assert response.status_code == 404

def test_get_job_status_with_logs(sample_job, tmp_path):
    log_file = tmp_path / "job-123.log"
    log_file.write_text("2023-01-01 12:00:00 | INFO | Starting job\nJust a normal log line")

    sample_job.logs_location = str(log_file)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Patch _LOG_BASE to allow reading from tmp_path
    with patch("src.server.routes.jobs._LOG_BASE", tmp_path):
        response = client.get("/api/v2/jobs/job-123")

    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["logs"][0]["level"] == "INFO"
    assert data["logs"][0]["message"] == "Starting job"
    assert data["logs"][1]["message"] == "Just a normal log line"


def test_cancel_job(sample_job):
    # cancel_job revokes celery first, then looks up the job
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.commit = AsyncMock()

    with patch("src.server.celery_app.celery_app") as mock_celery:
        response = client.post("/api/v2/jobs/job-123/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        mock_celery.control.revoke.assert_called_once_with("job-123", terminate=True)
        assert sample_job.status == JobStatus.CANCELLED
        mock_db_session.commit.assert_called()
