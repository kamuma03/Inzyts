"""
Analysis Code Generator Agent - Generates analysis/modeling notebook cells.

Matches the pattern of the Phase 1 Code Generator but for the Analysis phase.
It translates the abstract `StrategyToCodeGenHandoff` into concrete:
1. Feature Engineering code (pandas/sklearn).
2. Model Training code (fit/predict).
3. Evaluation code (metrics/plots).
"""

import json
from typing import Any, Dict, Optional

from src.utils.logger import get_logger
from src.utils.cache_manager import CacheManager

from src.agents.base import BaseAgent
from src.models.handoffs import (
    StrategyToCodeGenHandoff,
    AnalysisCodeToValidatorHandoff,
)
from src.models.state import AnalysisState, Phase
from src.models.cells import NotebookCell, CellManifest
from src.prompts import ANALYSIS_CODEGEN_PROMPT

# Import Helper Classes
from src.agents.phase2.template_generator import TemplateGenerator
from src.agents.phase2.code_injector import CodeInjector
from src.agents.phase2.prompt_builder import PromptBuilder

logger = get_logger()




class AnalysisCodeGeneratorAgent(BaseAgent):
    """
    Analysis Code Generator Agent for Phase 2.

    Generates the actual Python code for the analysis phase, including
    preprocessing pipelines, model training, and evaluation.
    Delegates complexity to helper classes:
    - TemplateGenerator: Deterministic code generation
    - PromptBuilder: LLM prompt construction
    - CodeInjector: Safety mechanisms
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="AnalysisCodeGenerator",
            phase=Phase.PHASE_2,
            system_prompt=ANALYSIS_CODEGEN_PROMPT,
            provider=provider,
            model=model,
        )
        self.template_generator = TemplateGenerator()

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Generate analysis notebook cells based on strategy.

        Args:
            state: Current analysis state.
            **kwargs: Must include 'strategy' (StrategyToCodeGenHandoff).

        Returns:
            Dictionary containing 'handoff' (AnalysisCodeToValidatorHandoff)
            with the generated cells.
        """
        strategy: StrategyToCodeGenHandoff | None = kwargs.get("strategy")

        if strategy is None:
            return {
                "handoff": None,
                "confidence": 0.0,
                "issues": [
                    self._create_issue(
                        "no_strategy", "missing_input", "error", "No strategy provided"
                    )
                ],
                "suggestions": ["Ensure Strategy Agent runs first"],
            }

        # CACHE CHECK
        # Only check check cache if this is the first iteration
        cache_manager = CacheManager()
        csv_hash = cache_manager.get_csv_hash(state.csv_path)

        cached_result = None
        if state.using_cached_profile:
            cached_result = cache_manager.load_artifact(
                csv_hash, "analysis_codegen_output"
            )

        if cached_result:
            try:
                cells = [
                    NotebookCell(**cell) for cell in cached_result.get("cells", [])
                ]
                result = cached_result.get("result", {})
                cell_manifest = [
                    CellManifest(**cm) for cm in cached_result.get("cell_manifest", [])
                ]

                handoff = AnalysisCodeToValidatorHandoff(
                    cells=cells,
                    total_cells=len(cells),
                    cell_manifest=cell_manifest,
                    required_imports=result.get("required_imports", []),
                    pip_dependencies=result.get("pip_dependencies", []),
                    expected_models=result.get("expected_models", []),
                    expected_metrics=result.get("expected_metrics", []),
                    expected_visualizations=result.get("expected_visualizations", 0),
                    source_strategy=strategy,
                )

                return {
                    "handoff": handoff,
                    "confidence": result.get("confidence", 0.8),
                    "issues": [],
                    "suggestions": [],
                }
            except Exception as e:
                logger.warning(f"Failed to use cached analysis codegen: {e}")

        # Try LLM generation, but fallback to template if we've failed validation multiple times
        try:
            # FORCE TEMPLATE if we've failed validation multiple times (recursion breaker)
            if len(state.analysis_validation_reports) >= 2:
                raise Exception(
                    "Forced template fallback due to repeated validation failures"
                )

            prompt = PromptBuilder.build_generation_prompt(strategy, state)
            response = self.llm_agent.invoke_with_json(prompt)
            result = json.loads(response)
            cells = [NotebookCell(**cell) for cell in result.get("cells", [])]
            cell_manifest = [
                CellManifest(**cm) for cm in result.get("cell_manifest", [])
            ]
        except json.JSONDecodeError as e:
            logger.warning(f"Analysis CodeGen JSON Decode Error: {e}")
            # Fall back to template generation
            cells, cell_manifest = self.template_generator.generate_template_cells(
                strategy, state
            )
            result = self.template_generator.build_template_result(cells, strategy)
        except Exception as e:
            logger.error(f"Analysis CodeGen Error: {e}")
            # Fall back to template generation
            cells, cell_manifest = self.template_generator.generate_template_cells(
                strategy, state
            )
            result = self.template_generator.build_template_result(cells, strategy)

        # Programmatic Injection of Safety Net (Fixes String Leakage)
        cells = CodeInjector.inject_safety_net(cells)

        # Save to cache
        cache_data = {
            "cells": [
                c.model_dump() for c in cells
            ],
            "cell_manifest": [
                cm.model_dump() for cm in cell_manifest
            ],
            "result": result,
        }
        cache_manager.save_artifact(csv_hash, "analysis_codegen_output", cache_data)

        # Build handoff
        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=len(cells),
            cell_manifest=cell_manifest if cell_manifest else [],
            required_imports=result.get("required_imports", []),
            pip_dependencies=result.get("pip_dependencies", []),
            expected_models=result.get("expected_models", []),
            expected_metrics=result.get("expected_metrics", []),
            expected_visualizations=result.get("expected_visualizations", 0),
            source_strategy=strategy,
        )

        return {
            "handoff": handoff,
            "confidence": result.get("confidence", 0.8),
            "issues": [],
            "suggestions": [],
        }
