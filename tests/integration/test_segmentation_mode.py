import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from src.agents.phase2 import SegmentationStrategyAgent
from src.models.state import AnalysisState, PipelineMode, ProfileLock
from src.models.handoffs import (
    ProfileToStrategyHandoff, 
    ColumnProfile, 
    DataType,
    StrategyToCodeGenHandoff,
    AnalysisType
)

@pytest.fixture
def segmentation_data():
    """Create a dataset suitable for clustering."""
    # Cluster 1: High spend, High engagement
    c1 = pd.DataFrame({
        "spend": np.random.normal(1000, 100, 50),
        "engagement": np.random.normal(10, 2, 50)
    })
    # Cluster 2: Low spend, Low engagement
    c2 = pd.DataFrame({
        "spend": np.random.normal(200, 50, 50),
        "engagement": np.random.normal(2, 1, 50)
    })
    
    return pd.concat([c1, c2], ignore_index=True)

@pytest.fixture
def segmentation_profile(segmentation_data):
    """Create a profile matching the segmentation data."""
    return ProfileToStrategyHandoff(
        profile_lock=MagicMock(),
        row_count=100,
        column_count=2,
        column_profiles=[
            ColumnProfile(name="spend", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[]),
            ColumnProfile(name="engagement", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=1.0, unique_count=100, null_percentage=0.0, sample_values=[])
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
def mock_state(segmentation_data, segmentation_profile):
    state = MagicMock(spec=AnalysisState)
    state.pipeline_mode = PipelineMode.SEGMENTATION
    state.csv_data = segmentation_data.to_dict(orient='records')
    
    # Mock Profile Lock
    state.profile_lock = MagicMock(spec=ProfileLock)
    state.profile_lock.is_locked.return_value = True
    state.profile_lock.get_locked_handoff.return_value = segmentation_profile
    
    state.user_intent = None
    # Segmentation has no explicit extension object in state currently, 
    # it relies on profile data.
    return state

class TestSegmentationMode:
    
    def test_segmentation_strategy_prompt_construction(self, mock_state):
        """
        Verify SegmentationStrategyAgent prompts for clustering.
        """
        agent = SegmentationStrategyAgent()
        
        with patch.object(agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_handoff = StrategyToCodeGenHandoff(
                profile_reference="ref",
                analysis_type=AnalysisType.CLUSTERING,
                analysis_objective="Customer Segmentation",
                feature_columns=["spend", "engagement"],
                models_to_train=[]
            )
            mock_llm.return_value = mock_handoff.model_dump_json()
            
            result = agent.process(mock_state)
            
            # Verify Prompt Content
            call_args = mock_llm.call_args
            prompt_text = call_args[1].get('prompt', call_args.kwargs.get('prompt'))
            
            # Should ask for clustering / segmentation
            assert "segmentation" in prompt_text.lower() or "clustering" in prompt_text.lower()
            assert "spend" in prompt_text
            
            assert result["strategy_outputs"][0].analysis_type == AnalysisType.CLUSTERING
