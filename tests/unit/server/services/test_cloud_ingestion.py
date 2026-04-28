import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from src.server.services.cloud_ingestion import (
    validate_cloud_uri,
    ingest_from_cloud,
    _convert_to_csv,
    _download_from_azure,
)


# --- validate_cloud_uri ---

def test_validate_cloud_uri_allows_s3():
    validate_cloud_uri("s3://my-bucket/path/to/file.csv")


def test_validate_cloud_uri_allows_gs():
    validate_cloud_uri("gs://my-bucket/data.parquet")


def test_validate_cloud_uri_allows_azure():
    validate_cloud_uri("az://container/blob.csv")
    validate_cloud_uri("abfs://container/blob.csv")
    validate_cloud_uri("abfss://container/blob.csv")


def test_validate_cloud_uri_rejects_http():
    with pytest.raises(ValueError, match="not allowed"):
        validate_cloud_uri("http://example.com/data.csv")


def test_validate_cloud_uri_rejects_ftp():
    with pytest.raises(ValueError, match="not allowed"):
        validate_cloud_uri("ftp://example.com/data.csv")


def test_validate_cloud_uri_rejects_file():
    with pytest.raises(ValueError, match="not allowed"):
        validate_cloud_uri("file:///etc/passwd")


# --- _convert_to_csv ---

def test_convert_csv_passthrough(tmp_path):
    csv_file = str(tmp_path / "data.csv")
    with open(csv_file, "w") as f:
        f.write("a,b\n1,2\n")
    result = _convert_to_csv(csv_file)
    assert result == csv_file


def test_convert_json_to_csv(tmp_path):
    import json
    json_file = str(tmp_path / "data.json")
    with open(json_file, "w") as f:
        json.dump([{"a": 1, "b": 2}], f)
    result = _convert_to_csv(json_file)
    assert result.endswith(".csv")
    assert not os.path.exists(json_file)  # original removed


def test_convert_excel_to_csv(tmp_path):
    import pandas as pd
    xlsx_file = str(tmp_path / "data.xlsx")
    pd.DataFrame({"col1": [1], "col2": [2]}).to_excel(xlsx_file, index=False)
    result = _convert_to_csv(xlsx_file)
    assert result.endswith(".csv")
    assert not os.path.exists(xlsx_file)


def test_convert_unknown_extension_passthrough(tmp_path):
    txt_file = str(tmp_path / "data.txt")
    with open(txt_file, "w") as f:
        f.write("hello")
    result = _convert_to_csv(txt_file)
    assert result == txt_file


# --- _download_from_s3 ---
# boto3 is imported lazily inside _download_from_s3, so we inject a mock via sys.modules.

def test_download_from_s3_success(tmp_path):
    from src.server.services.cloud_ingestion import _download_from_s3

    output = str(tmp_path / "file.csv")
    mock_boto3 = MagicMock()
    mock_client = mock_boto3.client.return_value
    mock_client.head_object.return_value = {"ContentLength": 1024}

    with patch.dict(sys.modules, {"boto3": mock_boto3}):
        _download_from_s3("s3://bucket/key.csv", output)

    mock_client.download_file.assert_called_once_with("bucket", "key.csv", output)


def test_download_from_s3_too_large(tmp_path):
    from src.server.services.cloud_ingestion import _download_from_s3

    output = str(tmp_path / "file.csv")
    mock_boto3 = MagicMock()
    mock_client = mock_boto3.client.return_value
    mock_client.head_object.return_value = {"ContentLength": 600 * 1024 * 1024}

    with patch.dict(sys.modules, {"boto3": mock_boto3}):
        with pytest.raises(ValueError, match="exceeds limit"):
            _download_from_s3("s3://bucket/big.csv", output)


# --- _download_from_gcs ---
# google.cloud.storage is imported lazily; inject mock.

def test_download_from_gcs_success(tmp_path):
    from src.server.services.cloud_ingestion import _download_from_gcs

    output = str(tmp_path / "file.csv")
    mock_storage_module = MagicMock()
    mock_blob = MagicMock()
    mock_blob.size = 1024  # int, not MagicMock
    mock_storage_module.Client.return_value.bucket.return_value.blob.return_value = mock_blob

    # Build nested module mocks so `from google.cloud import storage` works
    mock_google = MagicMock()
    mock_google_cloud = MagicMock()
    mock_google_cloud.storage = mock_storage_module
    mock_google.cloud = mock_google_cloud

    with patch.dict(sys.modules, {
        "google": mock_google,
        "google.cloud": mock_google_cloud,
        "google.cloud.storage": mock_storage_module,
    }):
        _download_from_gcs("gs://bucket/path.csv", output)

    mock_blob.download_to_filename.assert_called_once_with(output)


# --- _download_from_azure ---

def test_download_from_azure_missing_conn_string(tmp_path):
    output = str(tmp_path / "file.csv")
    mock_azure = MagicMock()
    with patch.dict(sys.modules, {
        "azure": MagicMock(),
        "azure.storage": MagicMock(),
        "azure.storage.blob": mock_azure,
    }):
        # Ensure the env var is not set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZURE_STORAGE_CONNECTION_STRING", None)
            with pytest.raises(ValueError, match="AZURE_STORAGE_CONNECTION_STRING"):
                _download_from_azure("az://container/blob.csv", output)


# --- ingest_from_cloud ---

def test_ingest_from_cloud_s3(tmp_path):
    with patch("src.server.services.cloud_ingestion._download_from_s3") as mock_dl, \
         patch("src.server.services.cloud_ingestion._convert_to_csv") as mock_convert:
        mock_convert.return_value = str(tmp_path / "output.csv")
        result = ingest_from_cloud("s3://bucket/data.csv", str(tmp_path))
        mock_dl.assert_called_once()
        assert result == str(tmp_path / "output.csv")


def test_ingest_from_cloud_gs(tmp_path):
    with patch("src.server.services.cloud_ingestion._download_from_gcs") as mock_dl, \
         patch("src.server.services.cloud_ingestion._convert_to_csv") as mock_convert:
        mock_convert.return_value = str(tmp_path / "output.csv")
        result = ingest_from_cloud("gs://bucket/data.parquet", str(tmp_path))
        mock_dl.assert_called_once()
        assert result == str(tmp_path / "output.csv")


def test_ingest_from_cloud_azure(tmp_path):
    with patch("src.server.services.cloud_ingestion._download_from_azure") as mock_dl, \
         patch("src.server.services.cloud_ingestion._convert_to_csv") as mock_convert:
        mock_convert.return_value = str(tmp_path / "output.csv")
        result = ingest_from_cloud("az://container/data.csv", str(tmp_path))
        mock_dl.assert_called_once()
        assert result == str(tmp_path / "output.csv")


def test_ingest_from_cloud_rejects_invalid_scheme():
    with pytest.raises(ValueError, match="not allowed"):
        ingest_from_cloud("http://example.com/data.csv")
