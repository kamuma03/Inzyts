"""Tests for Report Exporter Service."""

import pytest
import nbformat
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services.report_exporter import ReportExporter, ReportFormat, ReportResult
from src.services.executive_summary import ExecutiveSummary
from src.services.pii_detector import PIIScanResult, PIIFinding


def _make_full_notebook(tmp_path):
    """Create a full test notebook with all sections and code outputs."""
    nb = nbformat.v4.new_notebook()

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "# Sales Analysis\n\n## 1. Introduction\n\n"
        "Analysis of Q3 2025 sales data.\n\n---\n\n"
        "**Inzyts**: 0.10.0 | **Model**: claude-3-5-sonnet | **Mode**: Exploratory\n\n"
        "*Generated on 2025-12-01 10:00:00*"
    ))

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "---\n\n## 2. Data Profiling & Quality Assessment\n\n"
        "1000 rows, 15 columns. Missing: 2.5%."
    ))
    code_cell = nbformat.v4.new_code_cell("import pandas as pd\ndf.describe()")
    code_cell.outputs = [
        nbformat.v4.new_output(output_type="stream", text="count    1000\nmean     50.5"),
    ]
    nb.cells.append(code_cell)

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "---\n\n## 3. Exploratory Analysis Conclusions\n\n"
        "Revenue grew 15%. Churn decreased."
    ))

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "---\n\n## 4. Summary & Recommendations\n\n"
        "- Revenue is strong\n- Retention improved\n\n"
        "### Execution Metrics\n\n"
        "| Metric | Value |\n|--------|-------|\n"
        "| Total Time | 45.20s |\n| Iterations | 3 |\n"
        "| Phase 1 Quality | 0.92 |\n| Phase 2 Quality | 0.88 |"
    ))

    path = tmp_path / "analysis_test.ipynb"
    with open(path, "w") as f:
        nbformat.write(nb, f)
    return str(path)


@pytest.fixture
def notebook_path(tmp_path):
    return _make_full_notebook(tmp_path)


@pytest.fixture
def job_metadata():
    return {
        "job_id": "test-job-123",
        "mode": "Exploratory",
        "title": "Sales Analysis Report",
        "question": "What drove Q3 revenue?",
        "model": "claude-3-5-sonnet",
        "version": "0.10.0",
    }


@pytest.fixture
def exporter():
    return ReportExporter()


class TestReportExporterHTML:
    """Tests for HTML report generation."""

    def test_export_html_success(self, exporter, notebook_path, job_metadata, tmp_path):
        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            # Mock the summary generator to avoid LLM calls
            mock_summary = ExecutiveSummary(
                key_findings=["Revenue up 15%"],
                data_quality_highlights=["92% complete"],
                recommendations=["Invest in retention"],
                summary_text="Strong growth in Q3.",
                generated_by="fallback",
            )
            with patch.object(exporter._summary_generator, 'generate', return_value=mock_summary):
                result = exporter.export(
                    notebook_path=notebook_path,
                    job_metadata=job_metadata,
                    format=ReportFormat.HTML,
                )

        assert isinstance(result, ReportResult)
        assert result.format == ReportFormat.HTML
        assert result.file_size_bytes > 0
        assert result.has_executive_summary is True
        assert Path(result.file_path).exists()

        # Verify HTML content
        html = Path(result.file_path).read_text()
        assert "Sales Analysis Report" in html
        assert "Revenue up 15%" in html
        assert "Inzyts" in html

    def test_export_html_without_summary(self, exporter, notebook_path, job_metadata, tmp_path):
        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            result = exporter.export(
                notebook_path=notebook_path,
                job_metadata=job_metadata,
                format=ReportFormat.HTML,
                include_executive_summary=False,
            )

        assert result.has_executive_summary is False

    def test_export_html_with_pii_masking(self, exporter, tmp_path, job_metadata):
        # Create notebook with PII
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell(
            "## 1. Introduction\n\nContact: alice@example.com"
        ))
        nb.cells.append(nbformat.v4.new_markdown_cell(
            "---\n\n## 2. Summary & Recommendations\n\nDone."
        ))
        path = tmp_path / "pii_nb.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            result = exporter.export(
                notebook_path=str(path),
                job_metadata=job_metadata,
                format=ReportFormat.HTML,
                include_executive_summary=False,
                include_pii_masking=True,
            )

        html = Path(result.file_path).read_text()
        assert "alice@example.com" not in html
        assert "[EMAIL]" in html


class TestReportExporterMarkdown:
    """Tests for Markdown report generation."""

    def test_export_markdown_success(self, exporter, notebook_path, job_metadata, tmp_path):
        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            mock_summary = ExecutiveSummary(
                key_findings=["Revenue up 15%"],
                data_quality_highlights=["Good quality"],
                recommendations=["Keep going"],
                summary_text="Growth is strong.",
                generated_by="fallback",
            )
            with patch.object(exporter._summary_generator, 'generate', return_value=mock_summary):
                result = exporter.export(
                    notebook_path=notebook_path,
                    job_metadata=job_metadata,
                    format=ReportFormat.MARKDOWN,
                )

        assert result.format == ReportFormat.MARKDOWN
        assert result.file_path.endswith(".md")

        md = Path(result.file_path).read_text()
        assert "# Sales Analysis Report" in md
        assert "## Executive Summary" in md
        assert "Revenue up 15%" in md
        assert "## Execution Metrics" in md
        assert "Total Time" in md

    def test_export_markdown_with_pii_warning(self, exporter, tmp_path, job_metadata):
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell(
            "## 1. Intro\n\nContact: bob@test.com"
        ))
        path = tmp_path / "pii_md.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            result = exporter.export(
                notebook_path=str(path),
                job_metadata=job_metadata,
                format=ReportFormat.MARKDOWN,
                include_executive_summary=False,
            )

        md = Path(result.file_path).read_text()
        assert "PII Warning" in md


class TestReportExporterPDF:
    """Tests for PDF report generation."""

    def test_pdf_raises_without_weasyprint(self, exporter, notebook_path, job_metadata, tmp_path):
        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            with patch.dict("sys.modules", {"weasyprint": None}):
                with patch.object(exporter, '_render_pdf', side_effect=RuntimeError("PDF export requires weasyprint")):
                    with pytest.raises(RuntimeError, match="weasyprint"):
                        exporter.export(
                            notebook_path=notebook_path,
                            job_metadata=job_metadata,
                            format=ReportFormat.PDF,
                            include_executive_summary=False,
                        )


class TestReportExporterPPTX:
    """Tests for PPTX report generation."""

    def test_pptx_raises_without_python_pptx(self, exporter, notebook_path, job_metadata, tmp_path):
        with patch("src.services.report_exporter.settings") as mock_settings:
            mock_settings.output_dir = str(tmp_path)

            with patch.object(exporter, '_render_pptx', side_effect=RuntimeError("PPTX export requires python-pptx")):
                with pytest.raises(RuntimeError, match="python-pptx"):
                    exporter.export(
                        notebook_path=notebook_path,
                        job_metadata=job_metadata,
                        format=ReportFormat.PPTX,
                        include_executive_summary=False,
                    )


class TestReportExporterParsing:
    """Tests for notebook parsing and metrics extraction."""

    def test_extract_metrics(self, exporter, notebook_path):
        nb = exporter._read_notebook(notebook_path)
        metrics = exporter._extract_metrics(nb)

        assert "Total Time" in metrics
        assert metrics["Total Time"] == "45.20s"
        assert "Iterations" in metrics
        assert metrics["Iterations"] == "3"

    def test_parse_sections(self, exporter, notebook_path):
        nb = exporter._read_notebook(notebook_path)
        sections = exporter._parse_sections(nb)

        assert len(sections) >= 3
        titles = [s.title for s in sections]
        assert "Introduction" in titles
        assert "Data Profiling & Quality Assessment" in titles

    def test_read_notebook_missing(self, exporter):
        result = exporter._read_notebook("/nonexistent.ipynb")
        assert result is None

    def test_read_notebook_valid(self, exporter, notebook_path):
        result = exporter._read_notebook(notebook_path)
        assert result is not None
        assert len(result.cells) > 0

    def test_export_invalid_notebook(self, exporter, job_metadata):
        with pytest.raises(ValueError, match="Could not read"):
            exporter.export(
                notebook_path="/nonexistent.ipynb",
                job_metadata=job_metadata,
            )


class TestReportResult:
    """Tests for ReportResult model."""

    def test_creation(self):
        r = ReportResult(
            format=ReportFormat.HTML,
            file_path="/tmp/report.html",
            file_size_bytes=1024,
            generation_time_seconds=1.5,
            has_executive_summary=True,
            has_pii_warnings=False,
        )
        assert r.format == ReportFormat.HTML
        assert r.file_size_bytes == 1024

    def test_serialization(self):
        r = ReportResult(
            format=ReportFormat.PDF,
            file_path="/tmp/report.pdf",
            file_size_bytes=2048,
            generation_time_seconds=3.0,
            has_executive_summary=False,
            has_pii_warnings=True,
        )
        data = r.model_dump()
        assert data["format"] == "pdf"
        assert data["has_pii_warnings"] is True


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_all_formats(self):
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.PPTX.value == "pptx"
        assert ReportFormat.MARKDOWN.value == "markdown"

    def test_from_string(self):
        assert ReportFormat("html") == ReportFormat.HTML
        assert ReportFormat("pptx") == ReportFormat.PPTX
