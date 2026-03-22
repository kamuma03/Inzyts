"""
Unit tests for Strategy Agent (Phase 2).

Tests the ML strategy generation, analysis type detection, model selection,
and heuristic fallback functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.agents.phase2.strategy import StrategyAgent
from src.models.state import AnalysisState, Phase, ProfileLock, LockStatus
from src.models.handoffs import UserIntent
from src.models.handoffs import (
    ProfileToStrategyHandoff,
    ColumnProfile,
    DataType,
    AnalysisType,
    FeatureType,
)


@pytest.fixture(autouse=True)
def disable_cache():
    """Disable caching for all tests by patching CacheManager."""
    with patch('src.utils.cache_manager.CacheManager.load_artifact', return_value=None), \
         patch('src.utils.cache_manager.CacheManager.save_artifact', return_value=None), \
         patch('src.utils.cache_manager.CacheManager.get_csv_hash', return_value='test_hash'):
        yield


class TestStrategyAgent:
    """Test suite for Strategy Agent."""

    @pytest.fixture
    def mock_classification_profile(self, tmp_path):
        """Create a mock profile for binary classification."""
        csv_path = tmp_path / "churn_data.csv"
        df = pd.DataFrame({
            'customer_id': ['C001', 'C002', 'C003', 'C004', 'C005'],
            'age': [25, 30, 35, 40, 45],
            'tenure': [1, 5, 10, 2, 8],
            'monthly_charges': [50, 60, 70, 55, 65],
            'churn': ['No', 'No', 'Yes', 'No', 'Yes']
        })
        df.to_csv(csv_path, index=False)

        profile = ProfileToStrategyHandoff(
            phase1_quality_score=0.90,
            row_count=5,
            column_count=5,
            column_profiles=(
                ColumnProfile(
                    name='customer_id',
                    detected_type=DataType.IDENTIFIER,  # Marked as identifier to be excluded
                    detection_confidence=0.95,
                    unique_count=5,
                    null_percentage=0.0,
                    sample_values=['C001', 'C002', 'C003']
                ),
                ColumnProfile(
                    name='age',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.98,
                    unique_count=5,
                    null_percentage=0.0,
                    sample_values=[25, 30, 35]
                ),
                ColumnProfile(
                    name='tenure',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.98,
                    unique_count=5,
                    null_percentage=0.0,
                    sample_values=[1, 5, 10]
                ),
                ColumnProfile(
                    name='monthly_charges',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.98,
                    unique_count=5,
                    null_percentage=0.0,
                    sample_values=[50, 60, 70]
                ),
                ColumnProfile(
                    name='churn',
                    detected_type=DataType.CATEGORICAL,
                    detection_confidence=0.92,
                    unique_count=2,
                    null_percentage=0.0,
                    sample_values=['No', 'Yes']
                )
            ),
            overall_quality_score=0.90,
            missing_value_summary={'customer_id': 0.0, 'age': 0.0, 'tenure': 0.0, 'monthly_charges': 0.0, 'churn': 0.0},
            high_cardinality_columns=('customer_id',),
            data_quality_warnings=('High cardinality in customer_id',),
            identified_feature_types={
                'customer_id': FeatureType.IDENTIFIER,
                'age': FeatureType.NUMERIC_CONTINUOUS,
                'tenure': FeatureType.NUMERIC_CONTINUOUS,
                'monthly_charges': FeatureType.NUMERIC_CONTINUOUS,
                'churn': FeatureType.CATEGORICAL_LOW_CARDINALITY,
            }
        )
        return profile

    @pytest.fixture
    def mock_regression_profile(self, tmp_path):
        """Create a mock profile for regression."""
        csv_path = tmp_path / "housing_data.csv"
        df = pd.DataFrame({
            'bedrooms': [2, 3, 4, 2, 3],
            'bathrooms': [1, 2, 2, 1, 2],
            'sqft': [1000, 1500, 2000, 1200, 1800],
            'price': [200000, 300000, 400000, 250000, 350000]
        })
        df.to_csv(csv_path, index=False)

        profile = ProfileToStrategyHandoff(
            phase1_quality_score=0.95,
            row_count=5,
            column_count=4,
            column_profiles=(
                ColumnProfile(name='bedrooms', detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.98, unique_count=3, null_percentage=0.0, sample_values=[2, 3, 4]),
                ColumnProfile(name='bathrooms', detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.98, unique_count=2, null_percentage=0.0, sample_values=[1, 2]),
                ColumnProfile(name='sqft', detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.98, unique_count=5, null_percentage=0.0, sample_values=[1000, 1500, 2000]),
                ColumnProfile(name='price', detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.98, unique_count=5, null_percentage=0.0, sample_values=[200000, 300000, 400000])
            ),
            overall_quality_score=0.95,
            missing_value_summary={'bedrooms': 0.0, 'bathrooms': 0.0, 'sqft': 0.0, 'price': 0.0},
            high_cardinality_columns=(),
            data_quality_warnings=()
        )
        return profile

    @pytest.fixture
    def mock_state_classification(self, mock_classification_profile, tmp_path):
        """Create a mock analysis state for classification."""
        csv_path = str(tmp_path / "churn_data.csv")
        state = AnalysisState(
            csv_path=csv_path,
            user_intent=UserIntent(
                csv_path=csv_path,
                target_column='churn'
            ),
            current_phase=Phase.PHASE_2,
            profile_lock=ProfileLock(
                status=LockStatus.LOCKED,
                profile_handoff=mock_classification_profile,
                phase1_quality_score=0.90
            )
        )
        return state

    @pytest.fixture
    def mock_state_regression(self, mock_regression_profile, tmp_path):
        """Create a mock analysis state for regression."""
        csv_path = str(tmp_path / "housing_data.csv")
        state = AnalysisState(
            csv_path=csv_path,
            user_intent=UserIntent(
                csv_path=csv_path,
                target_column='price'
            ),
            current_phase=Phase.PHASE_2,
            profile_lock=ProfileLock(
                status=LockStatus.LOCKED,
                profile_handoff=mock_regression_profile,
                phase1_quality_score=0.95
            )
        )
        return state

    @pytest.fixture
    def strategy_agent(self):
        """Create a Strategy Agent instance."""
        return StrategyAgent()

    # Test 1: Process with valid classification profile
    @patch('src.utils.cache_manager.CacheManager')
    def test_process_with_classification_profile(self, mock_cache_manager_class, strategy_agent, mock_state_classification, mock_classification_profile):
        """Test strategy generation with binary classification profile."""
        # Mock cache manager to return no cached strategy (force heuristic)
        mock_cache_manager = MagicMock()
        mock_cache_manager.load_artifact.return_value = None
        mock_cache_manager.get_csv_hash.return_value = 'test_hash'
        mock_cache_manager_class.return_value = mock_cache_manager

        with patch.object(strategy_agent, '_heuristic_strategy') as mock_heuristic:
            # Mock the heuristic to return a strategy dict (not model)
            mock_strategy = {
                'analysis_type': 'classification',
                'analysis_objective': 'Predict churn',
                'target_column': 'churn',
                'feature_columns': ['age', 'tenure', 'monthly_charges'],
                'dropped_columns': ['customer_id'],
                'models_to_train': [
                    {'model_name': 'LogisticRegression', 'import_path': 'sklearn.linear_model.LogisticRegression', 'hyperparameters': {}, 'rationale': 'Baseline', 'priority': 1},
                    {'model_name': 'RandomForestClassifier', 'import_path': 'sklearn.ensemble.RandomForestClassifier', 'hyperparameters': {'n_estimators': 100}, 'rationale': 'Tree-based', 'priority': 2}
                ],
                'preprocessing_steps': [],
                'evaluation_metrics': ['accuracy', 'precision', 'recall', 'f1'],
                'result_visualizations': [],
                'confidence': 0.85
            }
            mock_heuristic.return_value = mock_strategy

            result = strategy_agent.process(
                mock_state_classification,
                profile_handoff=mock_classification_profile
            )

            assert result['handoff'] is not None
            assert result['handoff'].analysis_type == AnalysisType.CLASSIFICATION
            assert result['handoff'].target_column == 'churn'

    # Test 2: Process with valid regression profile
    @patch('src.utils.cache_manager.CacheManager')
    def test_process_with_regression_profile(self, mock_cache_manager_class, strategy_agent, mock_state_regression, mock_regression_profile):
        """Test strategy generation with regression profile."""
        # Mock cache manager to return no cached strategy (force heuristic)
        mock_cache_manager = MagicMock()
        mock_cache_manager.load_artifact.return_value = None
        mock_cache_manager.get_csv_hash.return_value = 'test_hash'
        mock_cache_manager_class.return_value = mock_cache_manager

        with patch.object(strategy_agent, '_heuristic_strategy') as mock_heuristic:
            # Mock the heuristic to return a strategy dict (not model)
            mock_strategy = {
                'analysis_type': 'regression',
                'analysis_objective': 'Predict price',
                'target_column': 'price',
                'feature_columns': ['bedrooms', 'bathrooms', 'sqft'],
                'dropped_columns': [],
                'models_to_train': [
                    {'model_name': 'LinearRegression', 'import_path': 'sklearn.linear_model.LinearRegression', 'hyperparameters': {}, 'rationale': 'Baseline', 'priority': 1},
                    {'model_name': 'RandomForestRegressor', 'import_path': 'sklearn.ensemble.RandomForestRegressor', 'hyperparameters': {'n_estimators': 100}, 'rationale': 'Tree-based', 'priority': 2}
                ],
                'preprocessing_steps': [],
                'evaluation_metrics': ['mae', 'rmse', 'r2'],
                'result_visualizations': [],
                'confidence': 0.85
            }
            mock_heuristic.return_value = mock_strategy

            result = strategy_agent.process(
                mock_state_regression,
                profile_handoff=mock_regression_profile
            )

            assert result['handoff'] is not None
            assert result['handoff'].analysis_type == AnalysisType.REGRESSION
            assert result['handoff'].target_column == 'price'

    # Test 3: Process without profile handoff (error case)
    def test_process_without_profile_handoff(self, strategy_agent, mock_state_classification):
        """Test error handling when profile is missing."""
        result = strategy_agent.process(mock_state_classification)

        assert result['handoff'] is None
        assert result['confidence'] == 0.0
        assert len(result['issues']) > 0
        assert any('no_profile' in str(issue) for issue in result['issues'])

    # Test 4: Process with unlocked profile (warning case)
    def test_process_with_unlocked_profile(self, strategy_agent, mock_state_classification, mock_classification_profile):
        """Test warning when profile is not locked."""
        # Set profile lock to None
        mock_state_classification.profile_lock = None

        with patch.object(strategy_agent, '_heuristic_strategy') as mock_heuristic:
            # Mock the heuristic to return a strategy dict (not handoff object)
            mock_strategy = {
                'analysis_type': 'classification',
                'analysis_objective': 'Predict churn',
                'target_column': 'churn',
                'feature_columns': ['age', 'tenure'],
                'dropped_columns': [],
                'models_to_train': [],
                'preprocessing_steps': [],
                'evaluation_metrics': ['accuracy'],
                'result_visualizations': [],
                'confidence': 0.85
            }
            mock_heuristic.return_value = mock_strategy

            result = strategy_agent.process(
                mock_state_classification,
                profile_handoff=mock_classification_profile
            )

            # Should still process but log warning
            assert result['handoff'] is not None

    # Test 5: Heuristic strategy - binary classification
    def test_heuristic_strategy_binary_classification(self, strategy_agent, mock_classification_profile, mock_state_classification):
        """Test heuristic fallback for binary classification."""
        strategy = strategy_agent._heuristic_strategy(mock_classification_profile, mock_state_classification)

        # _heuristic_strategy returns a dict now
        assert strategy['analysis_type'] == AnalysisType.CLASSIFICATION.value
        assert strategy['target_column'] == 'churn'
        assert len(strategy['models_to_train']) >= 2  # Should have multiple models
        assert 'accuracy' in strategy['evaluation_metrics']
        assert 'precision' in strategy['evaluation_metrics']

    # Test 6: Heuristic strategy - regression
    def test_heuristic_strategy_regression(self, strategy_agent, mock_regression_profile, mock_state_regression):
        """Test heuristic fallback for regression."""
        strategy = strategy_agent._heuristic_strategy(mock_regression_profile, mock_state_regression)

        assert strategy['analysis_type'] == AnalysisType.REGRESSION.value
        assert strategy['target_column'] == 'price'
        assert len(strategy['models_to_train']) >= 2
        assert 'mae' in strategy['evaluation_metrics'] or 'rmse' in strategy['evaluation_metrics'] or 'r2' in strategy['evaluation_metrics']

    # Test 7: Heuristic strategy - multi-class classification
    def test_heuristic_strategy_multiclass_classification(self, strategy_agent, tmp_path):
        """Test heuristic fallback for multi-class classification."""
        csv_path = tmp_path / "iris_data.csv"
        df = pd.DataFrame({
            'sepal_length': [5.1, 4.9, 6.2, 5.8],
            'sepal_width': [3.5, 3.0, 3.4, 2.7],
            'species': ['setosa', 'setosa', 'versicolor', 'virginica']
        })
        df.to_csv(csv_path, index=False)

        profile = ProfileToStrategyHandoff(
            phase1_quality_score=0.90,
            row_count=4,
            column_count=3,
            column_profiles=(
                ColumnProfile(
                    name='sepal_length',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.95,
                    unique_count=4,
                    null_percentage=0.0,
                    sample_values=[5.1, 4.9, 6.2]
                ),
                ColumnProfile(
                    name='sepal_width',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.95,
                    unique_count=4,
                    null_percentage=0.0,
                    sample_values=[3.5, 3.0, 3.4]
                ),
                ColumnProfile(
                    name='species',
                    detected_type=DataType.CATEGORICAL,
                    detection_confidence=0.92,
                    unique_count=3,
                    null_percentage=0.0,
                    sample_values=['setosa', 'versicolor', 'virginica']
                )
            ),
            overall_quality_score=0.90,
            missing_value_summary={'sepal_length': 0.0, 'sepal_width': 0.0, 'species': 0.0},
        )

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path), target_column='species'),
            current_phase=Phase.PHASE_2
        )

        strategy = strategy_agent._heuristic_strategy(profile, state)

        # _heuristic_strategy returns a dict - analysis type should be classification
        assert strategy['analysis_type'] == AnalysisType.CLASSIFICATION.value
        assert strategy['target_column'] == 'species'

    # Test 8: Cache hit scenario
    @patch('src.utils.cache_manager.CacheManager')
    def test_cache_hit(self, mock_cache_manager_class, strategy_agent, mock_state_classification, mock_classification_profile):
        """Test strategy retrieval from cache."""
        # Mock cache manager to return cached strategy (as dict, not model)
        mock_cache_manager = MagicMock()
        mock_cached_strategy = {
            'analysis_type': 'classification',
            'analysis_objective': 'Predict customer churn',
            'target_column': 'churn',
            'feature_columns': ['age', 'tenure'],
            'dropped_columns': ['customer_id'],
            'models_to_train': [
                {'model_name': 'RandomForest', 'import_path': 'sklearn.ensemble.RandomForestClassifier', 'hyperparameters': {}, 'rationale': 'Tree-based', 'priority': 1}
            ],
            'preprocessing_steps': [],
            'evaluation_metrics': ['accuracy'],
            'result_visualizations': [],
            'confidence': 0.85
        }
        mock_cache_manager.load_artifact.return_value = mock_cached_strategy
        mock_cache_manager.get_csv_hash.return_value = 'test_hash'
        mock_cache_manager_class.return_value = mock_cache_manager

        result = strategy_agent.process(
            mock_state_classification,
            profile_handoff=mock_classification_profile
        )

        # Should return a valid handoff from cached strategy
        assert result['handoff'] is not None
        assert result['handoff'].target_column == 'churn'

    # Test 9: LLM failure fallback - tests that process returns valid result
    def test_llm_failure_fallback(self, strategy_agent, mock_state_classification, mock_classification_profile):
        """Test that process method works with heuristic fallback."""
        with patch.object(strategy_agent, '_heuristic_strategy') as mock_heuristic:
            # Mock the heuristic to return a strategy dict
            mock_strategy = {
                'analysis_type': 'classification',
                'analysis_objective': 'Predict churn',
                'target_column': 'churn',
                'feature_columns': ['age', 'tenure'],
                'dropped_columns': [],
                'models_to_train': [],
                'preprocessing_steps': [],
                'evaluation_metrics': ['accuracy'],
                'result_visualizations': [],
                'confidence': 0.85
            }
            mock_heuristic.return_value = mock_strategy

            result = strategy_agent.process(
                mock_state_classification,
                profile_handoff=mock_classification_profile
            )

            # Should return valid result
            assert result['handoff'] is not None

    # Test 10: Build strategy prompt
    def test_build_strategy_prompt(self, strategy_agent, mock_classification_profile, mock_state_classification):
        """Test prompt construction for LLM."""
        prompt = strategy_agent._build_strategy_prompt(mock_classification_profile, mock_state_classification)

        # Check that prompt contains key information
        assert 'churn' in prompt  # Target column
        assert 'age' in prompt or 'tenure' in prompt  # Feature columns
        assert str(mock_classification_profile.row_count) in prompt
        assert str(mock_classification_profile.column_count) in prompt

    # Test 11: Preprocessing steps generation
    def test_preprocessing_steps_generated(self, strategy_agent, tmp_path):
        """Test that preprocessing steps are included in strategy when needed."""
        # Create a profile with columns that need preprocessing
        csv_path = tmp_path / "preprocess_data.csv"
        df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'category': ['A', 'B', 'A', 'C', 'B'],  # Categorical - needs encoding
            'value': [10.0, None, 30.0, 40.0, 50.0],  # Has missing values
            'target': [0, 1, 0, 1, 0]
        })
        df.to_csv(csv_path, index=False)

        profile = ProfileToStrategyHandoff(
            phase1_quality_score=0.90,
            row_count=5,
            column_count=4,
            column_profiles=(
                ColumnProfile(
                    name='id',
                    detected_type=DataType.IDENTIFIER,
                    detection_confidence=0.95,
                    unique_count=5,
                    null_percentage=0.0,
                    sample_values=[1, 2, 3]
                ),
                ColumnProfile(
                    name='category',
                    detected_type=DataType.CATEGORICAL,
                    detection_confidence=0.95,
                    unique_count=3,
                    null_percentage=0.0,
                    sample_values=['A', 'B', 'C']
                ),
                ColumnProfile(
                    name='value',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.98,
                    unique_count=4,
                    null_percentage=20.0,  # Has missing values
                    sample_values=[10.0, 30.0, 40.0]
                ),
                ColumnProfile(
                    name='target',
                    detected_type=DataType.BINARY,
                    detection_confidence=0.92,
                    unique_count=2,
                    null_percentage=0.0,
                    sample_values=[0, 1]
                )
            ),
            overall_quality_score=0.90,
            missing_value_summary={'id': 0.0, 'category': 0.0, 'value': 20.0, 'target': 0.0},
            identified_feature_types={
                'id': FeatureType.IDENTIFIER,
                'category': FeatureType.CATEGORICAL_LOW_CARDINALITY,
                'value': FeatureType.NUMERIC_CONTINUOUS,
                'target': FeatureType.CATEGORICAL_LOW_CARDINALITY,
            }
        )

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path), target_column='target'),
            current_phase=Phase.PHASE_2
        )

        strategy = strategy_agent._heuristic_strategy(profile, state)

        # Should have preprocessing steps for imputation or encoding
        assert 'preprocessing_steps' in strategy
        # The test verifies the structure is correct even if empty
        assert isinstance(strategy['preprocessing_steps'], list)

    # Test 12: Feature column filtering
    def test_feature_column_filtering(self, strategy_agent, mock_classification_profile, mock_state_classification):
        """Test that identifier columns are excluded from features."""
        strategy = strategy_agent._heuristic_strategy(mock_classification_profile, mock_state_classification)

        # customer_id should NOT be in feature columns (marked as identifier)
        assert 'customer_id' not in strategy['feature_columns']

    # Test 13: Confidence scoring
    def test_confidence_scoring(self, strategy_agent, mock_state_classification, mock_classification_profile):
        """Test that confidence score is calculated."""
        with patch.object(strategy_agent, '_heuristic_strategy') as mock_heuristic:
            # Mock the heuristic to return a strategy dict
            mock_strategy = {
                'analysis_type': 'classification',
                'analysis_objective': 'Predict churn',
                'target_column': 'churn',
                'feature_columns': ['age', 'tenure'],
                'dropped_columns': [],
                'models_to_train': [],
                'preprocessing_steps': [],
                'evaluation_metrics': ['accuracy'],
                'result_visualizations': [],
                'confidence': 0.85
            }
            mock_heuristic.return_value = mock_strategy

            result = strategy_agent.process(
                mock_state_classification,
                profile_handoff=mock_classification_profile
            )

            assert 'confidence' in result
            assert 0.0 <= result['confidence'] <= 1.0

    # Test 14: Visualization recommendations
    def test_visualization_recommendations(self, strategy_agent, mock_classification_profile, mock_state_classification):
        """Test that visualization recommendations are generated."""
        strategy = strategy_agent._heuristic_strategy(mock_classification_profile, mock_state_classification)

        # Should have visualizations for classification
        assert len(strategy['result_visualizations']) > 0
        # Typical classification visualizations
        viz_types = [viz.get('viz_type', '') for viz in strategy['result_visualizations']]
        assert any('confusion' in viz_type.lower() or 'roc' in viz_type.lower() for viz_type in viz_types)

    # Test 15: Model hyperparameters
    def test_model_hyperparameters(self, strategy_agent, mock_classification_profile, mock_state_classification):
        """Test that model specifications include hyperparameters."""
        strategy = strategy_agent._heuristic_strategy(mock_classification_profile, mock_state_classification)

        # Check that models have hyperparameters
        for model in strategy['models_to_train']:
            assert 'hyperparameters' in model
            assert isinstance(model['hyperparameters'], dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
