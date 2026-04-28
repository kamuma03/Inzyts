import unittest
import os
import tempfile
import json
import pandas as pd
from unittest.mock import MagicMock, patch

# Mock logger before imports
logger_patcher = patch('src.utils.logger.get_logger')
mock_logger = logger_patcher.start()
mock_logger.return_value = MagicMock()

from src.services.dictionary_manager import DictionaryParser

class TestDictionaryManager(unittest.TestCase):
    def setUp(self):
        # Create temporary files
        self.test_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.test_dir, "dict.csv")
        self.json_path = os.path.join(self.test_dir, "dict.json")
        self.txt_path = os.path.join(self.test_dir, "dict.txt")
        self.bad_path = os.path.join(self.test_dir, "dict.xyz")
        
        # Create CSV
        df = pd.DataFrame([
            {"column": "age", "description": "Patient age", "type": "int"},
            {"column": "income", "description": "Annual income", "constraints": "min=0"}
        ])
        df.to_csv(self.csv_path, index=False)
        
        # Create JSON
        data = [
            {"column_name": "id", "description": "Unique identifier", "type": "string"},
            {"column_name": "status", "description": "Current status"}
        ]
        with open(self.json_path, 'w') as f:
            json.dump(data, f)
        
        # Create TXT (tab-separated format)
        with open(self.txt_path, 'w') as f:
            f.write("# Data Dictionary\n")
            f.write("customer_id\tUnique customer identifier\n")
            f.write("purchase_date: Date of purchase\n")
            f.write("amount = Transaction amount in USD\n")
            
        # Create unsupported format file
        with open(self.bad_path, 'w') as f:
            f.write("invalid")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_parse_csv(self):
        d = DictionaryParser.parse(self.csv_path)
        self.assertIsNotNone(d)
        self.assertEqual(len(d.entries), 2)
        
        entry = d.get_entry("age")
        self.assertEqual(entry.description, "Patient age")
        self.assertEqual(entry.data_type, "int")
        
    def test_parse_json(self):
        d = DictionaryParser.parse(self.json_path)
        self.assertIsNotNone(d)
        self.assertEqual(len(d.entries), 2)
        
        entry = d.get_entry("id")
        self.assertEqual(entry.description, "Unique identifier")
    
    def test_parse_txt(self):
        """Test parsing tab-separated, colon-separated, and equals-separated txt files."""
        d = DictionaryParser.parse(self.txt_path)
        self.assertIsNotNone(d)
        self.assertEqual(len(d.entries), 3)
        
        # Tab-separated entry
        entry1 = d.get_entry("customer_id")
        self.assertIsNotNone(entry1)
        self.assertEqual(entry1.description, "Unique customer identifier")
        
        # Colon-separated entry
        entry2 = d.get_entry("purchase_date")
        self.assertIsNotNone(entry2)
        self.assertEqual(entry2.description, "Date of purchase")
        
        # Equals-separated entry
        entry3 = d.get_entry("amount")
        self.assertIsNotNone(entry3)
        self.assertEqual(entry3.description, "Transaction amount in USD")
        
    def test_parse_invalid(self):
        d = DictionaryParser.parse(self.bad_path)
        self.assertIsNone(d)
        
    def test_missing_file(self):
        d = DictionaryParser.parse("non_existent.csv")
        self.assertIsNone(d)

if __name__ == '__main__':
    unittest.main()

