import unittest
import os
import shutil
import tempfile
import pandas as pd
from unittest.mock import MagicMock, patch

# Mock logger before imports
logger_patcher = patch('src.utils.logger.get_logger')
mock_logger = logger_patcher.start()
mock_logger.return_value = MagicMock()

from src.agents.phase1.data_profiler import DataProfilerAgent
from src.models.handoffs import OrchestratorToProfilerHandoff, UserIntent
from src.models.multi_file import MultiFileInput, FileInput
from src.models.state import AnalysisState


class TestProfilerMultiFile(unittest.TestCase):
    def setUp(self):
        # Disable cache for all tests to prevent permission errors
        self.cache_save_patcher = patch('src.utils.cache_manager.CacheManager.save_artifact', return_value=None)
        self.cache_save_patcher.start()
        self.cache_load_patcher = patch('src.utils.cache_manager.CacheManager.load_artifact', return_value=None)
        self.cache_load_patcher.start()
        self.cache_hash_patcher = patch('src.utils.cache_manager.CacheManager.get_csv_hash', return_value='test_hash')
        self.cache_hash_patcher.start()
        
        self.test_dir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.test_dir, "customers.csv")
        self.file2 = os.path.join(self.test_dir, "orders.csv")
        
        # Create CSVs
        # Use Healthcare columns to trigger domain detection (PatientID, Diagnosis)
        pd.DataFrame({"PatientID": [1, 2], "Name": ["A", "B"]}).to_csv(self.file1, index=False)
        pd.DataFrame({"VisitID": [10, 20], "PatientID": [1, 2], "Diagnosis": ["Flu", "Cold"]}).to_csv(self.file2, index=False)
        
        # Mock LLM to avoid actual calls
        self.agent = DataProfilerAgent()
        self.agent.llm_agent = MagicMock()
        self.agent.llm_agent.invoke_with_json.return_value = "invalid json" # Trigger heuristic fallback

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        logger_patcher.stop()
        self.cache_save_patcher.stop()
        self.cache_load_patcher.stop()
        self.cache_hash_patcher.stop()

    def test_profiler_merges_files(self):
        # Setup handoff with multi-file input
        multi_input = MultiFileInput(
            files=[
                FileInput(file_path=self.file1, file_hash="1"),
                FileInput(file_path=self.file2, file_hash="2")
            ]
        )
        
        user_intent = UserIntent(
            csv_path=self.file1, # Primary "entry" point
            multi_file_input=multi_input
        )
        
        handoff = OrchestratorToProfilerHandoff(
            csv_path=self.file1,
            row_count=0,
            column_names=[],
            user_intent=user_intent,
            multi_file_input=multi_input
        )
        
        # State pointing to primary file initially
        state = AnalysisState(csv_path=self.file1)
        
        # Run agent
        result = self.agent.process(state, handoff=handoff)
        
        # Verify handoff has merged dataset info
        out_handoff = result["handoff"]
        # "Name" from file1, "Diagnosis" from file2
        column_names = [c.name for c in out_handoff.columns]
        self.assertIn("Name", column_names) 
        self.assertIn("Diagnosis", column_names)
        
        self.assertIsNotNone(out_handoff.detected_domain) # It runs domain detection
        
        # Check if merged file was created on disk
        # We can't know the exact path easily without mocking os.path or checking the log, 
        # but we know it should be in the same dir as input
        files = os.listdir(self.test_dir)
        merged_files = [f for f in files if f.startswith("merged_")]
        self.assertTrue(len(merged_files) > 0)

if __name__ == '__main__':
    unittest.main()
