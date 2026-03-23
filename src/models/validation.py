"""
Validation models for the Multi-Agent Data Analysis System.

Defines validation criteria, reports, and quality calculation functions.
"""

from typing import Dict, List, Optional, Tuple, Any

from pydantic import BaseModel

from src.models.common import Issue


# ============================================================================
# Validation Results
# ============================================================================


class ProfileValidationResult(BaseModel):
    """Result of Profile Validator execution."""

    # Execution results
    cells_passed: int
    total_cells: int

    # Type detection
    min_type_confidence: float
    columns_with_low_confidence: List[str] = []

    # Statistics coverage
    stats_coverage: float  # 0.0 - 1.0

    # Visualizations
    viz_count: int
    viz_failures: List[str] = []

    # Preprocessing
    preprocessing_recommendations_count: int = 0

    # Quality report
    report_sections_present: int
    report_sections_required: int

    # Code style
    pep8_score: float
    style_issues: List[str] = []

    # Issues found
    issues: List[Issue] = []


class AnalysisValidationResult(BaseModel):
    """Result of Analysis Validator execution."""

    # Execution results
    cells_passed: int
    total_cells: int

    # Model training
    models_trained: int
    model_failures: List[str] = []

    # Metrics
    metrics_computed: int
    metrics_required: int
    metric_values: Dict[str, float] = {}

    # Visualizations
    result_viz_count: int
    viz_failures: List[str] = []

    # Conclusions
    insights_count: int

    # Code style
    pep8_score: float
    style_issues: List[str] = []

    # Issues found
    issues: List[Issue] = []


# ============================================================================
# Validation Reports
# ============================================================================


class ValidationReport(BaseModel):
    """Complete validation report with routing decision."""

    phase: str  # "phase1" or "phase2"
    passed: bool
    quality_score: float

    # Detailed results
    execution_success: bool
    all_criteria_met: bool

    # For routing
    issues: List[Issue] = []
    route_to: Optional[str] = None  # Agent name or "GRANT_LOCK" / "COMPLETE"
    route_reason: str = ""

    # Suggestions for improvement
    suggestions: List[str] = []

    @property
    def formatted_feedback(self) -> str:
        """Pre-format issues and suggestions into a compact feedback string.

        Used by the retry prompt builder to avoid re-extracting and formatting
        on every retry iteration, saving token overhead.
        """
        parts: List[str] = []
        for issue in self.issues:
            parts.append(f"- Issue: {issue.message}")
        for s in self.suggestions:
            parts.append(f"- Suggestion: {s}")
        return "\n".join(parts)


# ============================================================================
# Phase 1 Validation Criteria
# ============================================================================


class Phase1ValidationCriteria:
    """
    Criteria for validating Phase 1 (Data Profiling) success.

    All criteria defined here must pass for the Profile Lock to be granted.
    The weights determine the contribution of each component to the
    final Quality Score.
    """

    CRITERIA = {
        "execution_success": {
            "description": "All cells execute without errors",
            "threshold": 1.0,  # 100% cells must succeed
            "weight": 0.30,
        },
        "type_detection_confidence": {
            "description": "Data type detection confidence >= 0.7 for all columns",
            "threshold": 0.7,
            "weight": 0.25,
        },
        "statistics_coverage": {
            "description": "Statistics generated for all applicable columns",
            "threshold": 1.0,  # 100% coverage
            "weight": 0.20,
        },
        "visualization_success": {
            "description": "At least 3 visualization types rendered",
            "threshold": 3,  # Minimum count
            "weight": 0.15,
        },
        "quality_report_completeness": {
            "description": "Data quality report contains all required sections",
            "threshold": 1.0,  # All sections present
            "weight": 0.05,
        },
        "code_style": {
            "description": "PEP8 compliance score",
            "threshold": 0.8,
            "weight": 0.05,
        },
    }

    LOCK_THRESHOLD = 0.80  # Overall score needed for lock


def calculate_phase1_quality(
    validation_result: ProfileValidationResult,
) -> Tuple[float, bool]:
    """
    Calculate Phase 1 quality score and lock recommendation.
    Returns (quality_score, should_grant_lock).
    """
    criteria = Phase1ValidationCriteria.CRITERIA

    scores = {
        "execution_success": validation_result.cells_passed
        / max(validation_result.total_cells, 1),
        "type_detection_confidence": min(validation_result.min_type_confidence, 1.0),
        "statistics_coverage": validation_result.stats_coverage,
        "visualization_success": min(validation_result.viz_count / 3, 1.0),
        "quality_report_completeness": validation_result.report_sections_present
        / max(validation_result.report_sections_required, 1),
        "code_style": validation_result.pep8_score,
    }

    # Check hard requirements
    hard_requirements_met = (
        scores["execution_success"] >= 1.0
        and scores["type_detection_confidence"] >= 0.7
        and scores["statistics_coverage"] >= 1.0
        and validation_result.viz_count >= 3
    )

    quality_score = 0.0
    for k in criteria:
        quality_score += float(criteria[k]["weight"]) * float(scores[k])  # type: ignore

    should_lock = (
        hard_requirements_met
        and quality_score >= Phase1ValidationCriteria.LOCK_THRESHOLD
    )

    return quality_score, should_lock


# ============================================================================
# Phase 2 Validation Criteria
# ============================================================================


class Phase2ValidationCriteria:
    """
    Criteria for validating Phase 2 (Analysis & Modeling) success.

    Ensures that the drafted analysis code is not just runnable, but
    meaningful (models trained, metrics computed, insights generated).
    """

    # Standard Predictive / Default Criteria
    DEFAULT_CRITERIA = {
        "execution_success": {
            "description": "All cells execute without errors",
            "threshold": 1.0,
            "weight": 0.25,
        },
        "model_training_success": {
            "description": "At least one model trained successfully",
            "threshold": 1,  # Minimum count
            "weight": 0.25,
        },
        "metrics_computed": {
            "description": "All specified evaluation metrics computed",
            "threshold": 1.0,
            "weight": 0.20,
        },
        "results_visualization": {
            "description": "At least 2 results visualizations rendered",
            "threshold": 2,
            "weight": 0.10,
        },
        "conclusions_quality": {
            "description": "Conclusions section with >= 3 insights",
            "threshold": 3,
            "weight": 0.10,
        },
        "code_style": {
            "description": "PEP8 compliance score",
            "threshold": 0.8,
            "weight": 0.10,
        },
    }

    DIAGNOSTIC_CRITERIA = {
        "execution_success": {"threshold": 1.0, "weight": 0.25},
        "root_cause_identified": {
            "threshold": 1.0,
            "weight": 0.25,
            "description": "Root causes identified via decomposition or correlation",
        },
        "factors_ranked": {
            "threshold": 1.0,
            "weight": 0.20,
            "description": "Contributing factors ranked by impact",
        },
        "evidence_provided": {
            "threshold": 1.0,
            "weight": 0.20,
            "description": "Statistical or visual evidence for root causes",
        },
        "code_style": {"threshold": 0.8, "weight": 0.10},
    }

    COMPARATIVE_CRITERIA = {
        "execution_success": {"threshold": 1.0, "weight": 0.25},
        "tests_completed": {
            "threshold": 1.0,
            "weight": 0.25,
            "description": "Statistical tests (t-test, ANOVA, etc.) completed",
        },
        "p_values_computed": {
            "threshold": 1.0,
            "weight": 0.20,
            "description": "P-values or confidence intervals computed",
        },
        "effect_sizes": {
            "threshold": 1.0,
            "weight": 0.20,
            "description": "Effect sizes reported",
        },
        "code_style": {"threshold": 0.8, "weight": 0.10},
    }

    FORECASTING_CRITERIA = {
        "execution_success": {"threshold": 1.0, "weight": 0.25},
        "forecast_generated": {
            "threshold": 1.0,
            "weight": 0.25,
            "description": "Future values forecast generated",
        },
        "confidence_intervals": {
            "threshold": 1.0,
            "weight": 0.15,
            "description": "Confidence intervals for forecast",
        },
        "accuracy_metrics": {
            "threshold": 1.0,
            "weight": 0.15,
            "description": "Backtesting metrics (MAE, RMSE, MAPE)",
        },
        "visualizations": {
            "threshold": 2,
            "weight": 0.10,
            "description": "Forecast plots with history",
        },
        "code_style": {"threshold": 0.8, "weight": 0.10},
    }

    SEGMENTATION_CRITERIA = {
        "execution_success": {"threshold": 1.0, "weight": 0.25},
        "clusters_generated": {
            "threshold": 1.0,
            "weight": 0.25,
            "description": "Clusters/Segments created",
        },
        "optimal_k_justified": {
            "threshold": 1.0,
            "weight": 0.15,
            "description": "Method for optimal clusters (Elbow, Silhouette) used",
        },
        "segment_profiles": {
            "threshold": 1.0,
            "weight": 0.25,
            "description": "Segments profiled and described",
        },
        "code_style": {"threshold": 0.8, "weight": 0.10},
    }

    COMPLETION_THRESHOLD = 0.75

    @classmethod
    def get_criteria_for_mode(cls, mode: str) -> Dict[str, Any]:
        """Retrieve validation criteria based on pipeline mode."""
        mode = mode.lower() if mode else "predictive"
        if mode == "diagnostic":
            return cls.DIAGNOSTIC_CRITERIA
        elif mode == "comparative":
            return cls.COMPARATIVE_CRITERIA
        elif mode == "forecasting":
            return cls.FORECASTING_CRITERIA
        elif mode == "segmentation":
            return cls.SEGMENTATION_CRITERIA
        else:
            return cls.DEFAULT_CRITERIA


def calculate_phase2_quality(
    validation_result: AnalysisValidationResult, mode: str = "predictive"
) -> Tuple[float, bool]:
    """
    Calculate Phase 2 quality score and completion status.
    Returns (quality_score, is_complete).
    """
    criteria = Phase2ValidationCriteria.get_criteria_for_mode(mode)

    # Base scores available in all modes
    scores = {
        "execution_success": validation_result.cells_passed
        / max(validation_result.total_cells, 1),
        "code_style": validation_result.pep8_score,
    }

    # Map validation result fields to criteria specific fields
    # This requires AnalysisValidationResult to hold these values OR we repurpose existing fields
    # properly.
    # For now, we will map "generic" result fields to mode-specific criteria where possible,
    # or assume 0 if not yet populated (AnalysisValidatorAgent needs to populate them).

    # We need to enhance AnalysisValidationResult or use a dictionary for flexible metrics.
    # Currently AnalysisValidationResult has specific fields.
    # Let's use the 'metric_values' dict in AnalysisValidationResult to store mode-specific flags/scores.

    mv = validation_result.metric_values or {}

    if mode == "diagnostic":
        scores["root_cause_identified"] = mv.get("root_cause_identified", 0.0)
        scores["factors_ranked"] = mv.get("factors_ranked", 0.0)
        scores["evidence_provided"] = mv.get("evidence_provided", 0.0)

    elif mode == "comparative":
        scores["tests_completed"] = mv.get("tests_completed", 0.0)
        scores["p_values_computed"] = mv.get("p_values_computed", 0.0)
        scores["effect_sizes"] = mv.get("effect_sizes", 0.0)

    elif mode == "forecasting":
        scores["forecast_generated"] = mv.get("forecast_generated", 0.0)
        scores["confidence_intervals"] = mv.get("confidence_intervals", 0.0)
        scores["accuracy_metrics"] = mv.get("accuracy_metrics", 0.0)
        scores["visualizations"] = min(
            validation_result.result_viz_count
            / criteria["visualizations"]["threshold"],
            1.0,
        )

    elif mode == "segmentation":
        scores["clusters_generated"] = mv.get("clusters_generated", 0.0)
        scores["optimal_k_justified"] = mv.get("optimal_k_justified", 0.0)
        scores["segment_profiles"] = mv.get("segment_profiles", 0.0)

    else:  # Predictive / Default
        scores["model_training_success"] = min(
            validation_result.models_trained / 1, 1.0
        )
        scores["metrics_computed"] = validation_result.metrics_computed / max(
            validation_result.metrics_required, 1
        )
        scores["results_visualization"] = min(
            validation_result.result_viz_count / 2, 1.0
        )
        scores["conclusions_quality"] = min(validation_result.insights_count / 3, 1.0)

    # Calculate weighted score
    quality_score = 0.0
    for k, criterion in criteria.items():
        weight = criterion["weight"]
        score = scores.get(k, 0.0)
        quality_score += weight * score

    # Check threshold
    is_complete = (
        scores["execution_success"] >= 1.0
        and quality_score >= Phase2ValidationCriteria.COMPLETION_THRESHOLD
    )

    return quality_score, is_complete


# ============================================================================
# Issue Classification
# ============================================================================


def has_data_understanding_issues(issues: List[Issue]) -> bool:
    """Determine if issues are data understanding related (route to Profiler)."""
    data_issue_types = {
        "type_detection_error",
        "pattern_detection_failure",
        "column_analysis_incomplete",
        "data_quality_assessment_error",
    }
    return any(issue.type in data_issue_types for issue in issues)


def has_code_generation_issues(issues: List[Issue]) -> bool:
    """Determine if issues are code generation related (route to CodeGen)."""
    code_issue_types = {
        "syntax_error",
        "runtime_error",
        "import_error",
        "visualization_error",
        "coverage_incomplete",
    }
    return any(issue.type in code_issue_types for issue in issues)


def has_strategy_issues(issues: List[Issue]) -> bool:
    """Determine if issues are strategy related (route to Strategy Agent)."""
    strategy_issue_types = {
        "algorithm_mismatch",
        "missing_preprocessing",
        "wrong_evaluation_metric",
        "feature_engineering_gap",
        "model_selection_error",
    }
    return any(issue.type in strategy_issue_types for issue in issues)


def has_systemic_issues(issues: List[Issue], issue_frequency: Dict[str, int]) -> bool:
    """Determine if issues are systemic (escalate to Orchestrator)."""
    # Check for repeated issues
    for issue in issues:
        if issue_frequency.get(issue.type, 0) >= 3:
            return True
    return False
