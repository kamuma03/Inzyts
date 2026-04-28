"""
Shared URI validation utilities.

Kept in src/utils so both the server layer (data_ingestion.py, cloud_ingestion.py)
and the agent layer (sql_agent.py) can import from here without cross-layer coupling.
"""

from typing import Optional, Set
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

def _is_db_host_blocked(db_uri: str) -> bool:
    """Return True when the URI host points at a loopback / link-local address.

    Blocks attempts to point ``db_uri`` at the platform's own internal services
    (the Docker-network Postgres at ``db``, Redis at ``redis``, the worker's
    loopback, the AWS metadata IP at ``169.254.169.254``, etc.).

    This is intentionally narrower than the API SSRF check — many legitimate
    customer DBs live on private RFC1918 addresses, so we only block:

      * loopback (127.0.0.0/8, ::1, ``localhost``, ``0.0.0.0``)
      * link-local (169.254.0.0/16, fe80::/10) — covers cloud metadata
      * the docker-network names of our own services (``db``, ``redis``,
        and any value in ``INZYTS_INTERNAL_HOSTS``)

    Operators who need to run an analytics DB on the same host can opt out by
    setting ``INZYTS_DB_URI_ALLOW_LOOPBACK=1`` in the environment.
    """
    import ipaddress
    import os
    import socket

    if os.environ.get("INZYTS_DB_URI_ALLOW_LOOPBACK") == "1":
        return False

    parsed = urlparse(db_uri)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        # No host (e.g. sqlite-style URIs) — already rejected by scheme check.
        return False

    # Block platform-internal docker hostnames + any operator-provided extras.
    blocked_names = {"db", "redis", "localhost"}
    extras = os.environ.get("INZYTS_INTERNAL_HOSTS", "")
    blocked_names.update(h.strip() for h in extras.split() if h.strip())
    if hostname in blocked_names:
        return True

    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError):
        # Don't block on DNS failure — it's a real DB outage signal that the
        # caller wants to see. The scheme check is the primary guard here.
        return False

    # is_unspecified covers ``0.0.0.0`` (the "any" address), which on Linux
    # routes back to the local interface and is therefore equivalent to
    # loopback for SSRF purposes.
    return ip.is_loopback or ip.is_link_local or ip.is_unspecified


def validate_db_uri(db_uri: str) -> None:
    """Raise if the database URI scheme is not in the allowed list, or if the
    host points at a platform-internal / loopback / link-local address."""
    validate_uri_scheme(db_uri, ALLOWED_DB_SCHEMES, label="Database URI")
    if _is_db_host_blocked(db_uri):
        raise DataValidationError(
            "Database URI host is not permitted. "
            "Loopback, link-local, and platform-internal hostnames are blocked. "
            "Set INZYTS_DB_URI_ALLOW_LOOPBACK=1 to permit loopback for local dev."
        )


def validate_cloud_uri(uri: str) -> None:
    """Raise if the cloud URI scheme is not in the allowed list."""
    validate_uri_scheme(uri, ALLOWED_CLOUD_SCHEMES, label="Cloud URI")


# ---------------------------------------------------------------------------
# SQL query validation (SELECT-only, AST-checked)
# ---------------------------------------------------------------------------

def validate_select_only(sql_query: str) -> Optional[str]:
    """Return an error message if ``sql_query`` is not a plain SELECT, else None.

    Uses sqlglot to parse the AST so that CTEs with embedded DML
    (e.g. ``WITH x AS (DELETE ...) SELECT ...``) are also rejected.

    Shared between:
      * ``src.agents.sql_agent`` — validating LLM-generated queries
      * ``src.server.services.data_ingestion`` — validating user-supplied
        queries on the explicit ``db_query`` ingestion path
      * ``src.server.routes.files`` — validating the SQL preview endpoint

    Centralising the rule here means a future tightening (e.g. blocking
    ``COPY``, ``EXECUTE``, set returning function calls) only needs one
    edit. Returns the error string instead of raising so callers can
    decide between HTTP 400, agent error, or workflow halt.
    """
    try:
        import sqlglot
        import sqlglot.expressions as exp
    except ImportError as e:
        raise RuntimeError(
            "sqlglot is required for SQL query validation. "
            "Install it with: pip install sqlglot"
        ) from e

    try:
        statement = sqlglot.parse_one(sql_query)
        if not isinstance(statement, exp.Select):
            return "Query is not a SELECT statement."

        # Reject any DML nodes anywhere in the AST (covers CTE abuse).
        # sqlglot renamed Truncate -> TruncateTable in v26+; support both.
        _truncate = getattr(exp, "TruncateTable", None) or getattr(exp, "Truncate", None)
        dml_types = tuple(
            t for t in (
                exp.Insert,
                exp.Update,
                exp.Delete,
                exp.Drop,
                exp.Create,
                _truncate,
            )
            if t is not None
        )
        for node in statement.walk():
            if isinstance(node, dml_types):
                return (
                    f"Query contains a disallowed DML operation "
                    f"({type(node).__name__}). Only read-only SELECT "
                    f"statements are permitted."
                )
        return None
    except Exception as parse_err:
        # If sqlglot cannot parse the query, reject it conservatively.
        return f"Query could not be parsed as valid SQL: {parse_err}"
