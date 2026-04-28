import unittest
import os
import tempfile
import pandas as pd
from unittest.mock import MagicMock, patch

# Mock logger before imports
logger_patcher = patch('src.utils.logger.get_logger')
mock_logger = logger_patcher.start()
mock_logger.return_value = MagicMock()

from src.services.data_loader import DataLoader
from src.models.multi_file import MultiFileInput, FileInput

class TestDataLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.test_dir, "file1.csv")
        self.file2 = os.path.join(self.test_dir, "file2.csv")
        self.file3 = os.path.join(self.test_dir, "file3.csv")
        self.parquet_file = os.path.join(self.test_dir, "data.parquet")
        self.log_file = os.path.join(self.test_dir, "data.log")
        self.parquet_available = False
        
        # Create test CSVs
        # File 1: Customers
        df1 = pd.DataFrame({
            "CustomerID": [1, 2, 3],
            "Name": ["Alice", "Bob", "Charlie"]
        })
        df1.to_csv(self.file1, index=False)
        
        # File 2: Orders (FK: CustomerID)
        df2 = pd.DataFrame({
            "OrderID": [101, 102, 103],
            "CustomerID": [1, 2, 4], # 4 is not in file1
            "Amount": [100, 200, 300]
        })
        df2.to_csv(self.file2, index=False)
        
        # File 3: Unrelated
        df3 = pd.DataFrame({
            "ProductID": [10, 20],
            "Name": ["Widget A", "Widget B"]
        })
        df3.to_csv(self.file3, index=False)
        
        # Create Parquet file (if pyarrow/fastparquet available)
        df_parquet = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [100.5, 200.7, 300.9],
            "category": ["A", "B", "C"]
        })
        try:
            df_parquet.to_parquet(self.parquet_file, index=False)
            self.parquet_available = True
        except ImportError:
            # pyarrow/fastparquet not installed, skip parquet tests
            pass
        
        # Create Log file (CSV-style)
        df_log = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "level": ["INFO", "WARNING", "ERROR"],
            "message": ["Started", "Low memory", "Crash"]
        })
        df_log.to_csv(self.log_file, index=False)
        
        self.loader = DataLoader()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)
        logger_patcher.stop()

    def test_load_csv(self):
        """Test loading a CSV file."""
        df = self.loader.load_dataset(self.file1)
        self.assertEqual(len(df), 3)
        self.assertIn("CustomerID", df.columns)
        self.assertIn("Name", df.columns)

    def test_load_parquet(self):
        """Test loading a Parquet file."""
        if not self.parquet_available:
            self.skipTest("pyarrow/fastparquet not installed")
        df = self.loader.load_dataset(self.parquet_file)
        self.assertEqual(len(df), 3)
        self.assertIn("id", df.columns)
        self.assertIn("value", df.columns)
        self.assertIn("category", df.columns)
        # Verify data integrity
        self.assertEqual(df.iloc[0]["id"], 1)
        self.assertAlmostEqual(df.iloc[0]["value"], 100.5)

    def test_load_log(self):
        """Test loading a log file (CSV-style)."""
        df = self.loader.load_dataset(self.log_file)
        self.assertEqual(len(df), 3)
        self.assertIn("timestamp", df.columns)
        self.assertIn("level", df.columns)
        self.assertIn("message", df.columns)
        # Verify data integrity
        self.assertEqual(df.iloc[1]["level"], "WARNING")

    def test_detect_joins(self):
        candidates = self.loader.detect_joins([self.file1, self.file2])
        self.assertTrue(len(candidates) > 0)
        
        # Should detect CustomerID
        match = next((c for c in candidates if c.left_column == "CustomerID"), None)
        self.assertIsNotNone(match)
        self.assertTrue(match.confidence_score > 0.6)

    def test_merge_datasets_auto(self):
        input_spec = MultiFileInput(
            files=[
                FileInput(file_path=self.file1, file_hash="1"),
                FileInput(file_path=self.file2, file_hash="2")
            ]
        )
        
        merged_df, meta = self.loader.merge_datasets(input_spec)
        
        # Expect LEFT join logic (default)
        self.assertEqual(len(merged_df), 3) # 1, 2 joined. 3 is left (since file1 is left). 
        # Wait, if file2 has 4, and it's left join file1->file2:
        # 1->101, 2->102, 3->NaN (if not in file2)
        # file2 has 4, which is not in file1.
        
        # Check columns
        self.assertIn("Name", merged_df.columns)
        self.assertIn("Amount", merged_df.columns)
        
    def test_merge_datasets_order(self):
        # Order matters for Auto join heuristic: Base is file1
        input_spec = MultiFileInput(
            files=[
                FileInput(file_path=self.file1, file_hash="1"),
                FileInput(file_path=self.file2, file_hash="2")
            ]
        )
        merged_df, _ = self.loader.merge_datasets(input_spec)
        # File1 (3 rows) -> File2
        # Cust 1 match
        # Cust 2 match
        # Cust 3 no match -> Amount NaN
        self.assertEqual(len(merged_df), 3)
        self.assertTrue(pd.isna(merged_df.loc[merged_df['CustomerID'] == 3, 'Amount'].values[0]))

if __name__ == '__main__':
    unittest.main()

