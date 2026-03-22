"""
Executive Summary Generator.

LLM-powered service that generates concise executive summaries from
completed analysis notebooks. Falls back to extracting conclusion text
from the notebook when LLM is unavailable or times out.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Dict, List, Optional

import nbformat
from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger()


class ExecutiveSummary(BaseModel):
    """Structured executive summary of an analysis."""

    key_findings: List[str]
    data_quality_highlights: List[str]
    recommendations: List[str]
    summary_text: str
    generated_by: str  # "llm" or "fallback"


_SYSTEM_PROMPT = """\
You are a senior data analyst writing an executive summary for a data analysis report.

Given the notebook content below, produce a concise executive summary as JSON with these fields:
- "key_findings": array of 3-5 bullet-point strings summarizing the most important discoveries
- "data_quality_highlights": array of 1-3 strings about data quality, completeness, or issues found
- "recommendations": array of 2-4 actionable next-step strings
- "summary_text": a 2-3 paragraph prose summary suitable for a non-technical audience

Be specific and reference actual metrics, columns, or patterns from the analysis.
Do NOT include generic filler — every bullet must be grounded in the provided content."""


class ExecutiveSummaryGenerator:
    """Generates executive summaries from analysis notebooks."""

    def __init__(self):
        self._llm_agent = None  # Lazy init to avoid import-time LLM setup

    def _get_llm_agent(self):
        """Lazily create LLMAgent to avoid import-time initialization."""
        if self._llm_agent is None:
            from src.llm.provider import LLMAgent

            self._llm_agent = LLMAgent(
                name="Executive Summary Generator",
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.3,
            )
        return self._llm_agent

    def generate(
        self, notebook_path: str, timeout_seconds: int = 60
    ) -> ExecutiveSummary:
        """Generate an executive summary from a completed notebook.

        Attempts LLM generation with a timeout. Falls back to extracting
        conclusion text directly from the notebook on any failure.

        Args:
            notebook_path: Path to the .ipynb file.
            timeout_seconds: Maximum seconds to wait for LLM response.

        Returns:
            ExecutiveSummary with findings, recommendations, and prose summary.
        """
        content = self._extract_notebook_content(notebook_path)
        if not content:
            return self._empty_summary()

        # Try LLM generation with timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._invoke_llm, content)
                result = future.result(timeout=timeout_seconds)
                if result is not None:
                    return result
        except FuturesTimeoutError:
            logger.warning(
                "Executive summary LLM call timed out after "
                f"{timeout_seconds}s, using fallback"
            )
        except Exception as e:
            logger.warning(f"Executive summary LLM call failed: {e}, using fallback")

        return self._fallback(content)

    def _invoke_llm(self, content: Dict[str, str]) -> Optional[ExecutiveSummary]:
        """Call LLM to generate structured executive summary."""
        prompt = self._build_prompt(content)
        agent = self._get_llm_agent()

        raw = agent.invoke_with_json(prompt)
        try:
            data = json.loads(raw)
            return ExecutiveSummary(
                key_findings=data.get("key_findings", []),
                data_quality_highlights=data.get("data_quality_highlights", []),
                recommendations=data.get("recommendations", []),
                summary_text=data.get("summary_text", ""),
                generated_by="llm",
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM executive summary response: {e}")
            return None

    def _build_prompt(self, content: Dict[str, str]) -> str:
        """Build the user prompt from extracted notebook content."""
        sections = []
        if content.get("introduction"):
            sections.append(f"## Introduction\n{content['introduction']}")
        if content.get("profiling_summary"):
            sections.append(
                f"## Data Profiling\n{content['profiling_summary']}"
            )
        if content.get("exploratory_conclusions"):
            sections.append(
                f"## Exploratory Conclusions\n{content['exploratory_conclusions']}"
            )
        if content.get("analysis_content"):
            sections.append(f"## Analysis\n{content['analysis_content']}")
        if content.get("conclusions"):
            sections.append(
                f"## Summary & Recommendations\n{content['conclusions']}"
            )
        if content.get("execution_metrics"):
            sections.append(
                f"## Execution Metrics\n{content['execution_metrics']}"
            )

        notebook_text = "\n\n".join(sections)

        # Truncate if too long (keep under ~8k chars to leave room for response)
        max_chars = 8000
        if len(notebook_text) > max_chars:
            notebook_text = notebook_text[:max_chars] + "\n\n[... truncated]"

        return (
            f"Generate an executive summary for the following data analysis report:\n\n"
            f"{notebook_text}"
        )

    def _extract_notebook_content(self, notebook_path: str) -> Dict[str, str]:
        """Extract text content from notebook cells organized by section.

        Parses the notebook structure created by NotebookAssembler:
        - Section 1: Introduction
        - Section 2: Data Profiling & Quality Assessment
        - Section 3: Exploratory Analysis Conclusions
        - Section 4: Analysis Phase (optional)
        - Section N: Summary & Recommendations
        """
        path = Path(notebook_path)
        if not path.exists():
            logger.warning(f"Executive summary: notebook not found at {notebook_path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                nb = nbformat.read(f, as_version=4)
        except Exception as e:
            logger.error(f"Executive summary: failed to read notebook: {e}")
            return {}

        content: Dict[str, str] = {}
        current_section = ""
        section_texts: Dict[str, List[str]] = {}

        # Section header patterns from notebook_assembler.py
        section_patterns = [
            (r"##\s*1\.\s*Introduction", "introduction"),
            (r"##\s*2\.\s*Data Profiling", "profiling_summary"),
            (r"##\s*3\.\s*Exploratory Analysis", "exploratory_conclusions"),
            (r"##\s*4\.\s*.*Analysis", "analysis_content"),
            (r"##\s*\d+\.\s*Summary & Recommendations", "conclusions"),
        ]

        for cell in nb.cells:
            if cell.cell_type != "markdown":
                continue

            text = cell.source.strip()

            # Check if this cell starts a new section
            matched_section = None
            for pattern, section_key in section_patterns:
                if re.search(pattern, text):
                    matched_section = section_key
                    break

            if matched_section:
                current_section = matched_section
                if current_section not in section_texts:
                    section_texts[current_section] = []
                # Add the cell text minus the header line
                lines = text.split("\n")
                remaining = "\n".join(lines[1:]).strip()
                if remaining:
                    section_texts[current_section].append(remaining)
            elif current_section:
                if current_section not in section_texts:
                    section_texts[current_section] = []
                section_texts[current_section].append(text)

        for key, texts in section_texts.items():
            content[key] = "\n\n".join(texts)

        return content

    def _fallback(self, content: Dict[str, str]) -> ExecutiveSummary:
        """Generate a basic summary without LLM by extracting notebook text.

        Splits conclusion text into bullet points and uses introduction
        as the summary text.
        """
        conclusions = content.get("conclusions", "")
        introduction = content.get("introduction", "")

        # Split conclusions into bullet-point-like findings
        key_findings = []
        for line in conclusions.split("\n"):
            line = line.strip()
            if line and not line.startswith("|") and not line.startswith("---"):
                # Strip markdown bullet markers
                clean = re.sub(r"^[-*]\s*", "", line)
                if clean and len(clean) > 10:
                    key_findings.append(clean)

        # Cap at 5 findings
        key_findings = key_findings[:5]
        if not key_findings:
            key_findings = ["Analysis completed. See full report for details."]

        # Extract quality mentions from profiling section
        profiling = content.get("profiling_summary", "")
        quality_highlights = []
        for line in profiling.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 10:
                quality_highlights.append(re.sub(r"^[-*]\s*", "", line))
        quality_highlights = quality_highlights[:3]
        if not quality_highlights:
            quality_highlights = ["Data profiling completed successfully."]

        summary_text = introduction if introduction else conclusions[:500]

        return ExecutiveSummary(
            key_findings=key_findings,
            data_quality_highlights=quality_highlights,
            recommendations=[
                "Review the detailed findings in the full notebook.",
                "Consider follow-up analysis on highlighted patterns.",
            ],
            summary_text=summary_text,
            generated_by="fallback",
        )

    def _empty_summary(self) -> ExecutiveSummary:
        """Return a minimal summary when no content is available."""
        return ExecutiveSummary(
            key_findings=["No analysis content available."],
            data_quality_highlights=[],
            recommendations=[],
            summary_text="The notebook could not be read for summary generation.",
            generated_by="fallback",
        )
