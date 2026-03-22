import pytest
import pandas as pd
from unittest.mock import patch
from pathlib import Path
from src.server.services.metrics_service import MetricsService

class TestMetricsService:
    
    @patch("src.server.services.metrics_service.pd.read_csv")
    @patch("src.server.services.metrics_service.Path.exists")
    def test_get_job_metrics_cached(self, mock_exists, mock_read_csv):
        """Test that get_job_metrics returns correct structure and uses cache."""
        mock_exists.return_value = True
        
        # Setup mock DF
        df = pd.DataFrame({
            "A": [1, 2, 3, None],
            "B": ["x", "y", "z", "w"]
        })
        mock_read_csv.return_value = df
        
        service = MetricsService()
        
        # First call
        metrics1 = service.get_job_metrics("job1", Path("dummy.csv"))
        
        assert metrics1["job_id"] == "job1"
        assert metrics1["row_count"] == 4
        assert metrics1["col_count"] == 2
        assert metrics1["numeric_stats"]["A"]["mean"] == 2.0
        
        # Second call - should use cache (we can verify by checking read_csv call count)
        metrics2 = service.get_job_metrics("job1", Path("dummy.csv"))
        assert metrics2 == metrics1
        
        # Ensure read_csv called only once
        assert mock_read_csv.call_count == 1

    def test_file_not_found(self):
         service = MetricsService()
         with pytest.raises(FileNotFoundError):
             service.get_job_metrics("job2", Path("nonexistent.csv"))
