import re
import uuid
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from sqlalchemy import text

from src.agents.base import BaseAgent
from src.config import settings
from src.models.state import AnalysisState, Phase
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

logger = get_logger()

# Maximum rows returned by an autonomous SQL query to prevent memory exhaustion.
_SQL_MAX_ROWS = settings.sql_max_rows
# Maximum columns — a wide result (e.g. SELECT * on a 600-column table) can OOM the worker.
_SQL_MAX_COLS = settings.sql_max_cols

SQL_AGENT_PROMPT = """You are the SQLExtractionAgent for the Inzyts data analysis system.
Your job is to read the schema of a SQL database and write a single, correct, read-only SQL query to extract the data needed to answer the user's analytical question.
Return ONLY the raw SQL query. Do not include markdown formatting or explanations. Ensure the query is a valid read-only SELECT statement with no semicolons.

Database Schema:
{schema}

User Question: {question}
"""


def _validate_select_only(sql_query: str) -> str | None:
    """Return an error message if sql_query is not a plain SELECT, else None.

    Uses sqlglot to parse the AST so that CTEs with embedded DML
    (e.g. WITH x AS (DELETE ...) SELECT ...) are also rejected.
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
            return "Generated query is not a SELECT statement."

        # Reject any DML nodes anywhere in the AST (covers CTE abuse).
        # sqlglot renamed Truncate -> TruncateTable in v26+; support both.
        _truncate = getattr(exp, "TruncateTable", None) or getattr(exp, "Truncate", None)
        dml_types = tuple(
            t for t in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, _truncate)
            if t is not None
        )
        for node in statement.walk():
            if isinstance(node, dml_types):
                return (
                    f"Generated query contains a disallowed DML operation "
                    f"({type(node).__name__}). Only read-only SELECT statements are permitted."
                )
        return None
    except Exception as parse_err:
        # If sqlglot cannot parse the query, reject it conservatively.
        return f"Query could not be parsed as valid SQL: {parse_err}"


class SQLExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SQLExtractionAgent",
            phase=Phase.PHASE_1,
            system_prompt=SQL_AGENT_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        logger.info("SQLExtractionAgent starting...")

        db_uri = getattr(state.user_intent, "db_uri", None)
        question = state.user_intent.analysis_question

        if not db_uri:
            logger.error("SQLExtractionAgent requires a db_uri in UserIntent.")
            return {"errors": ["No db_uri provided for SQLExtractionAgent."]}
        if not question:
            logger.error("SQLExtractionAgent requires an analysis_question in UserIntent to generate the query.")
            return {"errors": ["No analysis_question provided for SQLExtractionAgent."]}

        # URI scheme already validated by AnalysisRequest Pydantic model at
        # deserialization time (see schemas.py @field_validator).

        try:
            from langchain_community.utilities import SQLDatabase

            db = SQLDatabase.from_uri(db_uri, view_support=True)
            schema_info = db.get_table_info()

            prompt = self.system_prompt.format(schema=schema_info, question=question)
            response = self.llm_agent.invoke(prompt)
            sql_query = response.strip()

            # Strip markdown code fences using regex to handle all variants:
            # ```sql\n...\n``` or ```\n...\n```
            sql_query = re.sub(r"^```\w*\n?", "", sql_query)
            sql_query = re.sub(r"\n?```$", "", sql_query)
            sql_query = sql_query.strip()

            # Validate: must be a single read-only SELECT statement.
            # sqlglot AST check catches CTE+DML bypass attempts such as:
            #   WITH x AS (DELETE FROM users) SELECT 1
            validation_error = _validate_select_only(sql_query)
            if validation_error:
                logger.warning(
                    f"SQL validation blocked query (preview: {sql_query[:200]!r}): {validation_error}"
                )
                return {"errors": [validation_error]}

            # Log only the first 200 chars to avoid leaking sensitive literal values.
            logger.info(f"Generated SQL Query (preview): {sql_query[:200]}")

            # Reuse the engine from the SQLDatabase instance to avoid opening a second
            # connection pool. Fall back to creating a new engine if the private
            # attribute is unavailable in a future LangChain version.
            engine = getattr(db, "_engine", None)
            created_new_engine = False
            if engine is None:
                from sqlalchemy import create_engine
                engine = create_engine(db_uri)
                created_new_engine = True

            try:
                with engine.connect() as conn:
                    conn = conn.execution_options(
                        timeout=120,
                        postgresql_readonly=True,
                        mysql_read_only=True,
                    )
                    # Set session to read-only where supported (PostgreSQL, MySQL).
                    try:
                        conn.execute(text("SET TRANSACTION READ ONLY"))
                    except Exception:
                        pass  # Not all backends support this; validation above is primary guard.

                    # Read in chunks to avoid loading the full result set into memory.
                    # Explicitly close the iterator to release the cursor immediately.
                    chunk_iter = pd.read_sql(text(sql_query), conn, chunksize=_SQL_MAX_ROWS)
                    try:
                        df = next(iter(chunk_iter))
                    finally:
                        chunk_iter.close()
            finally:
                if created_new_engine:
                    engine.dispose()

            if len(df) == _SQL_MAX_ROWS:
                logger.warning(
                    f"Query result was truncated at {_SQL_MAX_ROWS} rows. "
                    "Increase SQL_MAX_ROWS env var if more data is needed."
                )

            if len(df.columns) > _SQL_MAX_COLS:
                return {
                    "errors": [
                        f"Query returns {len(df.columns)} columns (limit {_SQL_MAX_COLS}). "
                        "Narrow your SELECT to reduce memory usage."
                    ]
                }

            output_dir = Path(settings.upload_dir).resolve()
            ensure_dir(output_dir)

            filename = f"auto_sql_extract_{uuid.uuid4().hex[:8]}.csv"
            output_path = str(output_dir / filename)
            df.to_csv(output_path, index=False)

            logger.info(f"SQLExtractionAgent saved {len(df)} rows to {output_path}")
            return {"csv_path": output_path}

        except ImportError:
            return {"errors": ["langchain_community and sqlalchemy are required for SQLExtractionAgent."]}
        except Exception as e:
            logger.error(f"SQLExtractionAgent failed: {str(e)}")
            return {"errors": [f"SQLExtractionAgent failed: {str(e)}"]}
