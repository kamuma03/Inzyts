"""
Shared URI validation utilities.

Kept in src/utils so both the server layer (data_ingestion.py, cloud_ingestion.py)
and the agent layer (sql_agent.py) can import from here without cross-layer coupling.
"""

from typing import Set
from urllib.parse import urlparse

from src.utils.errors import DataValidationError

# ---------------------------------------------------------------------------
# Allowed URI scheme registries
# ---------------------------------------------------------------------------

# Database schemes.  sqlite is intentionally excluded: sqlite:// URIs resolve
# to local filesystem paths, allowing authenticated users to read arbitrary
# host files (e.g. sqlite:////etc/shadow).  Network databases only.
ALLOWED_DB_SCHEMES: Set[str] = {
    # PostgreSQL
    "postgresql",
    "postgresql+psycopg2",
    "postgresql+asyncpg",
    # MySQL
    "mysql",
    "mysql+pymysql",
    # Microsoft SQL Server
    "mssql",
    "mssql+pymssql",
    # Cloud Data Warehouses
    "bigquery",                  # Google BigQuery (sqlalchemy-bigquery)
    "snowflake",                 # Snowflake (snowflake-sqlalchemy)
    "redshift",                  # Amazon Redshift (sqlalchemy-redshift)
    "redshift+psycopg2",         # Redshift via psycopg2
    "databricks+connector",      # Databricks (databricks-sql-connector)
}

# Cloud storage schemes.
ALLOWED_CLOUD_SCHEMES: Set[str] = {"s3", "gs", "az", "abfs", "abfss"}


# ---------------------------------------------------------------------------
# Unified validator
# ---------------------------------------------------------------------------

def validate_uri_scheme(uri: str, allowed_schemes: Set[str], label: str = "URI") -> None:
    """Raise ``DataValidationError`` if the URI scheme is not in *allowed_schemes*.

    Prevents SSRF and local-file-read attacks via crafted URI schemes.

    Args:
        uri: The user-supplied URI string.
        allowed_schemes: Set of permitted scheme strings (lowercase).
        label: Human-readable label for error messages.
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        raise DataValidationError(
            f"{label} scheme '{scheme}' is not allowed. "
            f"Permitted schemes: {sorted(allowed_schemes)}"
        )


# ---------------------------------------------------------------------------
# Convenience wrappers (backward-compatible)
# ---------------------------------------------------------------------------

def validate_db_uri(db_uri: str) -> None:
    """Raise if the database URI scheme is not in the allowed list."""
    validate_uri_scheme(db_uri, ALLOWED_DB_SCHEMES, label="Database URI")


def validate_cloud_uri(uri: str) -> None:
    """Raise if the cloud URI scheme is not in the allowed list."""
    validate_uri_scheme(uri, ALLOWED_CLOUD_SCHEMES, label="Cloud URI")
