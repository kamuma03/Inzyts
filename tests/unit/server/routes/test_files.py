import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import verify_token
from src.server.db.models import User, UserRole


def _fake_analyst():
    """Upload routes now require Analyst+ — give the fake user that role."""
    return User(
        id="test-user-id",
        username="testuser",
        is_active=True,
        role=UserRole.ANALYST,
    )


# Override auth
@pytest.fixture(autouse=True)
def apply_dependency_overrides():
    fastapi_app.dependency_overrides[verify_token] = _fake_analyst
    yield
    fastapi_app.dependency_overrides.clear()

client = TestClient(fastapi_app)

def test_upload_file_empty():
    """Test rejection of empty files."""
    response = client.post(
        "/api/v2/files/upload",
        files={"file": ("test.csv", b"")}
    )
    assert response.status_code == 400
    assert "Empty files" in response.json()["detail"]

def test_upload_file_success(tmp_path):
    """Test successful upload of a CSV file."""
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = client.post(
            "/api/v2/files/upload",
            files={"file": ("test.csv", b"A,B,C\n1,2,3")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.csv"
        assert "saved_path" in data
        assert data["size"] > 0
        
        # File should exist on disk
        saved_file = tmp_path / data["saved_path"]
        assert saved_file.exists()
        assert saved_file.read_bytes() == b"A,B,C\n1,2,3"

def test_upload_invalid_mime_type(tmp_path):
    """Test rejection of invalid file types based on magic numbers."""
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        # Fake PK zip header to trigger non-csv mime detection
        invalid_data = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" * 300 
        response = client.post(
            "/api/v2/files/upload",
            files={"file": ("test.zip", invalid_data)}
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

def test_upload_file_exception_handling():
    """Test standard exception handling during upload."""
    with patch("src.server.routes.files.shutil.copyfileobj", side_effect=Exception("Disk full")):
        response = client.post(
            "/api/v2/files/upload",
            files={"file": ("test.csv", b"A,B\n1,2")}
        )
        
        # In files.py, all unexpected exceptions yield 500
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

def test_upload_batch_success(tmp_path):
    """Test successful batch upload."""
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = client.post(
            "/api/v2/files/upload_batch",
            files=[
                ("files", ("test1.csv", b"A,B\n1,2")),
                ("files", ("test2.csv", b"C,D\n3,4"))
            ]
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["filename"] == "test1.csv"
        assert data[1]["filename"] == "test2.csv"

def test_upload_batch_invalid_mime(tmp_path):
    """Test batch upload with one invalid file."""
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        invalid_data = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" * 300 
        response = client.post(
            "/api/v2/files/upload_batch",
            files=[
                ("files", ("test1.csv", b"A,B\n1,2")),
                ("files", ("test_bad.zip", invalid_data))
            ]
        )
        assert response.status_code == 400

def test_preview_file_not_found(tmp_path):
    response = client.get("/api/v2/files/preview", params={"path": "does_not_exist.csv"})
    assert response.status_code == 404

def test_preview_file_path_traversal(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        # Create a file outside the upload dir so it passes the os.path.exists check
        outside_file = tmp_path.parent / "secret.txt"
        outside_file.write_text("secret")
        
        response = client.get("/api/v2/files/preview", params={"path": str(outside_file)})
        assert response.status_code == 403

def test_preview_file_csv_success(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        test_file = tmp_path / "preview.csv"
        test_file.write_text("col1,col2\nval1,val2\nval3,val4")
        
        response = client.get("/api/v2/files/preview", params={"path": str(test_file)})
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "preview.csv"
        assert data["columns"] == ["col1", "col2"]
        assert len(data["rows"]) == 2
        assert data["total_rows"] == 2

def test_preview_file_invalid_extension(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("col1\nval1") # Just becomes a 1-column CSV
        response = client.get("/api/v2/files/preview", params={"path": str(invalid_file)})
        assert response.status_code == 200

def test_upload_batch_empty_file(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = client.post(
            "/api/v2/files/upload_batch",
            files=[
                ("files", ("test_empty.csv", b""))
            ]
        )
        assert response.status_code == 400
        assert "Empty file not allowed" in response.json()["detail"]

def test_upload_batch_exception_handling():
    with patch("src.server.routes.files.shutil.copyfileobj", side_effect=Exception("Disk full")):
        response = client.post(
            "/api/v2/files/upload_batch",
            files=[
                ("files", ("test.csv", b"A,B\n1,2"))
            ]
        )
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

def test_upload_file_parquet_octet_stream_fallback(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        with patch("src.server.routes.files.magic.Magic") as mock_magic:
            instance = mock_magic.return_value
            instance.from_buffer.return_value = "application/octet-stream"
            
            response = client.post(
                "/api/v2/files/upload",
                files={"file": ("test.parquet", b"PAR1...fake_data")}
            )
            assert response.status_code == 200

def test_upload_batch_parquet_octet_stream_fallback(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        with patch("src.server.routes.files.magic.Magic") as mock_magic:
            instance = mock_magic.return_value
            instance.from_buffer.return_value = "application/octet-stream"
            
            response = client.post(
                "/api/v2/files/upload_batch",
                files=[("files", ("test.parquet", b"PAR1...fake_data"))]
            )
            assert response.status_code == 200

def test_preview_file_parquet_success(tmp_path):
    import pandas as pd
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        test_file = tmp_path / "test.parquet"
        df = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})
        df.to_parquet(test_file)
        
        response = client.get("/api/v2/files/preview", params={"path": str(test_file)})
        assert response.status_code == 200
        assert response.json()["total_rows"] == 2
        
def test_preview_file_log_success(tmp_path):
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        test_file = tmp_path / "test.log"
        test_file.write_bytes(b"Line 1\nLine 2\n")

        response = client.get("/api/v2/files/preview", params={"path": str(test_file)})
        assert response.status_code == 200
        assert response.json()["total_rows"] == 1 # 1 line after subtracting "header"


# --- Excel upload and preview ---

def test_upload_file_xlsx(tmp_path):
    """Test that .xlsx files are accepted (MIME in ALLOWED_MIMES)."""
    import pandas as pd
    import io
    buf = io.BytesIO()
    pd.DataFrame({"A": [1], "B": [2]}).to_excel(buf, index=False)
    buf.seek(0)

    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        response = client.post(
            "/api/v2/files/upload",
            files={"file": ("test.xlsx", buf.getvalue())}
        )
        assert response.status_code == 200
        assert response.json()["filename"] == "test.xlsx"


def test_preview_file_xlsx(tmp_path):
    import pandas as pd
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        test_file = tmp_path / "test.xlsx"
        pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]}).to_excel(test_file, index=False)

        response = client.get("/api/v2/files/preview", params={"path": str(test_file)})
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == ["col1", "col2"]
        assert data["total_rows"] == 3


def test_preview_file_json(tmp_path):
    import json
    with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps([{"x": 1, "y": 2}, {"x": 3, "y": 4}]))

        response = client.get("/api/v2/files/preview", params={"path": str(test_file)})
        assert response.status_code == 200
        data = response.json()
        assert "x" in data["columns"]
        assert data["total_rows"] == 2


# --- DB test endpoint ---

def test_db_test_invalid_scheme():
    response = client.post("/api/v2/files/db-test", json={"db_uri": "sqlite:///test.db"})
    # Pydantic @field_validator raises 422 Unprocessable Entity
    assert response.status_code == 422


def test_db_test_success():
    with patch("sqlalchemy.create_engine") as mock_engine, \
         patch("sqlalchemy.inspect") as mock_inspect:
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_inspect.return_value.get_table_names.return_value = ["users", "orders"]

        response = client.post("/api/v2/files/db-test", json={"db_uri": "postgresql://user:pass@host/db"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["dialect"] == "postgresql"
        assert "users" in data["tables"]


def test_db_test_connection_failure():
    with patch("sqlalchemy.create_engine") as mock_engine:
        mock_engine.return_value.connect.side_effect = Exception("Connection refused")

        response = client.post("/api/v2/files/db-test", json={"db_uri": "postgresql://user:pass@badhost/db"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Connection failed" in data["error"]


# --- SQL preview endpoint ---

def test_sql_preview_rejects_insert():
    response = client.post("/api/v2/files/sql-preview", json={
        "db_uri": "postgresql://user:pass@host/db",
        "query": "INSERT INTO t VALUES (1)"
    })
    assert response.status_code == 400


def test_sql_preview_rejects_invalid_scheme():
    response = client.post("/api/v2/files/sql-preview", json={
        "db_uri": "sqlite:///test.db",
        "query": "SELECT 1"
    })
    # Pydantic @field_validator raises 422 Unprocessable Entity
    assert response.status_code == 422


# --- API preview endpoint ---

def test_api_preview_success():
    """The route uses ``_safe_get(session, url, ...)`` (per H-1 SSRF fix)
    so we mock the helper directly rather than ``requests.get``."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent._safe_get", return_value=mock_resp), \
         patch("src.agents.api_agent._is_private_ip", return_value=False):
        response = client.post("/api/v2/files/api-preview", json={
            "api_url": "https://api.example.com/users"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "api_preview"
        assert "id" in data["columns"]


def test_api_preview_private_ip():
    with patch("src.agents.api_agent._is_private_ip", return_value=True):
        response = client.post("/api/v2/files/api-preview", json={
            "api_url": "http://10.0.0.1/api"
        })
        assert response.status_code == 400
        assert "private" in response.json()["detail"].lower()


def test_api_preview_timeout():
    """Timeout from ``_safe_get`` should surface as a 400 with the timeout
    message preserved (not swallowed)."""
    import requests as req_lib
    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent._safe_get",
               side_effect=req_lib.exceptions.Timeout):
        response = client.post("/api/v2/files/api-preview", json={
            "api_url": "https://api.example.com/slow"
        })
        assert response.status_code == 400
        assert "timed out" in response.json()["detail"].lower()
