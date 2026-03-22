"""
Analysis Validator Agent - QA specialist for Phase 2.

Ensures the generated analysis code actually works and produces meaningful results.
1. Checks that models trained successfully (didn't crash).
2. Verifies that evaluation metrics were computed.
3. Checks for insights and conclusions.
4. Key Decision: Is the analysis "Complete" or do we need to refine the Strategy?
"""

import ast
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import BaseAgent
from src.agents.validation_utils import (
    validate_syntax,
    count_visualizations,
    calculate_pep8_score,
)
from src.models.state import AnalysisState, Phase
from src.models.common import Issue
from src.models.cells import NotebookCell
from src.models.handoffs import AnalysisCodeToValidatorHandoff
from src.models.validation import (
    AnalysisValidationResult,
    ValidationReport,
    calculate_phase2_quality,
)
from src.services.sandbox_executor import SandboxExecutor
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger()


class AnalysisValidatorAgent(BaseAgent):
    """
    Analysis Validator Agent for Phase 2.

    Validates analysis code execution and determines if Phase 2
    can be marked as complete.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="AnalysisValidator",
            phase=Phase.PHASE_2,
            system_prompt="You are an Analysis Validator Agent.",
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Validate analysis code and determine completion.

        Args:
            state: Current analysis state.
            **kwargs: Must include 'code_handoff' (AnalysisCodeToValidatorHandoff).

        Returns:
            Dictionary with validation results, quality scores, and the
            final 'is_complete' boolean.
        """
        # Log agent invocation
        logger.agent_execution("AnalysisValidator", "invoked")

        code_handoff: AnalysisCodeToValidatorHandoff | None = kwargs.get("code_handoff")

        if code_handoff is None:
            logger.agent_execution(
                "AnalysisValidator", "failed", reason="no_code_handoff"
            )
            return {
                "validation_result": None,
                "report": None,
                "confidence": 0.0,
                "issues": [
                    self._create_issue(
                        "no_code",
                        "missing_input",
                        "error",
                        "No analysis code handoff provided",
                    )
                ],
                "suggestions": ["Ensure Analysis Code Generator runs first"],
            }

        # Validate cells
        validation_result = self._validate_cells(code_handoff, state)

        # Get pipeline mode
        mode = state.pipeline_mode or "predictive"
        if hasattr(mode, "value"):  # Handle enum
            mode = mode.value

        # Calculate quality score with mode
        quality_score, is_complete = calculate_phase2_quality(
            validation_result, mode=mode
        )

        # Build validation report
        report = self._build_report(
            validation_result, quality_score, is_complete, state
        )

        # Log validation result
        logger.validation(
            "phase2",
            passed=is_complete,
            quality_score=quality_score,
            issues_count=len(validation_result.issues),
        )

        # Log Phase 2 completion if successful
        if is_complete:
            logger.phase_transition("phase2", "complete")
        else:
            logger.debug(f"Validation Failed. Quality: {quality_score}")
            logger.debug(f"Issues: {validation_result.issues}")
            logger.debug(
                f"Metrics Computed: {validation_result.metrics_computed} / {validation_result.metrics_required}"
            )
            logger.debug(f"Metric Values: {validation_result.metric_values}")

        # Log completion
        logger.agent_execution(
            "AnalysisValidator",
            "completed",
            is_complete=is_complete,
            quality_score=quality_score,
            models_trained=validation_result.models_trained,
        )

        return {
            "validation_result": validation_result,
            "report": report,
            "quality_score": quality_score,
            "is_complete": is_complete,
            "confidence": 0.9 if is_complete else 0.6,
            "issues": validation_result.issues,
            "suggestions": report.suggestions,
        }

    def _validate_cells(
        self, code_handoff: AnalysisCodeToValidatorHandoff, state: AnalysisState
    ) -> AnalysisValidationResult:
        """Validate all cells in the code handoff."""
        cells = code_handoff.cells
        issues: List[Issue] = []

        cells_passed = 0
        models_trained = 0
        metrics_computed = 0
        viz_count = 0
        insights_count = 0

        with SandboxExecutor(execution_timeout=120) as executor:
            for idx, cell in enumerate(cells):
                try:
                    if cell.cell_type == "code":
                        # Validate Python syntax
                        is_valid, error = self._validate_syntax(cell.source)
                        if is_valid:
                            # Execute the code
                            exec_result = executor.execute_cell(cell.source)
                            if exec_result.success:
                                cells_passed += 1
                                # Count model training
                                models_trained += self._count_model_training(
                                    cell.source
                                )
                                # Count metrics
                                metrics_computed += self._count_metrics(
                                    cell.source, code_handoff.source_strategy
                                )
                                # Count visualizations
                                viz_count += self._count_visualizations(cell.source)
                                # Count insights
                                insights_count += self._count_insights(cell.source)
                            else:
                                issues.append(
                                    self._create_issue(
                                        f"runtime_error_{idx}",
                                        "runtime_error",
                                        "error",
                                        f"Cell {idx} failed to execute: {exec_result.error_name}: {exec_result.error_value}",
                                        f"cell_{idx}",
                                    )
                                )
                        else:
                            issues.append(
                                self._create_issue(
                                    f"syntax_error_{idx}",
                                    "syntax_error",
                                    "error",
                                    f"Cell {idx} syntax error: {error}",
                                    f"cell_{idx}",
                                )
                            )
                    else:
                        cells_passed += 1
                        # Count insights in markdown
                        insights_count += self._count_markdown_insights(cell.source)

                except Exception as e:
                    issues.append(
                        self._create_issue(
                            f"validation_error_{idx}",
                            "system_error",
                            "error",
                            f"Cell {idx} validation system failed: {str(e)}",
                            f"cell_{idx}",
                        )
                    )

        # Calculate metrics requirements
        strategy = code_handoff.source_strategy
        metrics_required = (
            len(strategy.evaluation_metrics) if strategy.evaluation_metrics else 1
        )

        # Simplified PEP8 score
        pep8_score = self._calculate_pep8_score(cells)

        # Validate mode specific metrics
        # We use the state passed in to determine mode
        mode = state.pipeline_mode or "predictive"
        if hasattr(mode, "value"):
            mode = mode.value

        metric_values = self._validate_mode_specific_metrics(code_handoff, mode)

        metric_values = self._validate_mode_specific_metrics(code_handoff, mode)

        return AnalysisValidationResult(
            cells_passed=cells_passed,
            total_cells=len(cells),
            models_trained=min(
                models_trained,
                len(strategy.models_to_train) if strategy.models_to_train else 1,
            ),
            model_failures=[],
            metrics_computed=min(metrics_computed, metrics_required),
            metrics_required=metrics_required,
            metric_values=metric_values,
            result_viz_count=viz_count,
            viz_failures=[],
            insights_count=insights_count,
            pep8_score=pep8_score,
            style_issues=[],
            issues=issues,
        )

    def _validate_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax."""
        return validate_syntax(code)

    def _count_model_training(self, code: str) -> int:
        """Count model training operations."""
        count = 0
        training_patterns = [
            ".fit(",
            "model.train(",
            "classifier.fit(",
            "regressor.fit(",
        ]
        for pattern in training_patterns:
            count += code.count(pattern)
        return min(count, 3)  # Cap at 3 per cell

    def _count_metrics(self, code: str, strategy) -> int:
        """Count metric computations."""
        count = 0
        code_lower = code.lower()
        debug_metrics_looked_for = []

        has_class_report = "classification_report" in code_lower

        if strategy and strategy.evaluation_metrics:
            for metric in strategy.evaluation_metrics:
                debug_metrics_looked_for.append(metric)

                # Direct match (e.g. "accuracy_score" contains "accuracy")
                if metric in code_lower or f"_{metric}" in code_lower:
                    count += max(
                        code_lower.count(metric), code_lower.count(f"_{metric}")
                    )
                    continue

                # Classification report covers standard metrics
                if has_class_report and metric in [
                    "accuracy",
                    "precision",
                    "recall",
                    "f1_score",
                    "f1",
                ]:
                    count += 1
                    continue

                # Flexible matching
                if metric == "f1_score" and "f1" in code_lower:
                    count += code_lower.count("f1")
                    continue
                if metric == "roc_auc" and (
                    "roc_curve" in code_lower or "auc" in code_lower
                ):
                    count += 1  # Logic is fuzzy here, keeping simple
                    continue

        else:
            # Generic metric patterns
            metric_patterns = [
                "accuracy",
                "precision",
                "recall",
                "f1",
                "mse",
                "rmse",
                "mae",
                "r2",
            ]

            debug_metrics_looked_for = metric_patterns
            for pattern in metric_patterns:
                count += code_lower.count(pattern)
                if has_class_report and pattern in [
                    "accuracy",
                    "precision",
                    "recall",
                    "f1",
                ]:
                    # Avoid double counting if already counted via pattern?
                    # Actually simpler: just rely on regex counts or keep simple.
                    # If generic pattern counting is used, simpler is better.
                    pass

        if count == 0 and not has_class_report:
            pass

        return count

    _ANALYSIS_VIZ_PATTERNS = [
        "plt.show()",
        ".plot(",
        "sns.",
        "heatmap(",
        "confusion_matrix",
        "barh(",
        "scatter(",
    ]

    def _count_visualizations(self, code: str) -> int:
        """Count visualization calls."""
        return count_visualizations(code, self._ANALYSIS_VIZ_PATTERNS, cap=4)

    def _count_insights(self, code: str) -> int:
        """Count insight-generating code."""
        count = 0
        insight_patterns = [
            "print(",
            "Best Model",
            "Conclusions",
            "Key Insights",
            "Performance Summary",
        ]
        for pattern in insight_patterns:
            if pattern in code:
                count += 1
        return min(count, 5)

    def _count_markdown_insights(self, source: str) -> int:
        """Count insights in markdown cells."""
        count = 0
        lines = source.split("\n")
        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("*"):
                count += 1
            if "##" in line:
                count += 1
        return min(count, 3)

    def _calculate_pep8_score(self, cells: List[NotebookCell]) -> float:
        """Calculate PEP8 score using comprehensive shared linter."""
        return calculate_pep8_score(cells)

    def _build_report(
        self,
        result: AnalysisValidationResult,
        quality_score: float,
        is_complete: bool,
        state: AnalysisState,
    ) -> ValidationReport:
        """Build validation report with routing decision."""
        issues = result.issues
        suggestions: List[str] = []

        # Use centralized routing logic
        from src.workflow.routing import route_phase2_recursion

        next_agent, reason = route_phase2_recursion(result, state)

        if next_agent is None:
            # Phase complete
            route_to = "PHASE_2_COMPLETE"
            route_reason = "Phase 2 quality threshold met"
        else:
            route_to = next_agent
            route_reason = reason

            if next_agent == "StrategyAgent":
                suggestions.append(
                    "Review algorithm selection and preprocessing pipeline"
                )
            elif next_agent == "AnalysisCodeGenerator":
                suggestions.append("Fix syntax errors and improve code structure")
            elif reason == "ROLLBACK_TRIGGERED":
                suggestions.append(
                    "Rolling back to previous best state due to quality degradation"
                )

        # Specific suggestions
        if result.models_trained < 1:
            suggestions.append("Ensure at least one model is trained successfully")
        if result.metrics_computed < result.metrics_required:
            suggestions.append(
                f"Compute required evaluation metrics (found: {result.metrics_computed}/{result.metrics_required}). Check strategy for specific metrics."
            )
        if result.result_viz_count < 2:
            suggestions.append(
                f"Add more visualizations (current: {result.result_viz_count}, required: 2)"
            )
        if result.insights_count < 3:
            suggestions.append(
                f"Add more insights to conclusions (current: {result.insights_count}, required: 3)"
            )

        return ValidationReport(
            phase="phase2",
            passed=is_complete,
            quality_score=quality_score,
            execution_success=result.cells_passed == result.total_cells,
            all_criteria_met=is_complete,
            issues=issues,
            route_to=route_to,
            route_reason=route_reason,
            suggestions=suggestions,
        )

    def _validate_mode_specific_metrics(
        self, handoff: AnalysisCodeToValidatorHandoff, mode: str
    ) -> Dict[str, float]:
        """Validate metrics specific to the active pipeline mode."""
        code_content = "\n".join([cell.source for cell in handoff.cells])
        code_lower = code_content.lower()
        metrics = {}

        if mode == "diagnostic":
            # root_cause_identified: look for correlation, decomposition, causal keywords
            metrics["root_cause_identified"] = (
                1.0
                if any(
                    x in code_lower
                    for x in [
                        "correlation",
                        "causality",
                        "root cause",
                        "driver",
                        "factor",
                    ]
                )
                else 0.0
            )
            # factors_ranked: look for feature importance, coefficients, ranking
            metrics["factors_ranked"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["importance", "coefficient", "rank", "contribut"]
                )
                else 0.0
            )
            # evidence_provided: look for p-values, r-squared, confidence
            metrics["evidence_provided"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["p-value", "r-squared", "r2", "confidence", "significant"]
                )
                else 0.0
            )

        elif mode == "comparative":
            # tests_completed: t-test, anova, chi-square, mann-whitney
            metrics["tests_completed"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["ttest", "anova", "chisquare", "mannwhitney", "kruskal"]
                )
                else 0.0
            )
            # p_values_computed
            metrics["p_values_computed"] = (
                1.0 if "pvalue" in code_lower or "p-value" in code_lower else 0.0
            )
            # effect_sizes: cohen's d, eta squared, odds ratio
            metrics["effect_sizes"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["cohen", "effect size", "eta", "odds ratio"]
                )
                else 0.0
            )

        elif mode == "forecasting":
            # forecast_generated: predict, forecast, future
            metrics["forecast_generated"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["forecast", "future", "predict", "prophet", "arima"]
                )
                else 0.0
            )
            # confidence_intervals
            metrics["confidence_intervals"] = (
                1.0
                if any(
                    x in code_lower
                    for x in [
                        "confidence interval",
                        "interval",
                        "lower",
                        "upper",
                        "yhat_lower",
                    ]
                )
                else 0.0
            )
            # accuracy_metrics: mae, rmse, mape
            metrics["accuracy_metrics"] = (
                1.0
                if any(x in code_lower for x in ["mae", "rmse", "mape", "error"])
                else 0.0
            )

        elif mode == "segmentation":
            # clusters_generated: kmeans, dbscan, cluster labels
            metrics["clusters_generated"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["kmeans", "dbscan", "cluster", "hierarchy"]
                )
                else 0.0
            )
            # optimal_k_justified: elbow, silhouette, inertia
            metrics["optimal_k_justified"] = (
                1.0
                if any(
                    x in code_lower for x in ["elbow", "silhouette", "inertia", "score"]
                )
                else 0.0
            )
            # segment_profiles: groupby cluster, mean features
            metrics["segment_profiles"] = (
                1.0
                if any(
                    x in code_lower
                    for x in ["groupby", "mean", "profile", "characteristic"]
                )
                else 0.0
            )

        return metrics
