"""
Unit tests for Analysis Code Generator Agent (Phase 2).
Focuses on the Agent's process flow and interaction with helpers.
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import json

from src.agents.phase2.analysis_codegen import AnalysisCodeGeneratorAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent, StrategyToCodeGenHandoff, AnalysisType, AnalysisCodeToValidatorHandoff, ModelSpec, ValidationStrategy
from src.models.cells import NotebookCell

class TestAnalysisCodeGeneratorAgent:
    """Test suite for Analysis Code Generator Agent."""

    @pytest.fixture
    def mock_classification_strategy(self, tmp_path):
        return StrategyToCodeGenHandoff(
            profile_reference="locked_profile_123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Predict churn probability",
            target_column='churn',
            feature_columns=['age', 'tenure'],
            dropped_columns=['customer_id'],
            models_to_train=[ModelSpec(model_name='LogisticRegression', import_path='sklearn.linear_model.LogisticRegression', hyperparameters={}, priority=1, rationale='Baseline')],
            preprocessing_steps=[],
            validation_strategy=ValidationStrategy(method='train_test_split', parameters={'test_size': 0.2}),
            evaluation_metrics=['accuracy'],
            result_visualizations=[]
        )

    @pytest.fixture
    def mock_state(self, tmp_path):
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame({'age': [25, 30], 'churn': ['No', 'Yes']})
        df.to_csv(csv_path, index=False)
        return AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path), analysis_type_hint=AnalysisType.CLASSIFICATION, target_column='churn'),
            current_phase=Phase.PHASE_2
        )

    @pytest.fixture
    def codegen_agent(self):
        return AnalysisCodeGeneratorAgent()

    @patch('src.agents.phase2.analysis_codegen.CacheManager')
    def test_process_with_strategy_success(self, mock_cache_class, codegen_agent, mock_state, mock_classification_strategy):
        """Test successful processing using TemplateGenerator fallback (mocked LLM failure)."""
        mock_cache = MagicMock()
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache
        
        # Mock LLM to fail JSON decoding to trigger template fallback (deterministic test)
        codegen_agent.llm_agent.invoke_with_json = MagicMock(return_value="INVALID JSON")
        
        result = codegen_agent.process(mock_state, strategy=mock_classification_strategy)
        
        assert result['handoff'] is not None
        assert isinstance(result['handoff'], AnalysisCodeToValidatorHandoff)
        assert len(result['handoff'].cells) > 0
        assert result['confidence'] == 0.85 # Default template confidence

    def test_process_without_strategy(self, codegen_agent, mock_state):
        """Test error handling when strategy is missing."""
        result = codegen_agent.process(mock_state)
        assert result['handoff'] is None
        assert len(result['issues']) > 0

    @patch('src.agents.phase2.analysis_codegen.CacheManager')
    def test_cache_hit(self, mock_cache_manager_class, codegen_agent, mock_state, mock_classification_strategy):
        """Test retrieval from cache."""
        # Enable cache usage so the cache path is entered
        mock_state.using_cached_profile = True

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = 'hash'
        mock_cache.load_artifact.return_value = {
            'cells': [{'cell_type': 'code', 'source': 'print("Cached")', 'metadata': {}}],
            'result': {'confidence': 0.9},
            'cell_manifest': []
        }
        mock_cache_manager_class.return_value = mock_cache

        result = codegen_agent.process(mock_state, strategy=mock_classification_strategy)

        assert len(result['handoff'].cells) == 1
        assert result['handoff'].cells[0].source == 'print("Cached")'
    
    @patch('src.agents.phase2.analysis_codegen.CacheManager')
    def test_process_llm_success(self, mock_cache_class, codegen_agent, mock_state, mock_classification_strategy):
        """Test successful LLM generation."""
        # Ensure cache miss
        mock_cache = MagicMock()
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        # Use valid NotebookCell structure
        valid_cell = NotebookCell(cell_type="code", source="import pandas", metadata={})
        valid_json = json.dumps({
            "cells": [valid_cell.dict()],
            "cell_manifest": [],
            "confidence": 0.95
        })
        
        codegen_agent.llm_agent.invoke_with_json = MagicMock(return_value=valid_json)
        
        result = codegen_agent.process(mock_state, strategy=mock_classification_strategy)
        
        # Check if fallback happened (fallback produces 13 cells, success produces 1)
        assert len(result['handoff'].cells) == 1, "Fallback template generation was triggered unexpectedly"
        assert result['confidence'] == 0.95

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
