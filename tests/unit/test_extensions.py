import pytest
from unittest.mock import MagicMock, patch
from src.agents.extensions import ForecastingExtensionAgent, ComparativeExtensionAgent, DiagnosticExtensionAgent
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import ProfileToStrategyHandoff

@pytest.fixture
def mock_state():
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.EXPLORATORY
    state.user_intent = None
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    
    # Mock handoff
    handoff = MagicMock(spec=ProfileToStrategyHandoff)
    handoff.column_profiles = []
    handoff.model_dump.return_value = {}
    state.profile_lock.get_locked_handoff.return_value = handoff
    
    # Mock csv_data
    state.csv_data = [
        {"date": "2023-01-01", "value": 100, "category": "A"}, 
        {"date": "2023-01-02", "value": 110, "category": "B"},
        {"date": "2023-01-03", "value": 120, "category": "A"}
    ]
    return state

@pytest.fixture
def mock_llm_agent():
    with patch('src.agents.base.LLMAgent') as MockLLM:
        mock_instance = MockLLM.return_value
        # Mock invoke_with_json to return a valid JSON string
        # We need to return different JSONs for different tests ideally, 
        # or a generic one. But agents parse specific models.
        # We'll set return_value in individual tests or use side_effect.
        mock_instance.invoke_with_json.return_value = "{}" 
        yield mock_instance

def test_forecasting_extension_process(mock_state, mock_llm_agent):
    agent = ForecastingExtensionAgent()
    # Mock LLM response
    # We need a minimal valid JSON for ForecastingExtension
    # Assuming it allows defaults or I construct it.
    # Actually, let's use a dummy object and dump it.
    
    # We can't import ForecastingExtension easily if fields are required.
    # Let's mock model_validate_json? NO, that's on the class.
    
    # Let's create a dummy JSON
    dummy_json = '{"datetime_column": "date", "datetime_format": "%Y-%m-%d", "frequency": "D", "date_range": ["2023-01-01", "2023-01-10"], "gap_analysis": {"has_gaps": false, "gap_count": 0, "largest_gap_periods": 0, "gap_locations": []}, "total_periods": 10, "is_stationary": true, "recommended_model": "ARIMA", "confidence": 1.0, "reasoning": "test", "missing_periods": [], "trend_detected": false, "seasonality_detected": false, "recommended_models": ["ARIMA"], "preprocessing_needed": [], "stationarity_hint": "unknown", "frequency_confidence": 1.0, "created_at": "2023-01-01T00:00:00", "csv_hash": "hash"}'
    mock_llm_agent.invoke_with_json.return_value = dummy_json
    
    result = agent.process(mock_state)
    
    assert "forecasting_extension" in result
    assert "confidence" in result
    assert result["confidence"] == 1.0
    mock_llm_agent.invoke_with_json.assert_called_once()

def test_comparative_extension_process(mock_state, mock_llm_agent):
    agent = ComparativeExtensionAgent()
    
    dummy_json = '{"group_column": "category", "group_values": ["A", "B"], "group_sizes": {"A": 10, "B": 10}, "balance_ratio": 1.0, "is_balanced": true, "recommended_primary_metric": "conversion", "confidence": 1.0, "reasoning": "test", "baseline_group": "A", "treatment_groups": ["B"], "numeric_metrics": ["spend"], "categorical_metrics": ["conversion"], "recommended_tests": [], "multiple_comparison_correction": "none", "created_at": "2023-01-01T00:00:00", "csv_hash": "hash"}'
    mock_llm_agent.invoke_with_json.return_value = dummy_json
    
    result = agent.process(mock_state)
    
    assert "comparative_extension" in result
    mock_llm_agent.invoke_with_json.assert_called_once()

def test_diagnostic_extension_process(mock_state, mock_llm_agent):
    agent = DiagnosticExtensionAgent()
    
    dummy_json = '{"profile_reference": "ref", "has_temporal_data": true, "temporal_column": "date", "metric_columns": ["value"], "primary_metric": "value", "metric_direction": "higher_is_better", "dimension_columns": [], "change_points_detected": [], "anomalies_detected": [], "recommended_analysis": ["decomposition"], "created_at": "2023-01-01T00:00:00", "csv_hash": "hash"}'
    mock_llm_agent.invoke_with_json.return_value = dummy_json
    
    result = agent.process(mock_state)
    
    assert "diagnostic_extension" in result
    mock_llm_agent.invoke_with_json.assert_called_once()

def test_extension_without_lock(mock_state):
    mock_state.profile_lock.is_locked.return_value = False
    agent = ForecastingExtensionAgent()
    
    result = agent.process(mock_state)
    assert "error" in result
    assert result["error"] == "Profile not locked, cannot run extension"
