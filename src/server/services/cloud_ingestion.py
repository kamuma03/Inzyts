"""
Cloud storage ingestion service.

Downloads files from S3, GCS, or Azure Blob Storage and converts them to CSV
for use in the analysis pipeline. Follows the same pattern as data_ingestion.py.

Credentials are resolved from the environment (AWS_ACCESS_KEY_ID,
GOOGLE_APPLICATION_CREDENTIALS, AZURE_STORAGE_CONNECTION_STRING) — never from
request bodies.
"""

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from src.config import settings
from src.utils.db_utils import validate_cloud_uri
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

logger = get_logger()

# Maximum file size to download.
_MAX_DOWNLOAD_MB = settings.cloud_max_download_mb


def _download_from_s3(uri: str, output_path: str) -> None:
    """Download a file from S3."""
    import boto3

    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    s3 = boto3.client("s3")

    # Check file size before downloading
    head = s3.head_object(Bucket=bucket, Key=key)
    size_mb = head["ContentLength"] / (1024 * 1024)
    if size_mb > _MAX_DOWNLOAD_MB:
        raise ValueError(
            f"File is {size_mb:.1f} MB, exceeds limit of {_MAX_DOWNLOAD_MB} MB."
        )

    logger.info(f"Downloading s3://{bucket}/{key} ({size_mb:.1f} MB)")
    s3.download_file(bucket, key, output_path)


def _download_from_gcs(uri: str, output_path: str) -> None:
    """Download a file from Google Cloud Storage."""
    from google.cloud import storage as gcs_storage

    parsed = urlparse(uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip("/")

    client = gcs_storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Check size
    blob.reload()
    size_mb = (blob.size or 0) / (1024 * 1024)
    if size_mb > _MAX_DOWNLOAD_MB:
        raise ValueError(
            f"File is {size_mb:.1f} MB, exceeds limit of {_MAX_DOWNLOAD_MB} MB."
        )

    logger.info(f"Downloading gs://{bucket_name}/{blob_name} ({size_mb:.1f} MB)")
    blob.download_to_filename(output_path)


def _download_from_azure(uri: str, output_path: str) -> None:
    """Download a file from Azure Blob Storage."""
    from azure.storage.blob import BlobServiceClient

    parsed = urlparse(uri)
    container = parsed.netloc
    blob_name = parsed.path.lstrip("/")

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise ValueError(
            "AZURE_STORAGE_CONNECTION_STRING environment variable is required "
            "for Azure Blob Storage access."
        )

    client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = client.get_blob_client(container=container, blob=blob_name)

    # Check size
    props = blob_client.get_blob_properties()
    size_mb = props.size / (1024 * 1024)
    if size_mb > _MAX_DOWNLOAD_MB:
        raise ValueError(
            f"File is {size_mb:.1f} MB, exceeds limit of {_MAX_DOWNLOAD_MB} MB."
        )

    logger.info(f"Downloading az://{container}/{blob_name} ({size_mb:.1f} MB)")
    with open(output_path, "wb") as f:
        download_stream = blob_client.download_blob()
        download_stream.readinto(f)


def _convert_to_csv(file_path: str) -> str:
    """Convert non-CSV files (Excel, JSON, Parquet) to CSV. Returns CSV path."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return file_path

    csv_path = file_path.rsplit(".", 1)[0] + ".csv"

    if ext == ".parquet":
        df = pd.read_parquet(file_path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    elif ext == ".json":
        df = pd.read_json(file_path)
    else:
        # Fall back to treating as CSV
        return file_path

    df.to_csv(csv_path, index=False)
    # Clean up the original non-CSV file
    os.remove(file_path)
    logger.info(f"Converted {ext} to CSV: {csv_path}")
    return csv_path


def ingest_from_cloud(cloud_uri: str, output_dir: str = "data/uploads") -> str:
    """
    Download a file from cloud storage and return the local CSV path.

    Args:
        cloud_uri: Cloud storage URI (s3://, gs://, az://).
        output_dir: Directory to save the downloaded file.

    Returns:
        Absolute path to the local CSV file.
    """
    validate_cloud_uri(cloud_uri)
    ensure_dir(output_dir)

    parsed = urlparse(cloud_uri)
    scheme = parsed.scheme.lower()

    # Preserve the original file extension for format detection
    remote_filename = Path(parsed.path).name or "data.csv"
    ext = Path(remote_filename).suffix or ".csv"
    local_filename = f"cloud_{uuid.uuid4().hex[:8]}{ext}"
    local_path = str(Path(output_dir) / local_filename)

    # Log only bucket/container name for security
    safe_repr = f"{scheme}://{parsed.netloc}"
    logger.info(f"Ingesting data from cloud: {safe_repr}")

    try:
        if scheme == "s3":
            _download_from_s3(cloud_uri, local_path)
        elif scheme == "gs":
            _download_from_gcs(cloud_uri, local_path)
        elif scheme in ("az", "abfs", "abfss"):
            _download_from_azure(cloud_uri, local_path)
        else:
            raise ValueError(f"Unsupported cloud scheme: {scheme}")

        # Convert to CSV if needed (e.g. Parquet, Excel, JSON)
        csv_path = _convert_to_csv(local_path)
        logger.info(f"Cloud ingestion complete: {csv_path}")
        return csv_path
    except Exception:
        # Clean up partial/temp files on failure to avoid disk leaks.
        for path in (local_path, local_path.rsplit(".", 1)[0] + ".csv"):
            try:
                if Path(path).exists():
                    os.remove(path)
                    logger.debug(f"Cleaned up temp file: {path}")
            except OSError:
                pass
        raise
