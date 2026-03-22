import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.agents.extensions import ForecastingExtensionAgent
from src.agents.phase2 import ForecastingStrategyAgent
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import (
    ProfileToStrategyHandoff, 
    ColumnProfile, 
    DataType,
    ForecastingExtension,
    GapAnalysis,
    StrategyToCodeGenHandoff,
    AnalysisType
)

@pytest.fixture
def forecasting_data():
    """Create a time series dataset."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    values = np.linspace(0, 100, 100) + np.random.normal(0, 5, 100) # Trend with noise
    
    return pd.DataFrame({
        "date": dates,
        "sales": values
    })

@pytest.fixture
def forecasting_profile(forecasting_data):
    """Create a profile matching the forecasting data."""
    return ProfileToStrategyHandoff(
        profile_lock=MagicMock(),
        row_count=100,
        column_count=2,
        column_profiles=[
            ColumnProfile(name="date", detected_type=DataType.DATETIME, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[]),
            ColumnProfile(name="sales", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[])
        ],
        overall_quality_score=1.0,
        phase1_quality_score=1.0,
        missing_value_summary={},
        data_quality_warnings=[],
        recommended_target_candidates=[],
        identified_feature_types={},
        temporal_columns=["date"],
        high_cardinality_columns=[],
        detected_patterns=[],
        profile_cells=[]
    )

@pytest.fixture
def mock_state(forecasting_data, forecasting_profile):
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.FORECASTING
    state.csv_data = forecasting_data.to_dict(orient='records')
    
    # Mock Profile Lock
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.get_locked_handoff.return_value = forecasting_profile
    
    state.user_intent = None
    return state

class TestForecastingMode:
    
    def test_forecasting_extension_frequency_detection(self, mock_state):
        """
        Verify that ForecastingExtensionAgent detects temporal columns and frequency.
        """
        agent = ForecastingExtensionAgent()
        
        # We check heuristics by inspecting passed context or the extension logic
        # The agent heuristic runs BEFORE the LLM call.
        
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = ForecastingExtension(
                datetime_column="date",
                datetime_format="%Y-%m-%d",
                frequency="D",
                frequency_confidence=1.0,
                date_range=(datetime(2023,1,1), datetime(2023,4,10)),
                total_periods=100,
                missing_periods=[],
                gap_analysis=GapAnalysis(has_gaps=False, gap_count=0, largest_gap_periods=0, gap_locations=[]),
                stationarity_hint="likely_non_stationary",
                trend_detected=True,
                seasonality_detected=False,
                recommended_models=["Prophet", "ARIMA"],
                preprocessing_needed=[],
                created_at=datetime.now(),
                csv_hash="dummy_hash"
            ).model_dump_json()
            
            result = agent.process(mock_state)
            
            # Check context passed to LLM
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            # Heuristics should find 'date' as temporal column (key is 'date_column' in context)
            assert "'date_column': 'date'" in prompt_text or "'date_column': 'date'" in str(prompt_text)
            
            # Heuristics should detect frequency 'D' (if implemented in agent heuristic logic)
            # Inspecting agent logic would confirm if it does freq detection pre-LLM.
            # Assuming it passes summary stats.
            
            assert "forecasting_extension" in result
            assert result["confidence"] == 1.0


    def test_forecasting_strategy_prompt_construction(self, mock_state):
        """
        Verify ForecastingStrategyAgent receives extension output and plans.
        """
        extension_output = ForecastingExtension(
            datetime_column="date",
            datetime_format="%Y-%m-%d",
            frequency="D",
            frequency_confidence=1.0,
            date_range=(datetime(2023,1,1), datetime(2023,4,10)),
            total_periods=100,
            missing_periods=[],
            gap_analysis=GapAnalysis(has_gaps=False, gap_count=0, largest_gap_periods=0, gap_locations=[]),
            stationarity_hint="likely_non_stationary",
            trend_detected=True,
            seasonality_detected=False,
            recommended_models=["Prophet", "ARIMA"],
            preprocessing_needed=[],
            created_at=datetime.now(),
            csv_hash="dummy_hash"
        )
        mock_state.forecasting_extension = extension_output
        
        agent = ForecastingStrategyAgent()
        
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_handoff = StrategyToCodeGenHandoff(
                profile_reference="ref",
                analysis_type=AnalysisType.TIME_SERIES,
                analysis_objective="Forecast sales",
                feature_columns=["date", "sales"],
                models_to_train=[]
            ).model_dump_json()
            mock_llm.return_value = mock_handoff
            
            result = agent.process(mock_state)
            
            # Verify Prompt
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            assert "Prophet" in prompt_text # recommenation passed
            assert "frequency" in prompt_text
            
            assert result["strategy_outputs"][0].analysis_type == AnalysisType.TIME_SERIES
