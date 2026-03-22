import pytest
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from src.agents.sql_agent import SQLExtractionAgent, _validate_select_only
from src.models.state import AnalysisState
from src.models.handoffs import UserIntent


@pytest.fixture
def mock_sql_database():
    # SQLDatabase is imported lazily inside process(), so patch at the source module.
    # Provide a mock _engine so the agent reuses it instead of creating a second one.
    with patch("langchain_community.utilities.SQLDatabase") as mock:
        instance = mock.from_uri.return_value
        instance.get_table_info.return_value = "CREATE TABLE test (id INT, name TEXT);"
        instance._engine = MagicMock()
        yield mock


@pytest.fixture
def agent_with_mock_llm():
    """Return a SQLExtractionAgent whose LLM is replaced with a MagicMock."""
    with patch("src.agents.base.BaseAgent.__init__", lambda self, **kw: None):
        agent = object.__new__(SQLExtractionAgent)
        # Manually set required attributes that __init__ would normally set
        agent.name = "SQLExtractionAgent"
        from src.agents.sql_agent import SQL_AGENT_PROMPT
        agent.system_prompt = SQL_AGENT_PROMPT
        agent.llm_agent = MagicMock()
        agent.llm_agent.total_tokens = 0
        agent.llm_agent.invoke.return_value = "SELECT * FROM test"
    return agent


def _make_state(db_uri=None, question=None):
    intent = UserIntent(csv_path="", db_uri=db_uri, analysis_question=question)
    return AnalysisState(csv_path="", user_intent=intent)


def test_sql_extraction_agent_missing_db_uri():
    agent = SQLExtractionAgent()
    state = _make_state()
    result = agent.process(state)
    assert "errors" in result
    assert "No db_uri provided" in result["errors"][0]


def test_sql_extraction_agent_missing_question():
    """URI validation happens at schema layer; agent checks for missing question."""
    agent = SQLExtractionAgent()
    state = _make_state(db_uri="postgresql://user:pass@host/db")
    result = agent.process(state)
    assert "errors" in result
    assert "No analysis_question provided" in result["errors"][0]


def test_sql_extraction_agent_rejects_sqlite_uri():
    """sqlite URIs must be rejected at the schema validation layer."""
    from src.utils.db_utils import validate_db_uri
    from src.utils.errors import DataValidationError
    import pytest
    with pytest.raises(DataValidationError, match="sqlite"):
        validate_db_uri("sqlite:///:memory:")


def test_sql_extraction_agent_invalid_sql_non_select(agent_with_mock_llm, mock_sql_database):
    agent_with_mock_llm.llm_agent.invoke.return_value = "INSERT INTO test VALUES (1, 'Bob')"
    state = _make_state(db_uri="postgresql://user:pass@host/db", question="Add a user")
    result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "not a SELECT statement" in result["errors"][0]


def test_sql_extraction_agent_rejects_stacked_statements(agent_with_mock_llm, mock_sql_database):
    agent_with_mock_llm.llm_agent.invoke.return_value = "SELECT 1; DROP TABLE users"
    state = _make_state(db_uri="postgresql://user:pass@host/db", question="Get data")
    result = agent_with_mock_llm.process(state)
    assert "errors" in result
    # sqlglot may raise on multi-statement input or parse only the first statement.
    # Either way an error must be present.
    assert len(result["errors"]) > 0


def test_sql_extraction_agent_rejects_cte_with_delete(agent_with_mock_llm, mock_sql_database):
    """CTE embedding a DELETE must be rejected even though the outer node is a Select."""
    agent_with_mock_llm.llm_agent.invoke.return_value = (
        "WITH x AS (DELETE FROM users WHERE 1=1) SELECT * FROM x"
    )
    state = _make_state(db_uri="postgresql://user:pass@host/db", question="Get all users")
    result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert any("DML" in e or "DELETE" in e or "not a SELECT" in e for e in result["errors"])


def test_sql_extraction_agent_rejects_cte_with_drop(agent_with_mock_llm, mock_sql_database):
    """CTE embedding a DROP must be rejected."""
    agent_with_mock_llm.llm_agent.invoke.return_value = (
        "WITH del AS (DROP TABLE sensitive_data) SELECT 1"
    )
    state = _make_state(db_uri="postgresql://user:pass@host/db", question="Get data")
    result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert any("DML" in e or "DROP" in e or "not a SELECT" in e for e in result["errors"])


# --- Unit tests for _validate_select_only ---

def test_validate_select_only_plain_select():
    assert _validate_select_only("SELECT * FROM users") is None


def test_validate_select_only_rejects_insert():
    err = _validate_select_only("INSERT INTO t VALUES (1)")
    assert err is not None
    assert "SELECT" in err


def test_validate_select_only_rejects_cte_delete():
    err = _validate_select_only(
        "WITH x AS (DELETE FROM users WHERE 1=1) SELECT * FROM x"
    )
    assert err is not None


def test_sql_extraction_agent_success(agent_with_mock_llm, mock_sql_database, tmp_path):
    fake_df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    # Return an iterator with a .close() method (mimics pandas chunked read).
    class _FakeChunkIter:
        def __init__(self, df):
            self._iter = iter([df])
            self.closed = False
        def __iter__(self):
            return self._iter
        def __next__(self):
            return next(self._iter)
        def close(self):
            self.closed = True

    fake_iter = _FakeChunkIter(fake_df)

    mock_conn = MagicMock()
    mock_sql_database.from_uri.return_value._engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_sql_database.from_uri.return_value._engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("src.agents.sql_agent.pd.read_sql", return_value=fake_iter), \
         patch("src.agents.sql_agent.ensure_dir"), \
         patch("src.agents.sql_agent.settings") as mock_settings:

        mock_settings.upload_dir = str(tmp_path)

        state = _make_state(db_uri="postgresql://user:pass@host/db", question="Get all data")
        result = agent_with_mock_llm.process(state)

        assert "csv_path" in result, f"Expected csv_path, got: {result}"
        assert "errors" not in result
        assert result["csv_path"].startswith(str(tmp_path)), (
            f"csv_path {result['csv_path']!r} is outside tmp_path {tmp_path}"
        )
        agent_with_mock_llm.llm_agent.invoke.assert_called_once()
        assert fake_iter.closed, "chunk iterator was not closed after reading"
