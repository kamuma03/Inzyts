import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User

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


def test_get_job_metrics_job_not_found():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

def test_get_job_metrics_no_csv():
    mock_job = MagicMock()
    mock_job.csv_path = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "No CSV file associated with this job"

def test_get_job_metrics_csv_not_found(tmp_path):
    missing_csv = tmp_path / "missing.csv"
    mock_job = MagicMock()
    mock_job.csv_path = str(missing_csv)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    assert "CSV file not found" in response.json()["detail"]

@patch("src.server.services.metrics_service.metrics_service.get_job_metrics")
def test_get_job_metrics_success(mock_get_metrics, tmp_path):
    valid_csv = tmp_path / "valid.csv"
    valid_csv.touch()

    mock_job = MagicMock()
    mock_job.csv_path = str(valid_csv)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_get_metrics.return_value = {"status": "ok", "stats": {}}

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stats": {}}
    mock_get_metrics.assert_called_once()

@patch("src.server.services.metrics_service.metrics_service.get_job_metrics")
def test_get_job_metrics_exception(mock_get_metrics, tmp_path):
    valid_csv = tmp_path / "valid.csv"
    valid_csv.touch()

    mock_job = MagicMock()
    mock_job.csv_path = str(valid_csv)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_get_metrics.side_effect = Exception("Metrics failure")

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 500
    assert "Failed to compute metrics" in response.json()["detail"]
