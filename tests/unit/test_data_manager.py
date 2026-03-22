"""
Unit tests for DataManager service.

Tests data loading with robust CSV handling, metadata extraction,
and utility methods.
"""

import pytest
import pandas as pd

from src.services.data_manager import DataManager


class TestDataManager:
    """Test suite for DataManager service."""

    @pytest.fixture
    def data_manager(self):
        return DataManager()

    @pytest.fixture
    def sample_csv(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "age": [25, 30, 35, 40, 45],
            "salary": [50000.0, 60000.0, 70000.0, 80000.0, 90000.0],
        })
        df.to_csv(csv_path, index=False)
        return str(csv_path)

    @pytest.fixture
    def semicolon_csv(self, tmp_path):
        csv_path = tmp_path / "semicolon.csv"
        csv_path.write_text("id;name;age\n1;Alice;25\n2;Bob;30\n")
        return str(csv_path)

    def test_load_csv(self, data_manager, sample_csv):
        """Test loading a standard CSV file."""
        df = data_manager.load_data(sample_csv)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert list(df.columns) == ["id", "name", "age", "salary"]

    def test_load_semicolon_csv(self, data_manager, semicolon_csv):
        """Test loading a semicolon-delimited CSV via robust loader."""
        df = data_manager.load_data(semicolon_csv)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "name" in df.columns

    def test_load_nonexistent_file(self, data_manager):
        """Test loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            data_manager.load_data("/nonexistent/path.csv")

    def test_load_parquet(self, data_manager, tmp_path):
        """Test loading a Parquet file."""
        pytest.importorskip("pyarrow") # Skip if pyarrow is not installed
        
        parquet_path = tmp_path / "data.parquet"
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        df.to_parquet(parquet_path, index=False)

        result = data_manager.load_data(str(parquet_path))

        assert len(result) == 2
        assert list(result.columns) == ["a", "b"]

    def test_get_basic_metadata(self, data_manager, sample_csv):
        """Test extracting basic metadata from a DataFrame."""
        df = data_manager.load_data(sample_csv)
        metadata = data_manager.get_basic_metadata(df)

        assert metadata["row_count"] == 5
        assert metadata["column_count"] == 4
        assert "id" in metadata["columns"]
        assert metadata["duplicates"] == 0
        assert metadata["memory_usage"] > 0

    def test_get_unique_counts(self, data_manager, sample_csv):
        """Test getting unique value counts."""
        df = data_manager.load_data(sample_csv)
        unique_counts = data_manager.get_unique_counts(df)

        assert unique_counts["id"] == 5
        assert unique_counts["name"] == 5

    def test_get_sample(self, data_manager, sample_csv):
        """Test getting a random sample."""
        df = data_manager.load_data(sample_csv)
        sample = data_manager.get_sample(df, n=3)

        assert len(sample) == 3

    def test_get_sample_small_df(self, data_manager):
        """Test get_sample returns full df when n >= length."""
        df = pd.DataFrame({"a": [1, 2]})
        sample = data_manager.get_sample(df, n=5)

        assert len(sample) == 2

    def test_get_head(self, data_manager, sample_csv):
        """Test getting top N rows."""
        df = data_manager.load_data(sample_csv)
        head = data_manager.get_head(df, n=2)

        assert len(head) == 2
        assert head.iloc[0]["name"] == "Alice"

    def test_metadata_missing_values(self, data_manager, tmp_path):
        """Test metadata correctly reports missing values."""
        csv_path = tmp_path / "missing.csv"
        df = pd.DataFrame({
            "a": [1, None, 3],
            "b": [None, None, "x"],
        })
        df.to_csv(csv_path, index=False)

        loaded = data_manager.load_data(str(csv_path))
        metadata = data_manager.get_basic_metadata(loaded)

        assert metadata["missing_values"]["a"] == 1
        assert metadata["missing_values"]["b"] == 2
