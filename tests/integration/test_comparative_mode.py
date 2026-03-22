import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.agents.extensions import ComparativeExtensionAgent
from src.agents.phase2 import ComparativeStrategyAgent
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import (
    ProfileToStrategyHandoff, 
    ColumnProfile, 
    DataType,
    ComparativeExtension,
    StrategyToCodeGenHandoff,
    AnalysisType,
    RecommendedTest
)

@pytest.fixture
def comparative_data():
    """Create a dataset suitable for A/B testing or group comparison."""
    # Group A: Control (Mean ~ 100)
    group_a = pd.DataFrame({
        "group": ["Control"] * 50,
        "conversion": np.random.binomial(1, 0.1, 50), # 10% conversion
        "spend": np.random.normal(100, 10, 50)
    })
    
    # Group B: Treatment (Mean ~ 120)
    group_b = pd.DataFrame({
        "group": ["Treatment"] * 50,
        "conversion": np.random.binomial(1, 0.2, 50), # 20% conversion
        "spend": np.random.normal(120, 15, 50)
    })
    
    return pd.concat([group_a, group_b], ignore_index=True)

@pytest.fixture
def comparative_profile(comparative_data):
    """Create a profile matching the comparative data."""
    return ProfileToStrategyHandoff(
        profile_lock=MagicMock(),
        row_count=100,
        column_count=3,
        column_profiles=[
            ColumnProfile(name="group", detected_type=DataType.CATEGORICAL, detection_confidence=1.0, unique_count=2, null_percentage=0.0, sample_values=["Control", "Treatment"]),
            ColumnProfile(name="conversion", detected_type=DataType.BINARY, detection_confidence=1.0, unique_count=2, null_percentage=0.0, sample_values=[0, 1]),
            ColumnProfile(name="spend", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[])
        ],
        overall_quality_score=1.0,
        phase1_quality_score=1.0,
        missing_value_summary={},
        data_quality_warnings=[],
        recommended_target_candidates=[],
        identified_feature_types={},
        temporal_columns=[],
        high_cardinality_columns=[],
        detected_patterns=[],
        profile_cells=[]
    )

@pytest.fixture
def mock_state(comparative_data, comparative_profile):
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.COMPARATIVE
    state.csv_data = comparative_data.to_dict(orient='records')
    
    # Mock Profile Lock
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.get_locked_handoff.return_value = comparative_profile
    
    state.user_intent = None
    return state

class TestComparativeMode:
    
    def test_comparative_extension_logic(self, mock_state):
        """
        Verify that ComparativeExtensionAgent correctly helps identify groups
        and suggests tests.
        """
        agent = ComparativeExtensionAgent()
        
        # Mocking LLM output for the extension
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = ComparativeExtension(
                group_column="group",
                group_values=["Control", "Treatment"],
                baseline_group="Control",
                treatment_groups=["Treatment"],
                group_sizes={"Control": 50, "Treatment": 50},
                balance_ratio=1.0,
                is_balanced=True,
                numeric_metrics=["spend"],
                categorical_metrics=["conversion"],
                recommended_primary_metric="conversion",
                recommended_tests=[
                    RecommendedTest(metric="conversion", test_type="chi_square", rationale="Binary outcome"),
                    RecommendedTest(metric="spend", test_type="t_test", rationale="Numeric outcome")
                ],
                multiple_comparison_correction="none",
                created_at=datetime.now(),
                csv_hash="dummy_hash"
            ).model_dump_json()
            
            result = agent.process(mock_state)
            
            # Check context passed to LLM
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            # Context should contain profile data implying groups
            assert "group_candidates" in str(prompt_text) or "group_candidates" in str(call_args)
            
            assert "comparative_extension" in result
            assert result["confidence"] == 1.0

    def test_comparative_strategy_prompt_construction(self, mock_state):
        """
        Verify ComparativeStrategyAgent receives extension output and plans the analysis.
        """
        # Setup Extension Output in State
        extension_output = ComparativeExtension(
            group_column="group",
            group_values=["Control", "Treatment"],
            baseline_group="Control",
            treatment_groups=["Treatment"],
            group_sizes={"Control": 50, "Treatment": 50},
            balance_ratio=1.0,
            is_balanced=True,
            numeric_metrics=["spend"],
            categorical_metrics=["conversion"],
            recommended_primary_metric="conversion",
            recommended_tests=[
                RecommendedTest(metric="conversion", test_type="chi_square", rationale="Binary outcome"),
                RecommendedTest(metric="spend", test_type="t_test", rationale="Numeric outcome")
            ],
            multiple_comparison_correction="none",
            created_at=datetime.now(),
            csv_hash="dummy_hash"
        )
        mock_state.comparative_extension = extension_output
        
        agent = ComparativeStrategyAgent()
        
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_handoff = StrategyToCodeGenHandoff(
                profile_reference="ref",
                analysis_type=AnalysisType.COMPARATIVE,
                analysis_objective="A/B Test",
                feature_columns=["group", "spend", "conversion"],
                models_to_train=[]
            ).model_dump_json()
            mock_llm.return_value = mock_handoff
            
            result = agent.process(mock_state)
            
            # Verify Prompt Content
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            # Key elements that must be in the prompt for the LLM to do its job
            assert "Control" in prompt_text
            assert "Treatment" in prompt_text
            assert "chi_square" in prompt_text
            assert "t_test" in prompt_text
            
            assert result["strategy_outputs"][0].analysis_type == AnalysisType.COMPARATIVE
