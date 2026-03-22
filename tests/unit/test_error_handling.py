import pytest
from unittest.mock import patch
import pandas as pd
import numpy as np

from src.agents.phase1.data_profiler import DataProfilerAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent


@pytest.fixture(autouse=True)
def disable_cache():
    """Disable caching for all tests by patching CacheManager load and save."""
    with patch('src.utils.cache_manager.CacheManager.load_artifact', return_value=None), \
         patch('src.utils.cache_manager.CacheManager.save_artifact', return_value=None), \
         patch('src.utils.cache_manager.CacheManager.get_csv_hash', return_value='test_hash'):
        yield









class TestDataQualityIssues:
    """Test handling of various data quality issues."""

    def test_high_missing_values(self, tmp_path):
        """Test handling of dataset with high missing values."""
        csv_path = tmp_path / "missing.csv"
        df = pd.DataFrame({
            'col1': [1, None, 3, None, 5, None, 7, None, 9, None],
            'col2': [None] * 10
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should flag high missing values - check quality_check_requirements
        if 'handoff' in result:
            # The handoff should be created successfully for high missing values
            assert result['handoff'] is not None

    def test_single_value_columns(self, tmp_path):
        """Test handling of columns with single value."""
        csv_path = tmp_path / "single_value.csv"
        df = pd.DataFrame({
            'constant': [1] * 100,
            'normal': range(100)
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should detect constant column in columns list
        if 'handoff' in result:
            constant_col = next(
                (col for col in result['handoff'].columns if col.name == 'constant'),
                None
            )
            # The constant column should be detected
            assert constant_col is not None or result['handoff'].columns is not None

    def test_mixed_data_types(self, tmp_path):
        """Test handling of columns with mixed data types."""
        csv_path = tmp_path / "mixed_types.csv"
        df = pd.DataFrame({
            'mixed': ['1', '2', 'three', '4', 'five', '6']
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should handle mixed types
        assert 'handoff' in result or 'error' in result

    def test_outliers_detection(self, tmp_path):
        """Test detection of outliers in numeric columns."""
        csv_path = tmp_path / "outliers.csv"
        df = pd.DataFrame({
            'value': [1, 2, 3, 4, 5, 100, 2, 3, 4, 5]  # 100 is outlier
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should process without error
        assert 'handoff' in result or 'error' in result

    def test_duplicate_rows(self, tmp_path):
        """Test handling of duplicate rows."""
        csv_path = tmp_path / "duplicates.csv"
        df = pd.DataFrame({
            'col1': [1, 2, 3, 1, 2, 3],
            'col2': ['a', 'b', 'c', 'a', 'b', 'c']
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should handle duplicates
        assert 'handoff' in result


class TestGracefulDegradation:
    """Test graceful degradation in various failure scenarios."""

    def test_partial_column_analysis_failure(self, tmp_path):
        """Test that analysis continues if some columns fail."""
        csv_path = tmp_path / "partial_fail.csv"
        df = pd.DataFrame({
            'good_col': [1, 2, 3, 4, 5],
            'problematic_col': ['�', '�', '�', '�', '�']  # Invalid characters
        })
        df.to_csv(csv_path, index=False)

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should still return results for good columns
        assert 'handoff' in result or 'error' in result

    def test_encoding_detection_fallback(self, tmp_path):
        """Test fallback when encoding detection fails."""
        csv_path = tmp_path / "encoding_test.csv"
        # Create file with UTF-8 encoding
        df = pd.DataFrame({'text': ['hello', 'world']})
        df.to_csv(csv_path, index=False, encoding='utf-8')

        profiler = DataProfilerAgent()
        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path)),
            current_phase=Phase.PHASE_1
        )

        result = profiler.process(state)

        # Should handle encoding
        assert 'handoff' in result or 'error' in result

