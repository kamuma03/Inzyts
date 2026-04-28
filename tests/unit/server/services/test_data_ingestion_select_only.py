"""Regression tests for the H-2 fix: ``ingest_from_sql`` must reject DML
before opening a database connection.

Before the fix, the ``db_uri + db_query`` ingestion bridge wrote the user's
query straight to ``pd.read_sql(text(query), conn)`` with no AST guard. The
README claimed all SQL paths validated SELECT-only, but this path didn't.
An authenticated analyst could pass ``DROP TABLE x`` and Inzyts would
execute it.

These tests verify:

* All known DML/DDL forms raise ``DataValidationError`` before any
  ``create_engine``/connection happens.
* CTE-wrapped DML is also rejected.
* Plain SELECT queries proceed past validation (no error from the guard).
* On rejection, no database connection is opened (lifespan invariant).

The validator path is shared with ``src.agents.sql_agent`` and
``/api/v2/files/sql-preview``, so a regression here would also break those.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.server.services.data_ingestion import ingest_from_sql
from src.utils.errors import DataValidationError


_BAD_QUERIES = [
    pytest.param("DROP TABLE users",                    id="drop"),
    pytest.param("INSERT INTO users (id) VALUES (1)",   id="insert"),
    pytest.param("UPDATE users SET name = 'x'",         id="update"),
    pytest.param("DELETE FROM users",                   id="delete"),
    pytest.param("CREATE TABLE evil (x INT)",           id="create"),
    pytest.param("TRUNCATE TABLE users",                id="truncate"),
    # CTE wrapping a DELETE — the AST walk catches this even though the
    # statement *parses* as a SELECT at the top level.
    pytest.param(
        "WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x",
        id="cte_delete",
    ),
]


@pytest.mark.parametrize("query", _BAD_QUERIES)
def test_ingest_from_sql_rejects_dml_before_connecting(query, tmp_path):
    """Any non-plain-SELECT query must raise DataValidationError without
    ever calling ``create_engine``. This guarantees a malicious query never
    establishes a session — so ``SET TRANSACTION READ ONLY`` (defence in
    depth) does not need to be relied upon."""
    with patch(
        "src.server.services.data_ingestion.create_engine"
    ) as mock_create:
        with pytest.raises(DataValidationError):
            ingest_from_sql(
                "postgresql://u:p@warehouse.example.com/db",
                query,
                str(tmp_path),
            )

        # The validation guard MUST fire before we touch the network.
        mock_create.assert_not_called()


def test_ingest_from_sql_accepts_plain_select(tmp_path):
    """A plain SELECT must pass validation and reach the engine layer.

    We mock the engine so no real network call happens — the test only
    asserts that the validator did NOT block the query.
    """
    fake_engine = MagicMock(name="engine")
    fake_conn_cm = MagicMock()
    fake_conn = MagicMock()
    fake_conn_cm.__enter__ = MagicMock(return_value=fake_conn)
    fake_conn_cm.__exit__ = MagicMock(return_value=False)
    fake_engine.connect.return_value = fake_conn_cm

    with patch(
        "src.server.services.data_ingestion.create_engine",
        return_value=fake_engine,
    ), patch(
        "src.server.services.data_ingestion.pd.read_sql"
    ) as mock_read_sql:
        # Return a 1-row chunk iterator that has a .close() method so the
        # function body's ``finally: chunk_iter.close()`` works.
        import pandas as pd
        chunk_iter = MagicMock()
        chunk_iter.__iter__ = lambda self: iter(
            [pd.DataFrame({"a": [1], "b": [2]})]
        )
        chunk_iter.close = MagicMock()
        mock_read_sql.return_value = chunk_iter

        path = ingest_from_sql(
            "postgresql://u:p@warehouse.example.com/db",
            "SELECT a, b FROM small_table LIMIT 10",
            str(tmp_path),
        )

    # Validation passed → engine was opened (mocked) and a CSV was written.
    fake_engine.connect.assert_called_once()
    assert str(tmp_path) in path
    assert path.endswith(".csv")


def test_ingest_from_sql_attempts_read_only_transaction(tmp_path):
    """Defence in depth — even though the validator catches DML upfront,
    the function should still issue ``SET TRANSACTION READ ONLY`` against
    backends that support it (PostgreSQL, MySQL).
    """
    fake_engine = MagicMock(name="engine")
    fake_conn_cm = MagicMock()
    fake_conn = MagicMock()
    fake_conn_cm.__enter__ = MagicMock(return_value=fake_conn)
    fake_conn_cm.__exit__ = MagicMock(return_value=False)
    fake_engine.connect.return_value = fake_conn_cm

    with patch(
        "src.server.services.data_ingestion.create_engine",
        return_value=fake_engine,
    ), patch(
        "src.server.services.data_ingestion.pd.read_sql"
    ) as mock_read_sql:
        import pandas as pd
        chunk_iter = MagicMock()
        chunk_iter.__iter__ = lambda self: iter([pd.DataFrame({"x": [1]})])
        chunk_iter.close = MagicMock()
        mock_read_sql.return_value = chunk_iter

        ingest_from_sql(
            "postgresql://u:p@warehouse.example.com/db",
            "SELECT x FROM t",
            str(tmp_path),
        )

    # Inspect the SQL strings that the function executed via conn.execute.
    executed = [
        str(call.args[0]) if call.args else ""
        for call in fake_conn.execute.call_args_list
    ]
    assert any("READ ONLY" in s.upper() for s in executed), (
        f"Expected SET TRANSACTION READ ONLY to be issued, got: {executed}"
    )


def test_ingest_from_sql_unparseable_query_is_rejected(tmp_path):
    """A query that sqlglot cannot parse must be rejected conservatively
    rather than passed through to the engine."""
    with patch(
        "src.server.services.data_ingestion.create_engine"
    ) as mock_create:
        with pytest.raises(DataValidationError):
            ingest_from_sql(
                "postgresql://u:p@warehouse.example.com/db",
                "this is not SQL at all !!!",
                str(tmp_path),
            )
        mock_create.assert_not_called()
