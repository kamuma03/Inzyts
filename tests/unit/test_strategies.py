import pytest
from unittest.mock import MagicMock, patch
from src.agents.phase2 import (
    ForecastingStrategyAgent,
    ComparativeStrategyAgent,
    DiagnosticStrategyAgent,
    SegmentationStrategyAgent
)
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType

@pytest.fixture
def mock_state():
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.FORECASTING
    state.user_intent = None
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.get_locked_handoff.return_value = MagicMock()
    state.profile_lock.lock_hash = "fake_hash"
    return state

@pytest.fixture
def mock_llm_agent():
    with patch('src.agents.base.LLMAgent') as MockLLM:
        mock_instance = MockLLM.return_value
        # Return a StrategyToCodeGenHandoff JSON string
        mock_handoff = StrategyToCodeGenHandoff(
            profile_reference="profile_x",
            analysis_type=AnalysisType.TIME_SERIES,
            analysis_objective="Forecast",
            feature_columns=[],
            models_to_train=[]
        )
        mock_instance.invoke_with_json.return_value = mock_handoff.model_dump_json()
        yield mock_instance

def test_forecasting_strategy_process(mock_state, mock_llm_agent):
    agent = ForecastingStrategyAgent()
    agent.llm_agent = mock_llm_agent
    mock_state.forecasting_extension = MagicMock() # Mock extension input
    
    result = agent.process(mock_state)
    
    assert "handoff" in result
    strategy = result["handoff"]
    assert strategy.analysis_type == AnalysisType.TIME_SERIES
    agent.llm_agent.invoke_with_json.assert_called_once()

def test_comparative_strategy_process(mock_state, mock_llm_agent):
    agent = ComparativeStrategyAgent()
    agent.llm_agent = mock_llm_agent
    mock_state.comparative_extension = MagicMock()
    
    # Update mock return
    mock_handoff = StrategyToCodeGenHandoff(
        profile_reference="profile_x",
        analysis_type=AnalysisType.COMPARATIVE,
        analysis_objective="Forecast",
        feature_columns=[],
        models_to_train=[]
    )
    mock_llm_agent.invoke_with_json.return_value = mock_handoff.model_dump_json()
    
    result = agent.process(mock_state)
    
    assert result["handoff"].analysis_type == AnalysisType.COMPARATIVE

def test_diagnostic_strategy_process(mock_state, mock_llm_agent):
    agent = DiagnosticStrategyAgent()
    agent.llm_agent = mock_llm_agent
    mock_state.diagnostic_extension = MagicMock()
    
    mock_handoff = StrategyToCodeGenHandoff(
            profile_reference="profile_x",
            analysis_type=AnalysisType.CAUSAL,
            analysis_objective="Forecast",
            feature_columns=[],
            models_to_train=[]
        )
    mock_llm_agent.invoke_with_json.return_value = mock_handoff.model_dump_json()
    
    result = agent.process(mock_state)
    
    assert result["handoff"].analysis_type == AnalysisType.CAUSAL

def test_segmentation_strategy_process(mock_state, mock_llm_agent):
    agent = SegmentationStrategyAgent()
    agent.llm_agent = mock_llm_agent
    
    mock_handoff = StrategyToCodeGenHandoff(
            profile_reference="profile_x",
            analysis_type=AnalysisType.CLUSTERING,
            analysis_objective="Forecast",
            feature_columns=[],
            models_to_train=[]
        )
    mock_llm_agent.invoke_with_json.return_value = mock_handoff.model_dump_json()
    
    result = agent.process(mock_state)
    
    assert result["handoff"].analysis_type == AnalysisType.CLUSTERING
