"""
Integration tests for external database integration using a real PostgreSQL
container (via testcontainers).

These tests verify behaviour that unit tests with mocks cannot cover:
  - Read-only enforcement actually blocks writes
  - Row-limit truncation works end-to-end
  - ingest_from_sql produces a valid CSV from a real DB
  - _validate_select_only + real execution round-trip
  - Connection cleanup under normal and error conditions
  - Empty result sets handled gracefully
"""

import os
import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from unittest.mock import patch

from src.agents.sql_agent import _validate_select_only
from src.server.services.data_ingestion import ingest_from_sql

pytestmark = pytest.mark.requires_db


# ── ingest_from_sql against real Postgres ──────────────────────────────


class TestIngestFromSQL:
    """Tests for the data_ingestion.ingest_from_sql path."""

    def test_basic_extraction(self, seeded_db, tmp_path):
        """Ingest all rows from test_sales and verify the CSV contents."""
        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query="SELECT region, revenue, quarter FROM test_sales ORDER BY id",
            output_dir=str(tmp_path),
        )

        assert os.path.isfile(csv_path)
        df = pd.read_csv(csv_path)
        assert len(df) == 10
        assert set(df.columns) == {"region", "revenue", "quarter"}
        assert df["revenue"].sum() == 20000

    def test_filtered_query(self, seeded_db, tmp_path):
        """WHERE clause filtering works against real Postgres."""
        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query="SELECT region, revenue FROM test_sales WHERE quarter = 1",
            output_dir=str(tmp_path),
        )

        df = pd.read_csv(csv_path)
        assert len(df) == 3
        assert set(df["region"]) == {"North", "South", "East"}

    def test_aggregation_query(self, seeded_db, tmp_path):
        """GROUP BY + SUM works against real Postgres."""
        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query=(
                "SELECT region, SUM(revenue) AS total_revenue "
                "FROM test_sales GROUP BY region ORDER BY region"
            ),
            output_dir=str(tmp_path),
        )

        df = pd.read_csv(csv_path)
        assert len(df) == 4
        assert "total_revenue" in df.columns

    def test_empty_result_set(self, seeded_db, tmp_path):
        """Querying an empty table should produce a CSV with headers only."""
        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query="SELECT * FROM test_empty",
            output_dir=str(tmp_path),
        )

        df = pd.read_csv(csv_path)
        assert len(df) == 0
        assert "id" in df.columns

    def test_row_limit_truncation(self, seeded_db, tmp_path):
        """When SQL_MAX_ROWS < actual rows, only the first chunk is returned."""
        # Temporarily set the row limit very low
        with patch("src.server.services.data_ingestion._SQL_MAX_ROWS", 3):
            csv_path = ingest_from_sql(
                db_uri=seeded_db,
                query="SELECT * FROM test_sales",
                output_dir=str(tmp_path),
            )

        df = pd.read_csv(csv_path)
        assert len(df) == 3  # truncated to our mock limit

    def test_connection_error_propagates(self, tmp_path):
        """A bad URI raises an exception, not a silent failure."""
        with pytest.raises(Exception):
            ingest_from_sql(
                db_uri="postgresql://bad_user:bad_pass@localhost:1/no_db",
                query="SELECT 1",
                output_dir=str(tmp_path),
            )

    def test_invalid_query_raises(self, seeded_db, tmp_path):
        """A query referencing a non-existent table raises an error."""
        with pytest.raises(Exception, match="no_such_table"):
            ingest_from_sql(
                db_uri=seeded_db,
                query="SELECT * FROM no_such_table",
                output_dir=str(tmp_path),
            )


# ── Read-only enforcement ──────────────────────────────────────────────


class TestReadOnlyEnforcement:
    """Verify that SET TRANSACTION READ ONLY actually blocks writes on Postgres."""

    def test_read_only_blocks_insert(self, seeded_db):
        """A connection in read-only mode must reject INSERT."""
        engine = create_engine(seeded_db)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                with pytest.raises(Exception, match="read-only"):
                    conn.execute(
                        text("INSERT INTO test_sales (region, revenue, quarter) VALUES ('X', 0, 0)")
                    )
        finally:
            engine.dispose()

    def test_read_only_blocks_update(self, seeded_db):
        """A connection in read-only mode must reject UPDATE."""
        engine = create_engine(seeded_db)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                with pytest.raises(Exception, match="read-only"):
                    conn.execute(text("UPDATE test_sales SET revenue = 0"))
        finally:
            engine.dispose()

    def test_read_only_blocks_delete(self, seeded_db):
        """A connection in read-only mode must reject DELETE."""
        engine = create_engine(seeded_db)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                with pytest.raises(Exception, match="read-only"):
                    conn.execute(text("DELETE FROM test_sales"))
        finally:
            engine.dispose()

    def test_read_only_blocks_drop(self, seeded_db):
        """A connection in read-only mode must reject DROP TABLE."""
        engine = create_engine(seeded_db)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                with pytest.raises(Exception, match="read-only"):
                    conn.execute(text("DROP TABLE test_sales"))
        finally:
            engine.dispose()

    def test_read_only_allows_select(self, seeded_db):
        """SELECT still works under read-only mode."""
        engine = create_engine(seeded_db)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                result = conn.execute(text("SELECT COUNT(*) FROM test_sales"))
                count = result.scalar()
                assert count == 10
        finally:
            engine.dispose()


# ── SQL validation + real execution round-trip ─────────────────────────


class TestValidationRoundTrip:
    """Combine _validate_select_only with real query execution."""

    @pytest.mark.parametrize("query,expected_rows", [
        ("SELECT * FROM test_sales", 10),
        ("SELECT region FROM test_sales WHERE quarter = 2", 3),
        ("SELECT COUNT(*) AS cnt FROM test_sales", 1),
        ("WITH q1 AS (SELECT * FROM test_sales WHERE quarter = 1) SELECT * FROM q1", 3),
    ])
    def test_valid_queries_pass_and_execute(self, seeded_db, tmp_path, query, expected_rows):
        """Queries that pass validation should also execute successfully."""
        assert _validate_select_only(query) is None

        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query=query,
            output_dir=str(tmp_path),
        )
        df = pd.read_csv(csv_path)
        assert len(df) == expected_rows

    @pytest.mark.parametrize("bad_query", [
        "INSERT INTO test_sales (region, revenue, quarter) VALUES ('X', 0, 0)",
        "UPDATE test_sales SET revenue = 0",
        "DELETE FROM test_sales",
        "DROP TABLE test_sales",
        "SELECT 1; DROP TABLE test_sales",
    ])
    def test_dangerous_queries_blocked_by_validation(self, bad_query):
        """Dangerous queries must be rejected by _validate_select_only before execution."""
        error = _validate_select_only(bad_query)
        assert error is not None


# ── Connection cleanup ─────────────────────────────────────────────────


class TestConnectionCleanup:
    """Verify connections are properly released back to the pool."""

    def test_many_sequential_ingests_no_leak(self, seeded_db, tmp_path):
        """Run many ingestions sequentially — should not exhaust connections."""
        for i in range(20):
            csv_path = ingest_from_sql(
                db_uri=seeded_db,
                query=f"SELECT * FROM test_sales WHERE quarter = {(i % 4) + 1}",
                output_dir=str(tmp_path / str(i)),
            )
            assert os.path.isfile(csv_path)

    def test_connection_released_after_error(self, seeded_db, tmp_path):
        """After a failed query, subsequent queries should still work."""
        with pytest.raises(Exception):
            ingest_from_sql(
                db_uri=seeded_db,
                query="SELECT * FROM nonexistent_table_xyz",
                output_dir=str(tmp_path / "fail"),
            )

        # This should succeed — connection was properly cleaned up
        csv_path = ingest_from_sql(
            db_uri=seeded_db,
            query="SELECT * FROM test_sales LIMIT 1",
            output_dir=str(tmp_path / "ok"),
        )
        assert os.path.isfile(csv_path)
