import unittest
from unittest.mock import patch, MagicMock

# Mock logger before importing anything that uses it
logger_patcher = patch('src.utils.logger.get_logger')
mock_logger = logger_patcher.start()
mock_logger.return_value = MagicMock()

from fastapi.testclient import TestClient
from src.server.main import app
from src.models.templates import DomainTemplate

class TestTemplateRoutes(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        logger_patcher.stop()

    def setUp(self):
        # Use fastapi_app instead of the Socket.IO wrapper
        from src.server.main import fastapi_app
        from src.server.middleware.auth import verify_token
        
        # Override authentication
        fastapi_app.dependency_overrides[verify_token] = lambda: "test-token"
        
        self.client = TestClient(fastapi_app)
        
        # Patch TemplateManager used by the route dependency
        self.patcher = patch('src.server.routes.templates.TemplateManager')
        self.MockManager = self.patcher.start()
        self.mock_manager_instance = self.MockManager.return_value
        
        # Setup default mocks
        self.mock_template = DomainTemplate(
            domain_name="TestDomain",
            description="Test Description",
            concepts=[],
            recommended_analyses=[]
        )

    def tearDown(self):
        self.patcher.stop()

    def test_list_templates(self):
        self.mock_manager_instance.get_all_templates.return_value = [self.mock_template]
        
        response = self.client.get("/api/v2/templates")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["domain_name"], "TestDomain")

    def test_upload_template(self):
        self.mock_manager_instance.save_template.return_value = True
        
        template_json = self.mock_template.model_dump_json()
        files = {'file': ('test.json', template_json, 'application/json')}
        
        response = self.client.post("/api/v2/templates", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertIn("saved successfully", response.json()["message"])

    def test_upload_invalid_json(self):
        files = {'file': ('test.json', "invalid json", 'application/json')}
        response = self.client.post("/api/v2/templates", files=files)
        self.assertEqual(response.status_code, 400)

    def test_delete_template(self):
        self.mock_manager_instance.delete_template.return_value = True
        
        response = self.client.delete("/api/v2/templates/TestDomain")
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["message"])

    def test_delete_missing_template(self):
        self.mock_manager_instance.delete_template.return_value = False
        
        response = self.client.delete("/api/v2/templates/Unknown")
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
