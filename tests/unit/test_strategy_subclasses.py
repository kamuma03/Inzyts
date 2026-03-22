import pytest
from unittest.mock import MagicMock, patch
import json

from src.models.state import AnalysisState
from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType, ProfilerToCodeGenHandoff
from src.agents.phase2.comparative_strategy import ComparativeStrategyAgent
from src.agents.phase2.diagnostic_strategy import DiagnosticStrategyAgent
from src.agents.phase2.forecasting_strategy import ForecastingStrategyAgent
from src.agents.phase2.segmentation_strategy import SegmentationStrategyAgent

@pytest.fixture
def mock_state():
    state = AnalysisState(csv_path="test.csv")
    state.profile_lock = MagicMock()
    # Mock unlocked profile
    state.profile_lock.is_locked.return_value = False
    return state

@pytest.fixture
def locked_state():
    state = AnalysisState(csv_path="test.csv")
    state.profile_lock = MagicMock()
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.lock_hash = "fake_hash"
    
    handoff_mock = MagicMock(spec=ProfilerToCodeGenHandoff)
    handoff_mock.model_dump.return_value = {"fake": "dump"}
    state.profile_lock.get_locked_handoff.return_value = handoff_mock
    
    state.user_intent = MagicMock()
    state.user_intent.model_dump.return_value = {"intent": "test"}
    state.forecasting_extension = MagicMock()
    state.forecasting_extension.model_dump.return_value = {"ext": "val"}
    return state

@pytest.fixture
def valid_llm_response():
    return json.dumps({
        "analysis_objective": "Test objective",
        "target_column": "target",
        "feature_columns": ["f1"],
        "dropped_columns": [],
        "models_to_train": [],
        "preprocessing_steps": [],
        "validation_strategy": {"method": "train_test_split", "parameters": {}},
        "evaluation_metrics": [],
        "result_visualizations": []
    })

def test_comparative_strategy(mock_state, locked_state, valid_llm_response):
    agent = ComparativeStrategyAgent()
    agent.llm_agent = MagicMock()
    
    # Unlocked
    res = agent.process(mock_state)
    assert res == {"error": "Profile not locked"}
    
    # Locked
    agent.llm_agent.invoke_with_json.return_value = valid_llm_response
    res = agent.process(locked_state)
    assert "handoff" in res
    assert res["handoff"].analysis_type == AnalysisType.COMPARATIVE
    assert res["handoff"].profile_reference == "fake_hash"

def test_diagnostic_strategy(mock_state, locked_state, valid_llm_response):
    agent = DiagnosticStrategyAgent()
    agent.llm_agent = MagicMock()
    
    res = agent.process(mock_state)
    assert res == {"error": "Profile not locked"}
    
    agent.llm_agent.invoke_with_json.return_value = valid_llm_response
    res = agent.process(locked_state)
    assert "handoff" in res
    assert res["handoff"].analysis_type == AnalysisType.CAUSAL

    # Invalid JSON
    agent.llm_agent.invoke_with_json.return_value = "invalid json"
    with pytest.raises(Exception):
        agent.process(locked_state)

def test_forecasting_strategy(mock_state, locked_state, valid_llm_response):
    agent = ForecastingStrategyAgent()
    agent.llm_agent = MagicMock()
    
    res = agent.process(mock_state)
    assert res == {"error": "Profile not locked"}
    
    agent.llm_agent.invoke_with_json.return_value = valid_llm_response
    res = agent.process(locked_state)
    assert "handoff" in res
    assert res["handoff"].analysis_type == AnalysisType.TIME_SERIES

def test_segmentation_strategy(mock_state, locked_state, valid_llm_response):
    agent = SegmentationStrategyAgent()
    agent.llm_agent = MagicMock()
    
    res = agent.process(mock_state)
    assert res == {"error": "Profile not locked"}
    
    agent.llm_agent.invoke_with_json.return_value = valid_llm_response
    res = agent.process(locked_state)
    assert "handoff" in res
    assert res["handoff"].analysis_type == AnalysisType.CLUSTERING
