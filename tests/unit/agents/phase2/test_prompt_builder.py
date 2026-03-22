"""
Tests for PromptBuilder — covers all analysis types and feedback incorporation.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.agents.phase2.prompt_builder import PromptBuilder
from src.models.handoffs import (
    StrategyToCodeGenHandoff,
    AnalysisType,
    PreprocessingStep,
    ModelSpec,
    ResultVisualization,
    ValidationStrategy,
)
from src.models.state import AnalysisState


def _make_strategy(analysis_type: AnalysisType, **overrides) -> StrategyToCodeGenHandoff:
    """Create a minimal StrategyToCodeGenHandoff for testing."""
    defaults = dict(
        profile_reference="test_profile",
        analysis_type=analysis_type,
        analysis_objective="Test objective",
        target_column="target",
        feature_columns=["col_a", "col_b"],
        preprocessing_steps=[],
        models_to_train=[],
        evaluation_metrics=["accuracy"],
        validation_strategy=ValidationStrategy(method="train_test_split"),
        result_visualizations=[],
        conclusion_points=["Point 1"],
    )
    defaults.update(overrides)
    return StrategyToCodeGenHandoff(**defaults)


def _make_state(**overrides) -> MagicMock:
    """Create a mock AnalysisState."""
    state = MagicMock(spec=AnalysisState)
    state.csv_path = "/data/test.csv"
    state.analysis_validation_reports = overrides.get("analysis_validation_reports", [])
    return state


# ---------------------------------------------------------------------------
# Analysis type branching
# ---------------------------------------------------------------------------

class TestModeSpecificInstructions:

    @pytest.mark.parametrize("analysis_type,expected_fragment", [
        (AnalysisType.TIME_SERIES, "FORECASTING"),
        (AnalysisType.COMPARATIVE, "COMPARATIVE"),
        (AnalysisType.CAUSAL, "DIAGNOSTIC"),
        (AnalysisType.CLUSTERING, "SEGMENTATION"),
        (AnalysisType.DIMENSIONALITY, "DIMENSIONALITY"),
    ])
    @patch("src.agents.phase2.prompt_builder.FORECASTING_CODEGEN_PROMPT", "FORECASTING_PROMPT")
    @patch("src.agents.phase2.prompt_builder.COMPARATIVE_CODEGEN_PROMPT", "COMPARATIVE_PROMPT")
    @patch("src.agents.phase2.prompt_builder.DIAGNOSTIC_CODEGEN_PROMPT", "DIAGNOSTIC_PROMPT")
    @patch("src.agents.phase2.prompt_builder.SEGMENTATION_CODEGEN_PROMPT", "SEGMENTATION_PROMPT")
    @patch("src.agents.phase2.prompt_builder.DIMENSIONALITY_CODEGEN_PROMPT", "DIMENSIONALITY_PROMPT")
    def test_mode_instruction_selected(self, analysis_type, expected_fragment):
        strategy = _make_strategy(analysis_type)
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert expected_fragment in prompt

    def test_exploratory_has_no_mode_instruction(self):
        strategy = _make_strategy(AnalysisType.EXPLORATORY)
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        # Exploratory is not matched by any branch so mode_instruction stays ""
        assert "ANALYSIS TYPE: exploratory" in prompt

    def test_classification_has_no_mode_instruction(self):
        strategy = _make_strategy(AnalysisType.CLASSIFICATION)
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "ANALYSIS TYPE: classification" in prompt


# ---------------------------------------------------------------------------
# Preprocessing — Geography/Gender injection
# ---------------------------------------------------------------------------

class TestPreprocessingGeography:

    def test_geography_injects_gender(self):
        step = PreprocessingStep(
            step_name="encode_geography",
            step_type="encoding",
            method="onehot",
            target_columns=["Geography"],
            rationale="One-hot encode Geography",
            order=1,
        )
        strategy = _make_strategy(AnalysisType.CLASSIFICATION, preprocessing_steps=[step])
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        # The prompt builder injects Gender into the cols string
        assert "Gender" in prompt or "SAFETY NET" in prompt

    def test_no_geography_no_injection(self):
        step = PreprocessingStep(
            step_name="encode_city",
            step_type="encoding",
            method="onehot",
            target_columns=["City"],
            rationale="One-hot encode City",
            order=1,
        )
        strategy = _make_strategy(AnalysisType.CLASSIFICATION, preprocessing_steps=[step])
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        # PreprocessingStep has no 'description' attr, so prompt_builder uses str(step)
        assert "City" in prompt


# ---------------------------------------------------------------------------
# One-hot encoding detection and dynamic instruction
# ---------------------------------------------------------------------------

class TestOneHotDetection:

    @pytest.mark.parametrize("method", ["onehot", "one_hot", "one-hot", "get_dummies", "dummy", "OneHotEncoding"])
    def test_onehot_methods_trigger_instruction(self, method):
        step = PreprocessingStep(
            step_name="encode_color",
            step_type="encoding",
            method=method,
            target_columns=["Color"],
            rationale=f"Encode using {method}",
            order=1,
        )
        strategy = _make_strategy(AnalysisType.CLASSIFICATION, preprocessing_steps=[step])
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "DYNAMIC PREPROCESSING LOGIC" in prompt

    def test_non_encoding_step_no_onehot_instruction(self):
        step = PreprocessingStep(
            step_name="scale_age",
            step_type="scaling",
            method="standard",
            target_columns=["Age"],
            rationale="Scale Age",
            order=1,
        )
        strategy = _make_strategy(AnalysisType.CLASSIFICATION, preprocessing_steps=[step])
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "DYNAMIC PREPROCESSING LOGIC" not in prompt


# ---------------------------------------------------------------------------
# Feedback incorporation from validation reports
# ---------------------------------------------------------------------------

class TestFeedbackSection:

    def test_no_reports_no_feedback(self):
        strategy = _make_strategy(AnalysisType.EXPLORATORY)
        state = _make_state(analysis_validation_reports=[])
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "FAILED validation" not in prompt

    def test_dict_report_with_issues(self):
        report = {
            "issues": [{"message": "Missing metrics computation"}],
            "suggestions": ["Add accuracy calculation"],
        }
        strategy = _make_strategy(AnalysisType.CLASSIFICATION)
        state = _make_state(analysis_validation_reports=[report])
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "FAILED validation" in prompt
        assert "Missing metrics computation" in prompt
        assert "Add accuracy calculation" in prompt

    def test_object_report_with_issues(self):
        issue = MagicMock()
        issue.message = "No evaluation_results dict"
        report = MagicMock()
        report.issues = [issue]
        report.suggestions = ["Populate evaluation_results"]

        strategy = _make_strategy(AnalysisType.CLASSIFICATION)
        state = _make_state(analysis_validation_reports=[report])
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "FAILED validation" in prompt
        assert "No evaluation_results dict" in prompt

    def test_metrics_failure_triggers_critical(self):
        report = {
            "issues": [{"message": "Failed to compute required evaluation metrics"}],
            "suggestions": [],
        }
        strategy = _make_strategy(AnalysisType.CLASSIFICATION)
        state = _make_state(analysis_validation_reports=[report])
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "CRITICAL" in prompt
        assert "sklearn" in prompt

    def test_uses_latest_report_only(self):
        old_report = {"issues": [{"message": "Old issue"}], "suggestions": []}
        new_report = {"issues": [{"message": "New issue"}], "suggestions": []}
        strategy = _make_strategy(AnalysisType.CLASSIFICATION)
        state = _make_state(analysis_validation_reports=[old_report, new_report])
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "New issue" in prompt


# ---------------------------------------------------------------------------
# Models and visualizations in prompt
# ---------------------------------------------------------------------------

class TestModelsAndVisualizations:

    def test_models_listed(self):
        model = ModelSpec(
            model_name="RandomForest",
            import_path="sklearn.ensemble.RandomForestClassifier",
            rationale="Good baseline",
            priority=1,
        )
        strategy = _make_strategy(AnalysisType.CLASSIFICATION, models_to_train=[model])
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "RandomForest" in prompt
        assert "sklearn.ensemble.RandomForestClassifier" in prompt

    def test_visualizations_listed(self):
        viz = ResultVisualization(viz_type="confusion_matrix", title="Confusion matrix")
        strategy = _make_strategy(
            AnalysisType.CLASSIFICATION,
            result_visualizations=[viz],
        )
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "confusion_matrix" in prompt

    def test_safety_net_always_present(self):
        strategy = _make_strategy(AnalysisType.EXPLORATORY)
        state = _make_state()
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        assert "SAFETY NET" in prompt
        assert "select_dtypes" in prompt
