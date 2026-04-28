
import unittest
import pandas as pd
import tempfile
import os
import shutil
from src.services.join_detector import JoinDetector
from src.models.multi_file import FileInput

class TestJoinDetector(unittest.TestCase):
    def setUp(self):
        self.join_detector = JoinDetector()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_detect_candidates_simple(self):
        # Create two dataframes with a common column "user_id"
        df1 = pd.DataFrame({'user_id': [1, 2, 3], 'name': ['Alice', 'Bob', 'Charlie']})
        df2 = pd.DataFrame({'user_id': [1, 2, 4], 'email': ['a@a.com', 'b@b.com', 'd@d.com']})
        
        input1 = FileInput(file_path="f1.csv", file_hash="h1", description="Users")
        input2 = FileInput(file_path="f2.csv", file_hash="h2", description="Emails")
        
        dfs = {"h1": df1, "h2": df2}
        inputs = [input1, input2]
        
        candidates = self.join_detector.detect_join_candidates(inputs, dfs)
        
        self.assertTrue(len(candidates) > 0)
        # Check if "user_id" is detected
        match = next((c for c in candidates if c.left_column == "user_id" and c.right_column == "user_id"), None)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(match.confidence_score, 0.5)

    def test_execute_joins(self):
        df1 = pd.DataFrame({'id': [1, 2], 'val1': ['A', 'B']})
        df2 = pd.DataFrame({'id': [1, 2], 'val2': ['X', 'Y']})
        
        inputs = [
            FileInput(file_path="f1.csv", file_hash="h1"),
            FileInput(file_path="f2.csv", file_hash="h2")
        ]
        dfs = {"h1": df1, "h2": df2}
        candidates = self.join_detector.detect_join_candidates(inputs, dfs)
        
        output_path = os.path.join(self.test_dir, "merged.csv")
        merged_ds = self.join_detector.execute_joins(dfs, candidates, output_path, files=inputs)
        
        self.assertEqual(len(merged_ds.join_plan_executed), 1)
        
        # Verify merged file content
        merged_df = pd.read_csv(output_path)
        self.assertEqual(len(merged_df), 2)
        self.assertIn('val1', merged_df.columns)
        self.assertIn('val2', merged_df.columns)

    def test_no_common_columns(self):
        df1 = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        df2 = pd.DataFrame({'c': [10, 20], 'd': [30, 40]}) # Disjoint values
        
        inputs = [FileInput(file_path="f1.csv", file_hash="h1"), FileInput(file_path="f2.csv", file_hash="h2")]
        dfs = {"h1": df1, "h2": df2}
        
        candidates = self.join_detector.detect_join_candidates(inputs, dfs)
        # Should be empty or very low confidence
        high_conf = [c for c in candidates if c.confidence_score > 0.5]
        self.assertEqual(len(high_conf), 0)

    def test_type_mismatch(self):
        # ID as int vs ID as string
        df1 = pd.DataFrame({'id': [1, 2, 3]})
        df2 = pd.DataFrame({'id': ['1', '2', '3']})
        
        inputs = [FileInput(file_path="f1.csv", file_hash="h1"), FileInput(file_path="f2.csv", file_hash="h2")]
        dfs = {"h1": df1, "h2": df2}
        
        candidates = self.join_detector.detect_join_candidates(inputs, dfs)
        
        # Should be filtered out by type compatibility check (< 0.5)
        # Assuming current logic doesn't support implicit casting int->str
        match = next((c for c in candidates if c.left_column == "id" and c.right_column == "id"), None)
        self.assertIsNone(match)

    def test_chain_join(self):
        # A(id) -> B(id, ref) -> C(ref)
        df1 = pd.DataFrame({'id': [1, 2], 'name': ['A', 'B']})
        df2 = pd.DataFrame({'id': [1, 2], 'ref': [100, 200], 'middle': ['M1', 'M2']})
        df3 = pd.DataFrame({'ref': [100, 200], 'end': ['Z1', 'Z2']})
        
        inputs = [
            FileInput(file_path="f1.csv", file_hash="h1", alias="file1"), 
            FileInput(file_path="f2.csv", file_hash="h2", alias="file2"),
            FileInput(file_path="f3.csv", file_hash="h3", alias="file3")
        ]
        dfs = {"h1": df1, "h2": df2, "h3": df3}
        
        candidates = self.join_detector.detect_join_candidates(inputs, dfs)
        # Should find (f1.id, f2.id) and (f2.ref, f3.ref)
        
        # Manually construct a plan to ensure order for execution test logic 
        # (Though detector should find them)
        output_path = os.path.join(self.test_dir, "merged.csv")
        merged_ds = self.join_detector.execute_joins(dfs, candidates, output_path, files=inputs)
        
        # Should have joined all 3
        # Since logic joins transitively if candidates exist
        # f1+f2 -> merged
        # merged + f3 -> merged
        merged_df = pd.read_csv(output_path)
        
        self.assertEqual(len(merged_df), 2)
        print(merged_df.columns)
        # Check columns from all 3 exist
        self.assertTrue(any('name' in c for c in merged_df.columns))
        self.assertTrue(any('middle' in c for c in merged_df.columns))
        self.assertTrue(any('end' in c for c in merged_df.columns))

if __name__ == '__main__':
    unittest.main()
