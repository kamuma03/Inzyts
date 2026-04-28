import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User, UserRole

mock_db_session = AsyncMock()

def _fake_user():
    # /analyze now requires Analyst+. Tests model the post-RBAC contract.
    return User(
        id="test-user-id",
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
def mock_cost_estimator():
    with patch("src.server.routes.analysis.cost_estimator") as mock_est:
        mock_est.estimate_job_cost.return_value = {"total": 0.50, "estimated_cost_usd": 0.50}
        yield mock_est

@pytest.fixture
def mock_execution_task():
    with patch("src.server.services.engine.execution_task") as mock_task:
        yield mock_task

def test_analyze_success(mock_cost_estimator, mock_execution_task, tmp_path):
    # Create a real file within a tmp dir that we'll treat as data/uploads
    test_csv = tmp_path / "test.csv"
    test_csv.write_text("a,b\n1,2")

    with patch("src.server.routes.analysis._UPLOAD_DIR", tmp_path):
        payload = {
            "csv_path": str(test_csv),
            "mode": "exploratory",
            "title": "My Test Analysis",
            "question": "What is the trend?",
            "target_column": "sales"
        }

        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = client.post("/api/v2/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"

    # Verify task triggered
    mock_execution_task.apply_async.assert_called_once()
    kwargs = mock_execution_task.apply_async.call_args[1]["kwargs"]
    assert kwargs["csv_path"] == str(test_csv)
    assert kwargs["mode"] == "exploratory"

def test_analyze_task_queue_failure(mock_cost_estimator, mock_execution_task, tmp_path):
    test_csv = tmp_path / "test.csv"
    test_csv.write_text("a,b\n1,2")

    with patch("src.server.routes.analysis._UPLOAD_DIR", tmp_path):
        payload = {
            "csv_path": str(test_csv),
            "mode": "exploratory"
        }

        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Simulate Celery failure
        mock_execution_task.apply_async.side_effect = Exception("Celery down")

        response = client.post("/api/v2/analyze", json=payload)

    # The endpoint now raises HTTPException(status_code=500)
    assert response.status_code == 500

def test_analyze_validation_error():
    # csv_path is optional, but without csv_path or db_uri the endpoint returns 400
    payload = {
        "mode": "exploratory"
    }
    response = client.post("/api/v2/analyze", json=payload)

    # No csv_path, db_uri, cloud_uri, or api_url -> 400
    assert response.status_code == 400
    assert "data source" in response.json()["detail"].lower()


def test_analyze_cloud_uri(mock_cost_estimator, mock_execution_task, tmp_path):
    """Cloud URI triggers cloud ingestion and produces a csv_path."""
    mock_db_session.add = MagicMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    ingested_csv = str(tmp_path / "cloud_abc.csv")
    # Create the file so path validation passes
    (tmp_path / "cloud_abc.csv").write_text("a,b\n1,2")

    with patch("src.server.routes.analysis._UPLOAD_DIR", tmp_path), \
         patch("src.server.services.cloud_ingestion.ingest_from_cloud", return_value=ingested_csv):
        payload = {
            "cloud_uri": "s3://my-bucket/data.csv",
            "mode": "exploratory",
        }
        response = client.post("/api/v2/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data

    kwargs = mock_execution_task.apply_async.call_args[1]["kwargs"]
    assert kwargs["csv_path"] == ingested_csv


def test_analyze_cloud_uri_failure(mock_cost_estimator, mock_execution_task):
    """Cloud ingestion failure returns 400."""
    mock_db_session.add = MagicMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch("src.server.services.cloud_ingestion.ingest_from_cloud", side_effect=ValueError("Invalid scheme")):
        payload = {
            "cloud_uri": "ftp://bad/data.csv",
            "mode": "exploratory",
        }
        response = client.post("/api/v2/analyze", json=payload)

    assert response.status_code == 400


def test_analyze_api_url(mock_cost_estimator, mock_execution_task):
    """API URL is passed through to Celery task kwargs (csv_path stays None)."""
    mock_db_session.add = MagicMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    payload = {
        "api_url": "https://api.example.com/data",
        "api_headers": {"X-Custom": "value"},
        "api_auth": {"type": "bearer", "token": "abc"},
        "json_path": "data.items",
        "mode": "exploratory",
    }
    response = client.post("/api/v2/analyze", json=payload)

    assert response.status_code == 200
    kwargs = mock_execution_task.apply_async.call_args[1]["kwargs"]
    assert kwargs["api_url"] == "https://api.example.com/data"
    assert kwargs["api_headers"] == {"X-Custom": "value"}
    assert kwargs["api_auth"] == {"type": "bearer", "token": "abc"}
    assert kwargs["json_path"] == "data.items"
    # csv_path should be None since API extraction happens in workflow
    assert kwargs["csv_path"] is None


class TestSuggestMode:
    """Tests for the POST /suggest-mode endpoint."""

    @patch("src.services.mode_detector.ModeDetector")
    def test_suggest_mode_with_question_keywords(self, mock_detector_cls):
        from src.models._handoffs import PipelineMode

        mock_detector = MagicMock()
        mock_detector.determine_mode.return_value = (PipelineMode.FORECASTING, "inferred_keyword")
        mock_detector_cls.return_value = mock_detector

        response = client.post("/api/v2/suggest-mode", json={
            "question": "Forecast next month sales",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["suggested_mode"] == "forecasting"
        assert data["detection_method"] == "inferred_keyword"
        assert data["confidence"] == "medium"
        assert len(data["explanation"]) > 0

    @patch("src.services.mode_detector.ModeDetector")
    def test_suggest_mode_with_target_column(self, mock_detector_cls):
        from src.models._handoffs import PipelineMode

        mock_detector = MagicMock()
        mock_detector.determine_mode.return_value = (PipelineMode.PREDICTIVE, "target_column")
        mock_detector_cls.return_value = mock_detector

        response = client.post("/api/v2/suggest-mode", json={
            "target_column": "churn",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["suggested_mode"] == "predictive"
        assert data["confidence"] == "high"

    @patch("src.services.mode_detector.ModeDetector")
    def test_suggest_mode_default_exploratory(self, mock_detector_cls):
        from src.models._handoffs import PipelineMode

        mock_detector = MagicMock()
        mock_detector.determine_mode.return_value = (PipelineMode.EXPLORATORY, "default")
        mock_detector_cls.return_value = mock_detector

        response = client.post("/api/v2/suggest-mode", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["suggested_mode"] == "exploratory"
        assert data["confidence"] == "low"

    @patch("src.services.mode_detector.ModeDetector")
    def test_suggest_mode_dimensionality_maps_correctly(self, mock_detector_cls):
        """PipelineMode.DIMENSIONALITY should map back to AnalysisMode.DIMENSIONALITY_REDUCTION."""
        from src.models._handoffs import PipelineMode

        mock_detector = MagicMock()
        mock_detector.determine_mode.return_value = (PipelineMode.DIMENSIONALITY, "inferred_keyword")
        mock_detector_cls.return_value = mock_detector

        response = client.post("/api/v2/suggest-mode", json={
            "question": "Run PCA on this dataset",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["suggested_mode"] == "dimensionality"

    @patch("src.services.mode_detector.ModeDetector")
    def test_suggest_mode_with_both_question_and_target(self, mock_detector_cls):
        """Both question and target_column can be provided."""
        from src.models._handoffs import PipelineMode

        mock_detector = MagicMock()
        mock_detector.determine_mode.return_value = (PipelineMode.PREDICTIVE, "target_column")
        mock_detector_cls.return_value = mock_detector

        response = client.post("/api/v2/suggest-mode", json={
            "question": "What drives churn?",
            "target_column": "churn",
        })

        assert response.status_code == 200
        mock_detector.determine_mode.assert_called_once_with(
            mode_arg=None,
            target_column="churn",
            user_question="What drives churn?",
        )
