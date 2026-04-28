import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User, UserRole

mock_db_session = AsyncMock()

_TEST_USER_ID = "test-user-id"


def _fake_user():
    return User(
        id=_TEST_USER_ID,
        username="testuser",
        is_active=True,
        role=UserRole.ANALYST,
    )


@pytest.fixture(autouse=True)
def apply_dependency_overrides(tmp_path):
    """Stub auth+db and point the metrics path-validator at tmp_path so
    test CSVs created under tmp_path pass the upload-dir guard."""
    fastapi_app.dependency_overrides[verify_token] = _fake_user
    fastapi_app.dependency_overrides[get_db] = lambda: mock_db_session
    # The route binds `_UPLOAD_DIR` / `_DATASETS_DIR` at module load.
    # Patch them so test CSVs under tmp_path satisfy the path-traversal guard.
    with patch(
        "src.server.routes.metrics._UPLOAD_DIR", new=tmp_path.resolve()
    ), patch(
        "src.server.routes.metrics._DATASETS_DIR", new=None
    ):
        yield
    fastapi_app.dependency_overrides.clear()


client = TestClient(fastapi_app)


def _owned_job(**overrides):
    """Helper — a MagicMock job owned by the fake test user."""
    mock_job = MagicMock()
    mock_job.user_id = _TEST_USER_ID
    for k, v in overrides.items():
        setattr(mock_job, k, v)
    return mock_job


def test_get_job_metrics_job_not_found():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

def test_get_job_metrics_no_csv():
    mock_job = _owned_job(csv_path=None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "No CSV file associated with this job"

def test_get_job_metrics_csv_not_found(tmp_path):
    missing_csv = tmp_path / "missing.csv"
    mock_job = _owned_job(csv_path=str(missing_csv))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
    # Message is now generic to avoid leaking which directory was rejected.
    assert response.json()["detail"] == "CSV file not found"

@patch("src.server.services.metrics_service.metrics_service.get_job_metrics")
def test_get_job_metrics_success(mock_get_metrics, tmp_path):
    valid_csv = tmp_path / "valid.csv"
    valid_csv.touch()

    mock_job = _owned_job(csv_path=str(valid_csv))
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

    mock_job = _owned_job(csv_path=str(valid_csv))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_get_metrics.side_effect = Exception("Metrics failure")

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 500
    # Detail no longer leaks the underlying exception message.
    assert response.json()["detail"] == "Failed to compute metrics"


def test_get_job_metrics_cross_user_returns_404(tmp_path):
    """A job owned by a different user is invisible (404, not 403)."""
    other_csv = tmp_path / "other.csv"
    other_csv.touch()

    mock_job = MagicMock()
    mock_job.user_id = "some-other-user"
    mock_job.csv_path = str(other_csv)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v2/metrics/job-123")
    assert response.status_code == 404
