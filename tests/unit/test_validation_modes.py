import pytest
from unittest.mock import MagicMock
from src.models.validation import (
    Phase2ValidationCriteria,
    calculate_phase2_quality, 
    AnalysisValidationResult
)
from src.agents.phase2.analysis_validator import AnalysisValidatorAgent
from src.models.handoffs import (
    AnalysisCodeToValidatorHandoff, 
    NotebookCell,
    StrategyToCodeGenHandoff,
    AnalysisType
)

class TestValidationModes:
    
    def test_get_criteria_for_mode(self):
        """Test retrieving criteria for different modes."""
        assert Phase2ValidationCriteria.get_criteria_for_mode("diagnostic") == Phase2ValidationCriteria.DIAGNOSTIC_CRITERIA
        assert Phase2ValidationCriteria.get_criteria_for_mode("comparative") == Phase2ValidationCriteria.COMPARATIVE_CRITERIA
        assert Phase2ValidationCriteria.get_criteria_for_mode("forecasting") == Phase2ValidationCriteria.FORECASTING_CRITERIA
        assert Phase2ValidationCriteria.get_criteria_for_mode("segmentation") == Phase2ValidationCriteria.SEGMENTATION_CRITERIA
        # Default fallback
        assert Phase2ValidationCriteria.get_criteria_for_mode("unknown") == Phase2ValidationCriteria.DEFAULT_CRITERIA
        assert Phase2ValidationCriteria.get_criteria_for_mode(None) == Phase2ValidationCriteria.DEFAULT_CRITERIA

    def test_calculate_quality_diagnostic(self):
        """Test quality calculation for diagnostic mode."""
        # Mock result with perfect scores
        result = MagicMock(spec=AnalysisValidationResult)
        result.cells_passed = 10
        result.total_cells = 10
        result.pep8_score = 1.0
        result.metric_values = {
            "root_cause_identified": 1.0,
            "factors_ranked": 1.0,
            "evidence_provided": 1.0
        }
        
        score, is_complete = calculate_phase2_quality(result, mode="diagnostic")
        
        # Expected: 
        # execution (0.25*1) + root_cause (0.25*1) + factors (0.20*1) + evidence (0.20*1) + style (0.10*1) = 1.0
        assert score == pytest.approx(1.0)
        assert is_complete is True

    def test_calculate_quality_forecasting_partial(self):
        """Test partial quality for forecasting mode."""
        result = MagicMock(spec=AnalysisValidationResult)
        result.cells_passed = 10
        result.total_cells = 10
        result.pep8_score = 1.0
        result.result_viz_count = 2
        
        # Partial metrics
        result.metric_values = {
            "forecast_generated": 1.0,
            "confidence_intervals": 0.0, # Missing
            "accuracy_metrics": 1.0
        }
        
        score, is_complete = calculate_phase2_quality(result, mode="forecasting")
        
        # Expected:
        # exec (0.25) + forecast (0.25) + conf (0.15*0) + acc (0.15) + viz (0.10) + style (0.10)
        # 0.25 + 0.25 + 0 + 0.15 + 0.10 + 0.10 = 0.85
        assert score == pytest.approx(0.85)
        assert is_complete is True # Threshold is 0.85

    def test_validator_extracts_metrics(self):
        """Test that validator agent extracts correct metrics from code."""
        agent = AnalysisValidatorAgent()
        
        # Diagnostic Code
        code = """
        # Decomposition analysis
        import pandas as pd
        correlation = df.corr()
        print("Ranking important factors")
        """
        
        dummy_strategy = StrategyToCodeGenHandoff(
            profile_reference="dummy",
            analysis_type=AnalysisType.EXPLORATORY,
            analysis_objective="dummy"
        )
        
        handoff = AnalysisCodeToValidatorHandoff(
            source_strategy=dummy_strategy,
            cells=[NotebookCell(cell_type="code", source=code)],
            total_cells=1,
            cell_manifest=[],
            required_imports=["pandas"],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0
        )
        
        metrics = agent._validate_mode_specific_metrics(handoff, "diagnostic")
        assert metrics["root_cause_identified"] == 1.0
        assert metrics["factors_ranked"] == 1.0 # "factors" triggers it
        
        # Forecasting Code
        code_forecast = """
        from prophet import Prophet
        m = Prophet()
        m.fit(df)
        future = m.make_future_dataframe()
        forecast = m.predict(future)
        m.plot(forecast)
        """
        handoff_forecast = AnalysisCodeToValidatorHandoff(
            source_strategy=dummy_strategy,
            cells=[NotebookCell(cell_type="code", source=code_forecast)],
            total_cells=1,
            cell_manifest=[],
            required_imports=["prophet"],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=1
        )
        
        metrics_f = agent._validate_mode_specific_metrics(handoff_forecast, "forecasting")
        assert metrics_f["forecast_generated"] == 1.0
        # confidence intervals not explicit in this snippet keywords (except maybe default prophet output)
        # but our keywords look for "confidence interval" etc.
        assert metrics_f["confidence_intervals"] == 0.0 
