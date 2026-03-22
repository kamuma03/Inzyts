"""
Integration tests for File Upload API endpoints.

Tests the file upload, preview, and validation endpoints from
src/server/routes/files.py
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.server.main import fastapi_app as app


class TestFileUploadAPI:
    """Test suite for file upload API endpoints."""

    @pytest.fixture(autouse=True)
    def mock_upload_dir(self, tmp_path):
        """Mock the upload directory to use a temporary directory for tests."""
        # Patch the UPLOAD_DIR constant in the files module
        with patch('src.server.routes.files.UPLOAD_DIR', str(tmp_path)):
            yield tmp_path

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_path = tmp_path / "test_data.csv"
        csv_content = """name,age,city
Alice,25,NYC
Bob,30,LA
Charlie,35,Chicago
"""
        csv_path.write_text(csv_content)
        return csv_path

    @pytest.fixture
    def large_csv(self, tmp_path):
        """Create a large CSV file for testing."""
        csv_path = tmp_path / "large_data.csv"
        with open(csv_path, 'w') as f:
            f.write("col1,col2,col3,col4,col5\n")
            for i in range(1000):
                f.write(f"{i},{i*2},{i*3},{i*4},{i*5}\n")
        return csv_path

    # Test 1: Upload CSV file successfully
    def test_upload_csv_success(self, client, sample_csv):
        """Test successful CSV file upload."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('test_data.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        data = response.json()
        assert 'filename' in data
        assert 'saved_path' in data
        assert 'size' in data
        assert data['filename'] == 'test_data.csv'
        assert data['size'] > 0
        # Verify file exists
        assert os.path.exists(data['saved_path'])

    # Test 2: Upload file with unique naming
    def test_upload_unique_filenames(self, client, sample_csv):
        """Test that uploaded files get unique names to prevent overwrites."""
        # Upload same file twice
        with open(sample_csv, 'rb') as f:
            files = {'file': ('same_name.csv', f, 'text/csv')}
            response1 = client.post('/api/v2/files/upload', files=files)

        with open(sample_csv, 'rb') as f:
            files = {'file': ('same_name.csv', f, 'text/csv')}
            response2 = client.post('/api/v2/files/upload', files=files)

        assert response1.status_code == 200
        assert response2.status_code == 200

        path1 = response1.json()['saved_path']
        path2 = response2.json()['saved_path']

        # Paths should be different
        assert path1 != path2

    # Test 3: Upload large file
    def test_upload_large_file(self, client, large_csv):
        """Test uploading a large CSV file."""
        with open(large_csv, 'rb') as f:
            files = {'file': ('large_data.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        data = response.json()
        assert data['size'] > 10000  # Should be reasonably large

    # Test 4: Upload without file (error case)
    def test_upload_no_file(self, client):
        """Test upload endpoint without providing a file."""
        response = client.post('/api/v2/files/upload')

        assert response.status_code == 422  # Unprocessable entity

    # Test 5: Upload non-CSV file
    def test_upload_non_csv_file(self, client, tmp_path):
        """Test uploading a non-CSV file (should still work, server accepts any file)."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is not a CSV")

        with open(txt_file, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = client.post('/api/v2/files/upload', files=files)

        # Server doesn't validate file type at upload, only at processing
        assert response.status_code == 200

    # Test 6: Preview CSV file successfully
    def test_preview_csv_success(self, client, sample_csv):
        """Test CSV preview endpoint."""
        response = client.get(f'/api/v2/files/preview?path={sample_csv}')

        assert response.status_code == 200
        data = response.json()
        assert 'filename' in data
        assert 'columns' in data
        assert 'rows' in data
        assert 'total_rows' in data
        assert data['columns'] == ['name', 'age', 'city']
        assert len(data['rows']) <= 5  # Preview shows first 5 rows
        assert data['total_rows'] == 3

    # Test 7: Preview with large CSV
    def test_preview_large_csv(self, client, large_csv):
        """Test preview only returns first 5 rows even for large files."""
        response = client.get(f'/api/v2/files/preview?path={large_csv}')

        assert response.status_code == 200
        data = response.json()
        assert len(data['rows']) == 5  # Should limit to 5 rows
        assert data['total_rows'] == 1000

    # Test 8: Preview non-existent file
    # Test 8: Preview file security and Not Found
    def test_preview_security_and_not_found(self, client, mock_upload_dir):
        """Test preview endpoint for security (403) and missing files (404)."""
        # Case 1: Path traversal (outside upload dir) -> 403
        response = client.get('/api/v2/files/preview?path=/etc/passwd')
        assert response.status_code == 403
        assert 'access denied' in response.json()['detail'].lower()

        # Case 2: File in upload dir but missing -> 404
        missing_file = mock_upload_dir / "missing.csv"
        response = client.get(f'/api/v2/files/preview?path={missing_file}')
        assert response.status_code == 404
        assert 'file not found' in response.json()['detail'].lower()

    # Test 9: Preview malformed CSV
    def test_preview_malformed_csv(self, client, tmp_path):
        """Test preview with malformed CSV file."""
        malformed_csv = tmp_path / "malformed.csv"
        malformed_csv.write_text("col1,col2\nvalue1\nvalue2,value3,extra")

        response = client.get(f'/api/v2/files/preview?path={malformed_csv}')

        # Should handle gracefully, may return 200 or 400 depending on implementation
        assert response.status_code in [200, 400]

    # Test 10: Preview empty CSV
    def test_preview_empty_csv(self, client, tmp_path):
        """Test preview with empty CSV file."""
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("")

        response = client.get(f'/api/v2/files/preview?path={empty_csv}')

        # Should handle gracefully
        assert response.status_code in [200, 400]

    # Test 11: Preview CSV with special characters
    def test_preview_csv_special_characters(self, client, tmp_path):
        """Test preview with CSV containing special characters."""
        special_csv = tmp_path / "special.csv"
        special_csv.write_text('name,comment\n"Alice","Hello, world!"\n"Bob","Line1\nLine2"')

        response = client.get(f'/api/v2/files/preview?path={special_csv}')

        assert response.status_code == 200
        data = response.json()
        assert len(data['rows']) > 0

    # Test 12: Upload directory path (should create if not exists)
    def test_upload_directory_creation(self, client, sample_csv):
        """Test that upload directory is created if it doesn't exist."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('test.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        # Verify upload directory exists
        assert os.path.exists('data/uploads')

    # Test 13: Upload returns absolute path
    def test_upload_returns_absolute_path(self, client, sample_csv):
        """Test that upload endpoint returns absolute path."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('test.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        saved_path = response.json()['saved_path']
        assert os.path.isabs(saved_path)

    # Test 14: Preview returns correct column count
    def test_preview_column_count(self, client, sample_csv):
        """Test that preview returns correct number of columns."""
        response = client.get(f'/api/v2/files/preview?path={sample_csv}')

        assert response.status_code == 200
        data = response.json()
        assert len(data['columns']) == 3

    # Test 15: Preview returns row data as dictionaries
    def test_preview_row_format(self, client, sample_csv):
        """Test that preview returns rows as dictionaries."""
        response = client.get(f'/api/v2/files/preview?path={sample_csv}')

        assert response.status_code == 200
        data = response.json()
        assert len(data['rows']) > 0
        assert isinstance(data['rows'][0], dict)
        assert 'name' in data['rows'][0]

    # Test 16: Upload file with spaces in name
    def test_upload_filename_with_spaces(self, client, tmp_path):
        """Test uploading file with spaces in filename."""
        spaced_file = tmp_path / "file with spaces.csv"
        spaced_file.write_text("col1,col2\nval1,val2")

        with open(spaced_file, 'rb') as f:
            files = {'file': ('file with spaces.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200

    # Test 17: File upload error handling
    @patch('src.server.routes.files.shutil.copyfileobj')
    def test_upload_file_write_error(self, mock_copy, client, sample_csv):
        """Test error handling when file write fails."""
        mock_copy.side_effect = IOError("Disk full")

        with open(sample_csv, 'rb') as f:
            files = {'file': ('test.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 500

    # Test 18: Preview CSV with missing columns
    def test_preview_csv_missing_columns(self, client, tmp_path):
        """Test preview with CSV that has inconsistent columns."""
        inconsistent_csv = tmp_path / "inconsistent.csv"
        inconsistent_csv.write_text("col1,col2,col3\nval1,val2\nval3,val4,val5")

        response = client.get(f'/api/v2/files/preview?path={inconsistent_csv}')

        # Should handle gracefully
        assert response.status_code in [200, 400]

    # Test 19: Multiple concurrent uploads
    def test_concurrent_uploads(self, client, sample_csv):
        """Test multiple simultaneous file uploads."""
        responses = []
        for i in range(5):
            with open(sample_csv, 'rb') as f:
                files = {'file': (f'test_{i}.csv', f, 'text/csv')}
                response = client.post('/api/v2/files/upload', files=files)
                responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        # All should have different paths
        paths = [r.json()['saved_path'] for r in responses]
        assert len(paths) == len(set(paths))

    # Test 20: Upload preserves file extension
    def test_upload_preserves_extension(self, client, sample_csv):
        """Test that uploaded file preserves original extension."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('data.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        saved_path = response.json()['saved_path']
        assert saved_path.endswith('.csv')

    # Test 21: Preview query parameter validation
    def test_preview_missing_path_parameter(self, client):
        """Test preview endpoint without path parameter."""
        response = client.get('/api/v2/files/preview')

        assert response.status_code == 422  # Missing required parameter

    # Test 22: Upload file size reporting
    def test_upload_reports_file_size(self, client, sample_csv):
        """Test that upload endpoint reports correct file size."""
        actual_size = os.path.getsize(sample_csv)

        with open(sample_csv, 'rb') as f:
            files = {'file': ('test.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        reported_size = response.json()['size']
        assert reported_size == actual_size

    # Test 23: Preview total row count accuracy
    def test_preview_total_rows_accuracy(self, client, tmp_path):
        """Test that preview accurately counts total rows."""
        csv_file = tmp_path / "counted.csv"
        with open(csv_file, 'w') as f:
            f.write("col1,col2\n")
            for i in range(100):
                f.write(f"{i},{i*2}\n")

        response = client.get(f'/api/v2/files/preview?path={csv_file}')

        assert response.status_code == 200
        assert response.json()['total_rows'] == 100

    # Test 24: Upload binary file handling
    def test_upload_binary_file(self, client, tmp_path):
        """Test uploading binary file (edge case)."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03\x04')

        with open(binary_file, 'rb') as f:
            files = {'file': ('binary.bin', f, 'application/octet-stream')}
            response = client.post('/api/v2/files/upload', files=files)

        # Should accept any file type
        assert response.status_code == 200

    # Test 25: Preview filename extraction
    def test_preview_extracts_filename(self, client, sample_csv):
        """Test that preview correctly extracts filename from path."""
        response = client.get(f'/api/v2/files/preview?path={sample_csv}')

        assert response.status_code == 200
        data = response.json()
        assert data['filename'] == os.path.basename(str(sample_csv))

    # Test 26: Cleanup - file upload creates persistent files
    def test_upload_file_persistence(self, client, sample_csv):
        """Test that uploaded files persist after request."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('persistent.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        saved_path = response.json()['saved_path']

        # File should still exist after request
        assert os.path.exists(saved_path)

        # Cleanup
        os.remove(saved_path)

    # Test 27: Upload empty file
    def test_upload_empty_file(self, client, tmp_path):
        """Test uploading an empty file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        with open(empty_file, 'rb') as f:
            files = {'file': ('empty.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        assert response.json()['size'] == 0

    # Test 28: Preview CSV with Unicode characters
    def test_preview_unicode_csv(self, client, tmp_path):
        """Test preview with CSV containing Unicode characters."""
        unicode_csv = tmp_path / "unicode.csv"
        unicode_csv.write_text("name,city\nAlice,Tokyo 東京\nBob,München", encoding='utf-8')

        response = client.get(f'/api/v2/files/preview?path={unicode_csv}')

        assert response.status_code == 200
        data = response.json()
        # Should handle Unicode properly
        assert any('Tokyo' in str(row) or '東京' in str(row) for row in data['rows'])

    # Test 29: Upload returns original filename
    def test_upload_returns_original_filename(self, client, sample_csv):
        """Test that response includes original filename."""
        original_name = "my_dataset.csv"
        with open(sample_csv, 'rb') as f:
            files = {'file': (original_name, f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        assert response.json()['filename'] == original_name

    # Test 30: API response schema validation
    def test_upload_response_schema(self, client, sample_csv):
        """Test that upload response matches expected schema."""
        with open(sample_csv, 'rb') as f:
            files = {'file': ('test.csv', f, 'text/csv')}
            response = client.post('/api/v2/files/upload', files=files)

        assert response.status_code == 200
        data = response.json()
        required_fields = ['filename', 'saved_path', 'size']
        for field in required_fields:
            assert field in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
