"""
Integration test fixtures — spins up a throwaway PostgreSQL container via
testcontainers so that SQL integration tests hit a real database.

The container is shared across all tests in the session (scope="session")
and automatically destroyed when pytest exits.
"""

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL 15 container and yield (container, uri).

    Skips the entire session-scoped fixture if Docker is unavailable.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    with PostgresContainer("postgres:15.5") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_uri(pg_container):
    """Return a SQLAlchemy connection URI for the test Postgres."""
    return pg_container.get_connection_url()


@pytest.fixture(scope="session")
def pg_engine(pg_uri):
    """Create a shared SQLAlchemy engine for the session."""
    engine = create_engine(pg_uri)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded_db(pg_engine, pg_uri):
    """Seed the test database with sample tables and return the URI.

    Tables:
      - test_sales (id SERIAL, region TEXT, revenue NUMERIC, quarter INT)
      - test_empty (id SERIAL, value TEXT)  — intentionally empty
      - test_wide  (c0..c19 INT)            — 20 columns, for column-limit tests
    """
    with pg_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_sales (
                id SERIAL PRIMARY KEY,
                region TEXT NOT NULL,
                revenue NUMERIC NOT NULL,
                quarter INT NOT NULL
            )
        """))
        conn.execute(text("TRUNCATE test_sales RESTART IDENTITY"))
        conn.execute(text("""
            INSERT INTO test_sales (region, revenue, quarter) VALUES
            ('North', 1500, 1), ('South', 2300, 1), ('East', 1800, 1),
            ('West', 2100, 2), ('North', 1700, 2), ('South', 2500, 2),
            ('East', 1900, 3), ('West', 2200, 3), ('North', 1600, 3),
            ('South', 2400, 4)
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_empty (
                id SERIAL PRIMARY KEY, value TEXT
            )
        """))
        conn.execute(text("TRUNCATE test_empty RESTART IDENTITY"))

        # Wide table for column-limit tests
        col_defs = ", ".join(f"c{i} INT" for i in range(20))
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS test_wide ({col_defs})"))
        conn.execute(text("TRUNCATE test_wide"))
        col_names = ", ".join(f"c{i}" for i in range(20))
        col_vals = ", ".join(str(i) for i in range(20))
        conn.execute(text(f"INSERT INTO test_wide ({col_names}) VALUES ({col_vals})"))

    return pg_uri
