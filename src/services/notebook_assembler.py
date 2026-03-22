"""
Notebook Assembler Service.

Handles the physical assembly of the final Jupyter Notebook artifact from
various analysis components (profile cells, analysis cells, markdown reports).
"""

import nbformat
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from src.models.state import AnalysisState, Phase
from src.models.handoffs import FinalAssemblyHandoff
from src.config import settings
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

logger = get_logger()


class NotebookAssembler:
    """
    Service to assemble and save Jupyter Notebooks.
    """

    @staticmethod
    def assemble_notebook(
        state: AnalysisState, assembly_handoff: FinalAssemblyHandoff
    ) -> Dict[str, Any]:
        """
        Assemble the final Jupyter Notebook artifact.

        Args:
            state: Current state.
            assembly_handoff: The structured content to assemble.

        Returns:
            Dictionary containing the final notebook path and quality metrics.
        """
        if assembly_handoff is None:
            return {"error": "No assembly handoff provided", "confidence": 0.0}

        # Create notebook structure
        nb = nbformat.v4.new_notebook()

        # Determine if this is an exploratory-only analysis (no Phase 2)
        has_analysis_phase = len(assembly_handoff.analysis_cells) > 0

        # Get display info
        model_name = getattr(
            settings.llm, f"{settings.llm.default_provider}_model", "unknown"
        )
        pipeline_mode = state.pipeline_mode
        if not pipeline_mode:
            mode_display = "Analysis"
        else:
            mode_display = (
                pipeline_mode.title()
                if isinstance(pipeline_mode, str)
                else pipeline_mode.value.title()
            )

        # =====================================================================
        # Section 1: Introduction
        # =====================================================================
        intro_cell = nbformat.v4.new_markdown_cell(
            f"# {assembly_handoff.notebook_title}\n\n"
            f"## 1. Introduction\n\n"
            f"{assembly_handoff.introduction_content}\n\n"
            f"---\n\n"
            f"**Inzyts**: {settings.app_version} | **Model**: {model_name} ({settings.llm.default_provider}) | **Mode**: {mode_display}\n\n"
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        nb.cells.append(intro_cell)

        # =====================================================================
        # Section 2: Data Profiling & Quality Assessment
        # =====================================================================
        profile_header = nbformat.v4.new_markdown_cell(
            "---\n\n"
            "## 2. Data Profiling & Quality Assessment\n\n"
            "Automated data quality checks, type detection, and statistical profiling."
        )
        nb.cells.append(profile_header)

        for cell in assembly_handoff.profile_cells:
            if cell.cell_type == "code":
                nb_cell = nbformat.v4.new_code_cell(cell.source)
            else:
                nb_cell = nbformat.v4.new_markdown_cell(cell.source)
            nb.cells.append(nb_cell)

        # =====================================================================
        # Section 3: Exploratory Analysis Conclusions (Always Present)
        # =====================================================================
        exploratory_header = nbformat.v4.new_markdown_cell(
            "---\n\n"
            "## 3. Exploratory Analysis Conclusions\n\n"
            "Insights generated based on your specific questions and data profile."
        )
        nb.cells.append(exploratory_header)

        if assembly_handoff.exploratory_cells:
            for cell in assembly_handoff.exploratory_cells:
                if cell.cell_type == "code":
                    nb_cell = nbformat.v4.new_code_cell(cell.source)
                else:
                    nb_cell = nbformat.v4.new_markdown_cell(cell.source)
                nb.cells.append(nb_cell)
        else:
            # Placeholder if no exploratory conclusions were generated
            placeholder = nbformat.v4.new_markdown_cell(
                "*No additional exploratory conclusions were generated for this analysis.*"
            )
            nb.cells.append(placeholder)

        # =====================================================================
        # Section 4: Analysis Phase (Only for Predictive/Modeling Modes)
        # =====================================================================
        if has_analysis_phase:
            analysis_header = nbformat.v4.new_markdown_cell(
                "---\n\n"
                f"## 4. {mode_display} Analysis\n\n"
                f"*Profile locked. Proceeding with {mode_display.lower()} modeling and evaluation.*"
            )
            nb.cells.append(analysis_header)

            for cell in assembly_handoff.analysis_cells:
                if cell.cell_type == "code":
                    nb_cell = nbformat.v4.new_code_cell(cell.source)
                else:
                    nb_cell = nbformat.v4.new_markdown_cell(cell.source)
                nb.cells.append(nb_cell)

        # =====================================================================
        # Section 5 (or 4 for Exploratory): Summary & Recommendations
        # =====================================================================
        summary_section_num = "5" if has_analysis_phase else "4"
        conclusion_cell = nbformat.v4.new_markdown_cell(
            f"---\n\n"
            f"## {summary_section_num}. Summary & Recommendations\n\n"
            f"{assembly_handoff.conclusion_content}\n\n"
            f"### Execution Metrics\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Total Time | {assembly_handoff.total_execution_time:.2f}s |\n"
            f"| Iterations | {assembly_handoff.total_iterations} |\n"
            f"| Phase 1 Quality | {assembly_handoff.phase1_quality_score:.2f} |\n"
            f"| Phase 2 Quality | {assembly_handoff.phase2_quality_score:.2f} |"
        )
        nb.cells.append(conclusion_cell)

        # 7. Save to Disk
        output_dir = Path(settings.output_dir)
        ensure_dir(output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_name = Path(state.csv_path).stem
        notebook_path = output_dir / f"analysis_{csv_name}_{timestamp}.ipynb"

        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        # 8. Copy Data file to Output Directory for portable/live execution
        destination_csv_path = output_dir / Path(state.csv_path).name
        # Avoid self-copy error if paths are identical
        if Path(state.csv_path).resolve() != destination_csv_path.resolve():
            try:
                shutil.copy2(state.csv_path, destination_csv_path)
            except Exception as e:
                logger.error(f"Failed to copy data file to output directory: {e}")

        return {
            "final_notebook_path": str(notebook_path),
            "current_phase": Phase.COMPLETE,
            "final_quality_score": (
                assembly_handoff.phase1_quality_score
                + assembly_handoff.phase2_quality_score
            )
            / 2,
            "confidence": 1.0,
        }
