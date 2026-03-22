"""Tests for graph routing functions — specifically route_after_initialize."""

from unittest.mock import MagicMock
from src.workflow.graph import route_after_initialize


def _make_state(db_uri=None, api_url=None, cached=False, multi_files=None):
    state = MagicMock()
    state.using_cached_profile = cached
    state.cache = MagicMock() if cached else None

    intent = MagicMock()
    intent.db_uri = db_uri
    intent.api_url = api_url
    intent.multi_file_input = multi_files
    state.user_intent = intent

    return state


def test_route_sql_extraction():
    state = _make_state(db_uri="postgresql://user:pass@host/db")
    assert route_after_initialize(state) == "sql_extraction"


def test_route_api_extraction():
    state = _make_state(api_url="https://api.example.com/data")
    assert route_after_initialize(state) == "api_extraction"


def test_route_sql_takes_precedence_over_api():
    """When both db_uri and api_url are set, SQL extraction takes priority."""
    state = _make_state(
        db_uri="postgresql://user:pass@host/db",
        api_url="https://api.example.com/data",
    )
    assert route_after_initialize(state) == "sql_extraction"


def test_route_cache_restore():
    state = _make_state(cached=True)
    assert route_after_initialize(state) == "restore_cache"


def test_route_data_merger():
    mock_files = MagicMock()
    mock_files.files = [MagicMock(), MagicMock()]
    state = _make_state(multi_files=mock_files)
    assert route_after_initialize(state) == "data_merger"


def test_route_default_phase1():
    """No special conditions -> goes to create_phase1_handoff."""
    state = _make_state()
    assert route_after_initialize(state) == "create_phase1_handoff"
