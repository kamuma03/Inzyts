import uuid
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from sqlalchemy import create_engine, text

from src.config import settings
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

logger = get_logger()

# Maximum rows to load into memory from a single SQL extraction.
_SQL_MAX_ROWS = settings.sql_max_rows


def ingest_from_sql(db_uri: str, query: str, output_dir: str = "data/uploads") -> str:
    """
    Connect to a SQL database, execute a query, and save the result as a CSV.

    Args:
        db_uri: SQLAlchemy connection string (scheme must be in the allowed list).
        query: SQL SELECT query to execute.
        output_dir: Directory to save the resulting CSV.

    Returns:
        Absolute path to the generated CSV file.

    Raises:
        ValueError: If the URI scheme is not permitted.
        Exception: On connection or query failure.
    """
    # URI scheme already validated by Pydantic model (AnalysisRequest / SQLPreviewRequest).

    # Log only the host portion of the URI to avoid leaking credentials.
    parsed = urlparse(db_uri)
    safe_uri_repr = f"{parsed.scheme}://{parsed.hostname or 'unknown'}"
    logger.info(f"Ingesting data from SQL: {safe_uri_repr}")

    # Log a truncated version of the query to avoid leaking sensitive data in logs.
    query_preview = query[:200] + ("..." if len(query) > 200 else "")
    logger.info(f"Executing Query (truncated): {query_preview}")

    ensure_dir(output_dir)

    try:
        engine = create_engine(db_uri, connect_args={"connect_timeout": 10})

        # Read in chunks to avoid loading the full result set into memory before
        # applying the row limit. Take only the first chunk (_SQL_MAX_ROWS rows),
        # then explicitly close the iterator to release the cursor immediately.
        with engine.connect() as conn:
            chunk_iter = pd.read_sql(text(query), conn, chunksize=_SQL_MAX_ROWS)
            try:
                df = next(iter(chunk_iter))
            finally:
                chunk_iter.close()

        if len(df) == _SQL_MAX_ROWS:
            logger.warning(
                f"Query result was truncated at {_SQL_MAX_ROWS} rows. "
                "Increase SQL_MAX_ROWS env var if more data is needed."
            )

        filename = f"sql_extract_{uuid.uuid4().hex[:8]}.csv"
        output_path = str(Path(output_dir) / filename)
        df.to_csv(output_path, index=False)
        logger.info(f"Successfully extracted {len(df)} rows to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error extracting data from SQL Database: {str(e)}")
        raise
