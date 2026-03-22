import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.agents.extensions import DiagnosticExtensionAgent
from src.agents.phase2 import DiagnosticStrategyAgent
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import (
    ProfileToStrategyHandoff, 
    ColumnProfile, 
    DataType,
    DiagnosticExtension,
    StrategyToCodeGenHandoff,
    AnalysisType
)

@pytest.fixture
def diagnostic_data():
    """Create a dataset with clear anomalies and change points."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    
    # Base signal
    values = np.random.normal(100, 10, 100)
    
    # Introduce a Change Point (Step change) at index 50
    values[50:] += 50  # Jump from ~100 to ~150
    
    # Introduce an Anomaly (Spike) at index 20
    values[20] = 300  # 20 sigma event
    
    df = pd.DataFrame({
        "date": dates,
        "sales": values,
        "region": ["A"] * 50 + ["B"] * 50 # Categorical dimension
    })
    return df

@pytest.fixture
def diagnostic_profile(diagnostic_data):
    """Create a profile matching the diagnostic data."""
    return ProfileToStrategyHandoff(
        profile_lock=MagicMock(),
        row_count=100,
        column_count=3,
        column_profiles=[
            ColumnProfile(name="date", detected_type=DataType.DATETIME, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[]),
            ColumnProfile(name="sales", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[]),
            ColumnProfile(name="region", detected_type=DataType.CATEGORICAL, detection_confidence=1.0, unique_count=2, null_percentage=0.0, sample_values=["A", "B"])
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
def mock_state(diagnostic_data, diagnostic_profile):
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.DIAGNOSTIC
    state.csv_data = diagnostic_data.to_dict(orient='records')
    
    # Mock Profile Lock
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.get_locked_handoff.return_value = diagnostic_profile
    
    state.user_intent = None
    return state

class TestDiagnosticMode:
    
    def test_diagnostic_extension_heuristics(self, mock_state):
        """
        Verify that DiagnosticExtensionAgent correctly identifies:
        1. Temporal column
        2. Anomalies (Z-score)
        3. Change Points (Rolling mean shift)
        WITHOUT relying on the LLM (checking the context passed TO the LLM).
        """
        agent = DiagnosticExtensionAgent()

        # We verify heuristics by inspecting what is passed to the LLM
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            # Return dummy response to allow process to finish
            # Return dummy response with all required fields
            mock_llm.return_value = DiagnosticExtension(
                profile_reference="ref",
                has_temporal_data=True,
                temporal_column="date",
                before_period=None, after_period=None,
                metric_columns=["sales"],
                primary_metric="sales",
                metric_direction="higher_is_better",
                dimension_columns=["region"],
                change_points_detected=[],
                anomalies_detected=[],
                recommended_analysis=["decomposition"],
                created_at=datetime.now(),
                csv_hash="dummy_hash"
            ).model_dump_json()

            result = agent.process(mock_state)

            # 1. Capture the 'user_input' passed to LLM, which contains the context
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt')) # user_input kwarg

            # 2. Verify Heuristic Detections in Prompt Context
            # Optional: print(prompt_text) to debug

            # Check Temporal Column detection
            assert "'temporal_column': 'date'" in prompt_text or "'temporal_column': 'date'" in str(prompt_text)

            # Check Anomaly Detection (Value 300 at index 20)
            assert "Z-score" in prompt_text
            # We expect at least 1 anomaly
            assert "Found" in prompt_text

            # Check Change Point Detection (Jump at index 50)
            assert "change_points_summary': 'Found" in prompt_text

            # 3. Verify Output Structure
            assert "diagnostic_extension" in result
            assert result["confidence"] == 1.0

    def test_diagnostic_strategy_prompt_construction(self, mock_state):
        """
        Verify that DiagnosticStrategyAgent constructs the strategy prompt correctly
        using the output from the Extension agent.
        """
        # Setup Extension Output in State
        extension_output = DiagnosticExtension(
            profile_reference="ref",
            has_temporal_data=True,
            temporal_column="date",
            before_period=None, after_period=None,
            metric_columns=["sales"],
            primary_metric="sales",
            metric_direction="higher_is_better",
            dimension_columns=["region"],
            change_points_detected=[],
            anomalies_detected=[],
            recommended_analysis=["decomposition"],
            created_at=datetime.now(),
            csv_hash="dummy_hash"
        )
        mock_state.diagnostic_extension = extension_output

        agent = DiagnosticStrategyAgent()
        
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_handoff = StrategyToCodeGenHandoff(
                profile_reference="ref",
                analysis_type=AnalysisType.CAUSAL,
                analysis_objective="Diagnose sales drop",
                feature_columns=[],
                models_to_train=[]
            )
            mock_llm.return_value = mock_handoff.model_dump_json()
            
            result = agent.process(mock_state)
            
            # Verify Prompt Content
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            # Should contain profile summary
            assert "profile_summary" in prompt_text
            # Should contain extension output
            assert "extension_output" in prompt_text
            assert "sales" in prompt_text # metric
            assert "decomposition" in prompt_text # recommendation being passed through
            
            # Verify Result
            assert result["strategy_outputs"][0].analysis_type == AnalysisType.CAUSAL
