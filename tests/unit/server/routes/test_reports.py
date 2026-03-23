"""Tests for Report Export API Routes."""

import pytest
import nbformat
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.database import get_db
from src.server.db.models import User, Job

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


def _mock_job_with_notebook(tmp_path):
    """Create a mock Job with a real notebook file."""
    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_markdown_cell(
        "# Test\n\n## 1. Introduction\n\nTest analysis."
    ))
    nb.cells.append(nbformat.v4.new_markdown_cell(
        "---\n\n## 2. Summary & Recommendations\n\n- Finding 1\n\n"
        "### Execution Metrics\n\n"
        "| Metric | Value |\n|--------|-------|\n| Total Time | 10s |"
    ))
    path = tmp_path / "test.ipynb"
    with open(path, "w") as f:
        nbformat.write(nb, f)

    mock_job = MagicMock(spec=Job)
    mock_job.id = "job-123"
    mock_job.result_path = str(path)
    mock_job.mode = "exploratory"
    mock_job.title = "Test Analysis"
    mock_job.question = "What happened?"
    mock_job.executive_summary = None
    return mock_job


class TestExportReportGet:
    """Tests for GET /reports/{job_id}/export."""

    def test_export_html_success(self, tmp_path):
        mock_job = _mock_job_with_notebook(tmp_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.services.report_exporter.settings") as mock_settings, \
             patch("src.server.routes.reports._get_exporter") as mock_get_exporter:
            mock_settings.output_dir = str(tmp_path)
            mock_settings.app_version = "0.10.0"
            mock_settings.llm = MagicMock()
            mock_settings.llm.default_provider = "anthropic"
            mock_settings.llm.anthropic_model = "claude-3-5-sonnet"

            # Create a real HTML file that the exporter would produce
            report_path = tmp_path / "reports" / "report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html><body>Report</body></html>")

            mock_exporter = MagicMock()
            mock_exporter.export.return_value = MagicMock(
                file_path=str(report_path),
                has_executive_summary=True,
                has_pii_warnings=False,
            )
            mock_get_exporter.return_value = mock_exporter

            response = client.get("/api/v2/reports/job-123/export?format=html")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_export_invalid_format(self, tmp_path):
        mock_job = _mock_job_with_notebook(tmp_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/job-123/export?format=docx")
        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]

    def test_export_job_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/nonexistent/export?format=html")
        assert response.status_code == 404

    def test_export_no_notebook(self):
        mock_job = MagicMock(spec=Job)
        mock_job.id = "job-no-nb"
        mock_job.result_path = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/job-no-nb/export?format=html")
        assert response.status_code == 404
        assert "No notebook" in response.json()["detail"]


class TestExportReportPost:
    """Tests for POST /reports/{job_id}/export."""

    def test_export_post_with_options(self, tmp_path):
        mock_job = _mock_job_with_notebook(tmp_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        report_path = tmp_path / "reports" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Report")

        with patch("src.server.routes.reports._get_exporter") as mock_get_exporter:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = MagicMock(
                file_path=str(report_path),
                has_executive_summary=False,
                has_pii_warnings=True,
            )
            mock_get_exporter.return_value = mock_exporter

            response = client.post("/api/v2/reports/job-123/export", json={
                "format": "markdown",
                "include_executive_summary": False,
                "include_pii_masking": True,
            })

        assert response.status_code == 200


class TestExecutiveSummaryEndpoint:
    """Tests for GET /reports/{job_id}/executive-summary."""

    def test_get_summary_success(self, tmp_path):
        mock_job = _mock_job_with_notebook(tmp_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.services.executive_summary import ExecutiveSummary

        mock_summary = ExecutiveSummary(
            key_findings=["Sales up 15%"],
            data_quality_highlights=["92% complete"],
            recommendations=["Invest more"],
            summary_text="Strong growth.",
            generated_by="fallback",
        )

        with patch("src.server.routes.reports._get_summary_gen") as mock_gen:
            mock_gen.return_value.generate.return_value = mock_summary
            response = client.get("/api/v2/reports/job-123/executive-summary")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert "Sales up 15%" in data["key_findings"]
        assert data["generated_by"] == "fallback"

    def test_get_summary_job_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/nonexistent/executive-summary")
        assert response.status_code == 404


class TestPIIScanEndpoint:
    """Tests for GET /reports/{job_id}/pii-scan."""

    def test_pii_scan_success(self, tmp_path):
        mock_job = _mock_job_with_notebook(tmp_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/job-123/pii-scan")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert "has_pii" in data
        assert "findings" in data
        assert "scanned_cells" in data

    def test_pii_scan_with_pii(self, tmp_path):
        # Create notebook with PII
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell("Contact: alice@test.com"))
        path = tmp_path / "pii.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        mock_job = MagicMock(spec=Job)
        mock_job.id = "job-pii"
        mock_job.result_path = str(path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/job-pii/pii-scan")

        assert response.status_code == 200
        data = response.json()
        assert data["has_pii"] is True
        assert len(data["findings"]) >= 1
        assert data["findings"][0]["pii_type"] == "email"

    def test_pii_scan_job_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v2/reports/nonexistent/pii-scan")
        assert response.status_code == 404
