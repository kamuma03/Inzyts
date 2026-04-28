
import unittest
from unittest.mock import patch, MagicMock

class TestTemplateManager(unittest.TestCase):
    def setUp(self):
        # Mock logger to avoid PermissionError
        self.logger_patcher = patch('src.utils.logger.get_logger')
        self.mock_logger = self.logger_patcher.start()
        self.mock_logger.return_value = MagicMock()
        
        # Import inside setUp to ensure patch works if it was imported at module level in other tests
        from src.services.template_manager import TemplateManager
        # Use the real template directory since we created built-in templates
        self.manager = TemplateManager()

    def tearDown(self):
        self.logger_patcher.stop()

    def test_load_templates(self):
        """Test that built-in templates are loaded."""
        self.assertGreater(len(self.manager.templates), 0)
        domains = [t.domain_name for t in self.manager.templates]
        self.assertIn("Healthcare", domains)
        self.assertIn("Finance", domains)
        self.assertIn("Retail", domains)

    def test_detect_healthcare(self):
        """Test detection of Healthcare domain."""
        columns = ["Patient ID", "Assessment Date", "Diagnosis Code", "Age", "Gender"]
        domain = self.manager.detect_domain(columns)
        self.assertIsNotNone(domain)
        self.assertEqual(domain.domain_name, "Healthcare")

    def test_detect_retail(self):
        """Test detection of Retail domain."""
        columns = ["Transaction_ID", "Customer_ID", "Sales_Amount", "Product_SKU", "Date"]
        domain = self.manager.detect_domain(columns)
        self.assertIsNotNone(domain)
        self.assertEqual(domain.domain_name, "Retail")
        
    def test_detect_finance(self):
        """Test detection of Finance domain."""
        columns = ["Account_No", "Trans_Amt", "Fraud_Label", "Date"]
        domain = self.manager.detect_domain(columns)
        self.assertIsNotNone(domain)
        self.assertEqual(domain.domain_name, "Finance")

    def test_detect_none(self):
        """Test that ambiguous/unrelated columns return None."""
        columns = ["Col1", "Col2", "X", "Y", "Value"]
        domain = self.manager.detect_domain(columns)
        self.assertIsNone(domain)

if __name__ == '__main__':
    unittest.main()
