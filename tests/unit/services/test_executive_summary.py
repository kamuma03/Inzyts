"""Tests for Executive Summary Generator."""

import json
import pytest
import nbformat
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.services.executive_summary import ExecutiveSummary, ExecutiveSummaryGenerator


class TestExecutiveSummaryModel:
    """Tests for the ExecutiveSummary Pydantic model."""

    def test_creation(self):
        s = ExecutiveSummary(
            key_findings=["Finding 1", "Finding 2"],
            data_quality_highlights=["Good quality"],
            recommendations=["Do X"],
            summary_text="Summary here",
            generated_by="llm",
        )
        assert len(s.key_findings) == 2
        assert s.generated_by == "llm"

    def test_serialization(self):
        s = ExecutiveSummary(
            key_findings=["A"],
            data_quality_highlights=[],
            recommendations=[],
            summary_text="Text",
            generated_by="fallback",
        )
        data = s.model_dump()
        assert data["generated_by"] == "fallback"
        assert isinstance(data["key_findings"], list)


def _make_test_notebook(tmp_path, include_conclusions=True, include_profiling=True):
    """Create a realistic test notebook following NotebookAssembler structure."""
    nb = nbformat.v4.new_notebook()

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "# Test Analysis\n\n## 1. Introduction\n\n"
        "This analysis explores sales data for Q3 2025."
    ))

    if include_profiling:
        nb.cells.append(nbformat.v4.new_markdown_cell(
            "---\n\n## 2. Data Profiling & Quality Assessment\n\n"
            "The dataset contains 1000 rows and 15 columns.\n"
            "Missing values: 2.5% overall.\n"
            "Data quality score: 0.92"
        ))

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "---\n\n## 3. Exploratory Analysis Conclusions\n\n"
        "Revenue grew 15% year-over-year.\n"
        "Customer churn decreased in Q3."
    ))

    if include_conclusions:
        nb.cells.append(nbformat.v4.new_markdown_cell(
            "---\n\n## 4. Summary & Recommendations\n\n"
            "- Revenue growth is strong at 15% YoY\n"
            "- Customer retention improved significantly\n"
            "- Marketing spend efficiency increased by 20%\n\n"
            "### Execution Metrics\n\n"
            "| Metric | Value |\n|--------|-------|\n"
            "| Total Time | 45.20s |\n| Iterations | 3 |"
        ))

    path = tmp_path / "test_analysis.ipynb"
    with open(path, "w") as f:
        nbformat.write(nb, f)
    return str(path)


class TestExecutiveSummaryGenerator:
    """Tests for ExecutiveSummaryGenerator."""

    def test_fallback_with_conclusions(self, tmp_path):
        """Fallback should extract bullet points from conclusions."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        # Force fallback by not initializing LLM
        with patch.object(gen, '_invoke_llm', return_value=None):
            result = gen.generate(path)

        assert isinstance(result, ExecutiveSummary)
        assert result.generated_by == "fallback"
        assert len(result.key_findings) > 0
        assert any("15%" in f or "Revenue" in f for f in result.key_findings)

    def test_fallback_with_profiling(self, tmp_path):
        """Fallback should extract quality highlights from profiling section."""
        path = _make_test_notebook(tmp_path, include_profiling=True)
        gen = ExecutiveSummaryGenerator()

        with patch.object(gen, '_invoke_llm', return_value=None):
            result = gen.generate(path)

        assert len(result.data_quality_highlights) > 0

    def test_fallback_minimal_notebook(self, tmp_path):
        """Fallback with minimal notebook returns sensible defaults."""
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell("# Minimal"))
        path = tmp_path / "minimal.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        gen = ExecutiveSummaryGenerator()
        with patch.object(gen, '_invoke_llm', return_value=None):
            result = gen.generate(str(path))

        assert result.generated_by == "fallback"
        assert len(result.key_findings) >= 1

    def test_missing_notebook_returns_empty(self):
        """Missing notebook returns empty summary."""
        gen = ExecutiveSummaryGenerator()
        result = gen.generate("/nonexistent/path.ipynb")
        assert result.generated_by == "fallback"
        assert "could not be read" in result.summary_text.lower()

    def test_llm_success(self, tmp_path):
        """LLM path returns structured summary."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        mock_summary = ExecutiveSummary(
            key_findings=["Sales up 15%", "Churn down 8%"],
            data_quality_highlights=["92% completeness"],
            recommendations=["Invest in retention"],
            summary_text="The analysis shows strong growth.",
            generated_by="llm",
        )
        with patch.object(gen, '_invoke_llm', return_value=mock_summary):
            result = gen.generate(path)

        assert result.generated_by == "llm"
        assert "Sales up 15%" in result.key_findings

    def test_llm_timeout_falls_back(self, tmp_path):
        """LLM timeout should trigger fallback gracefully."""
        from concurrent.futures import TimeoutError as FTE

        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        with patch.object(gen, '_invoke_llm', side_effect=FTE("timeout")):
            result = gen.generate(path, timeout_seconds=1)

        assert result.generated_by == "fallback"

    def test_llm_exception_falls_back(self, tmp_path):
        """Any LLM exception should trigger fallback."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        with patch.object(gen, '_invoke_llm', side_effect=RuntimeError("LLM down")):
            result = gen.generate(path, timeout_seconds=1)

        assert result.generated_by == "fallback"

    def test_extract_notebook_content(self, tmp_path):
        """Content extraction should find all sections."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        content = gen._extract_notebook_content(path)
        assert "introduction" in content
        assert "profiling_summary" in content
        assert "conclusions" in content

    def test_extract_notebook_missing_file(self):
        gen = ExecutiveSummaryGenerator()
        content = gen._extract_notebook_content("/nonexistent.ipynb")
        assert content == {}

    def test_build_prompt_truncates_long_content(self, tmp_path):
        """Prompt should be truncated if notebook content is too large."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()
        content = gen._extract_notebook_content(path)

        # Inflate content to trigger truncation
        content["conclusions"] = "A" * 10000
        prompt = gen._build_prompt(content)

        assert len(prompt) <= 9000  # 8000 char limit + prompt prefix

    def test_invoke_llm_parses_json(self, tmp_path):
        """_invoke_llm should parse JSON from LLM response."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        mock_agent = MagicMock()
        mock_agent.invoke_with_json.return_value = json.dumps({
            "key_findings": ["Finding A"],
            "data_quality_highlights": ["Good"],
            "recommendations": ["Do X"],
            "summary_text": "Summary.",
        })
        gen._llm_agent = mock_agent

        content = gen._extract_notebook_content(path)
        result = gen._invoke_llm(content)

        assert result is not None
        assert result.generated_by == "llm"
        assert result.key_findings == ["Finding A"]

    def test_invoke_llm_bad_json_returns_none(self, tmp_path):
        """Bad JSON from LLM should return None (triggers fallback)."""
        path = _make_test_notebook(tmp_path)
        gen = ExecutiveSummaryGenerator()

        mock_agent = MagicMock()
        mock_agent.invoke_with_json.return_value = "not valid json"
        gen._llm_agent = mock_agent

        content = gen._extract_notebook_content(path)
        result = gen._invoke_llm(content)

        assert result is None
