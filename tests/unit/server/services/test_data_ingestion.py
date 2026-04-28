import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.server.services.data_ingestion import ingest_from_sql
from src.utils.db_utils import validate_db_uri
from sqlalchemy.exc import SQLAlchemyError


class _FakeChunkIter:
    """Iterator with a .close() method, mimicking pandas chunked-read behaviour."""
    def __init__(self, df):
        self._iter = iter([df])
        self.closed = False

    def __iter__(self):
        return self._iter

    def __next__(self):
        return next(self._iter)

    def close(self):
        self.closed = True


@pytest.fixture
def mock_engine():
    with patch("src.server.services.data_ingestion.create_engine") as mock:
        yield mock


@pytest.fixture
def mock_read_sql():
    with patch("src.server.services.data_ingestion.pd.read_sql") as mock:
        df = pd.DataFrame({"id": [1, 2], "value": ["A", "B"]})
        mock.return_value = _FakeChunkIter(df)
        yield mock


@pytest.fixture
def mock_makedirs():
    with patch("pathlib.Path.mkdir") as mock:
        yield mock


@pytest.fixture
def mock_to_csv():
    with patch("src.server.services.data_ingestion.pd.DataFrame.to_csv") as mock:
        yield mock


def test_ingest_from_sql_success(mock_engine, mock_read_sql, mock_makedirs, mock_to_csv):
    output_dir = "/tmp/test_uploads"
    csv_path = ingest_from_sql(
        db_uri="postgresql://user:pass@localhost/db",
        query="SELECT * FROM test",
        output_dir=output_dir
    )

    assert "sql_extract_" in csv_path
    assert csv_path.endswith(".csv")
    mock_engine.assert_called_once()
    mock_read_sql.assert_called_once()
    mock_makedirs.assert_called_once_with(parents=True, exist_ok=True)
    mock_to_csv.assert_called_once()


def test_validate_db_uri_rejects_sqlite_at_model_level():
    """sqlite URIs are now rejected by the Pydantic @field_validator on request models,
    not inside ingest_from_sql itself. Verify the validator still works."""
    with pytest.raises(ValueError, match="not allowed"):
        validate_db_uri("sqlite:///local.db")


def test_ingest_from_sql_db_error(mock_engine, mock_read_sql, tmp_path):
    mock_read_sql.side_effect = SQLAlchemyError("DB Connection failed")

    with pytest.raises(Exception) as exc_info:
        ingest_from_sql(
            db_uri="postgresql://user:pass@invalid/db",
            query="SELECT 1",
            output_dir=str(tmp_path)
        )

    assert "DB Connection failed" in str(exc_info.value)


# --- Unit tests for validate_db_uri ---

def test_validate_db_uri_allows_postgresql():
    """No exception should be raised for allowed schemes."""
    validate_db_uri("postgresql://user:pass@localhost/db")
    validate_db_uri("postgresql+psycopg2://user:pass@localhost/db")
    validate_db_uri("mysql://user:pass@localhost/db")


def test_validate_db_uri_rejects_sqlite():
    with pytest.raises(ValueError, match="not allowed"):
        validate_db_uri("sqlite:///test.db")


def test_validate_db_uri_rejects_file_scheme():
    with pytest.raises(ValueError, match="not allowed"):
        validate_db_uri("file:///etc/passwd")


def test_validate_db_uri_rejects_http():
    with pytest.raises(ValueError, match="not allowed"):
        validate_db_uri("http://malicious.example.com/data")


# --- Cloud Data Warehouse URI schemes ---

def test_validate_db_uri_allows_bigquery():
    validate_db_uri("bigquery://project/dataset")


def test_validate_db_uri_allows_snowflake():
    validate_db_uri("snowflake://user:pass@account/db")


def test_validate_db_uri_allows_redshift():
    validate_db_uri("redshift://user:pass@cluster.region.redshift.amazonaws.com:5439/db")
    validate_db_uri("redshift+psycopg2://user:pass@host/db")


def test_validate_db_uri_allows_databricks():
    validate_db_uri("databricks+connector://token:dapi@host:443/default")
