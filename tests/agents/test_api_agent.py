import pytest
import json
import pandas as pd
from unittest.mock import patch, MagicMock

from src.agents.api_agent import (
    APIExtractionAgent,
    _build_auth_headers,
    _is_private_ip,
    _extract_data_with_jmespath,
)
from src.models.state import AnalysisState
from src.models.handoffs import UserIntent


# --- Helper ---

def _make_state(api_url=None, api_headers=None, api_auth=None, json_path=None, question=None):
    intent = UserIntent(
        csv_path="",
        api_url=api_url,
        api_headers=api_headers,
        api_auth=api_auth,
        json_path=json_path,
        analysis_question=question,
    )
    return AnalysisState(csv_path="", user_intent=intent)


@pytest.fixture
def agent_with_mock_llm():
    """Return an APIExtractionAgent whose LLM is replaced with a MagicMock."""
    with patch("src.agents.base.BaseAgent.__init__", lambda self, **kw: None):
        agent = object.__new__(APIExtractionAgent)
        agent.name = "APIExtractionAgent"
        from src.agents.api_agent import API_AGENT_PROMPT
        agent.system_prompt = API_AGENT_PROMPT
        agent.llm_agent = MagicMock()
        agent.llm_agent.total_tokens = 0
    return agent


# --- _build_auth_headers ---

def test_build_auth_headers_none():
    assert _build_auth_headers(None) == {}


def test_build_auth_headers_bearer():
    headers = _build_auth_headers({"type": "bearer", "token": "abc123"})
    assert headers == {"Authorization": "Bearer abc123"}


def test_build_auth_headers_api_key():
    headers = _build_auth_headers({"type": "api_key", "key_name": "X-My-Key", "key_value": "secret"})
    assert headers == {"X-My-Key": "secret"}


def test_build_auth_headers_api_key_default_name():
    headers = _build_auth_headers({"type": "api_key", "key_value": "secret"})
    assert headers == {"X-API-Key": "secret"}


def test_build_auth_headers_basic():
    import base64
    headers = _build_auth_headers({"type": "basic", "username": "user", "password": "pass"})
    expected = base64.b64encode(b"user:pass").decode()
    assert headers == {"Authorization": f"Basic {expected}"}


def test_build_auth_headers_unknown_type():
    headers = _build_auth_headers({"type": "oauth2"})
    assert headers == {}


# --- _is_private_ip ---

def test_is_private_ip_localhost():
    """localhost is blocked to prevent SSRF attacks on internal services."""
    assert _is_private_ip("http://localhost:8000/api") is True


def test_is_private_ip_127():
    assert _is_private_ip("http://127.0.0.1:8000/api") is True


def test_is_private_ip_no_hostname():
    assert _is_private_ip("not-a-url") is True


def test_is_private_ip_private_range():
    with patch("socket.gethostbyname", return_value="192.168.1.1"):
        assert _is_private_ip("http://internal.corp/api") is True


def test_is_private_ip_public():
    with patch("socket.gethostbyname", return_value="8.8.8.8"):
        assert _is_private_ip("http://api.example.com/data") is False


# --- _extract_data_with_jmespath ---

def test_extract_list_directly():
    data = [{"a": 1}, {"a": 2}]
    assert _extract_data_with_jmespath(data, None) == data


def test_extract_common_key_data():
    data = {"data": [{"x": 1}], "meta": {}}
    assert _extract_data_with_jmespath(data, None) == [{"x": 1}]


def test_extract_common_key_results():
    data = {"results": [{"x": 1}]}
    assert _extract_data_with_jmespath(data, None) == [{"x": 1}]


def test_extract_with_jmespath_expression():
    data = {"response": {"items": [{"id": 1}, {"id": 2}]}}
    result = _extract_data_with_jmespath(data, "response.items")
    assert len(result) == 2
    assert result[0]["id"] == 1


def test_extract_single_dict_wraps_in_list():
    data = {"key": "value"}
    result = _extract_data_with_jmespath(data, None)
    assert result == [{"key": "value"}]


# --- APIExtractionAgent.process ---

def test_api_agent_missing_url(agent_with_mock_llm):
    state = _make_state()
    result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "No api_url provided" in result["errors"][0]


def test_api_agent_ssrf_private_ip(agent_with_mock_llm):
    with patch("src.agents.api_agent._is_private_ip", return_value=True):
        state = _make_state(api_url="http://10.0.0.1/api", question="Get data")
        result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "private" in result["errors"][0].lower()


def test_api_agent_success(agent_with_mock_llm, tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'[{"id":1,"name":"Alice"}]'
    mock_response.json.return_value = [{"id": 1, "name": "Alice"}]
    mock_response.headers = {}

    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent.requests.get", return_value=mock_response), \
         patch("src.agents.api_agent.ensure_dir"), \
         patch("src.agents.api_agent.settings") as mock_settings:
        mock_settings.upload_dir = str(tmp_path)

        # Need to actually write the CSV for the path to exist
        with patch("src.agents.api_agent.pd.json_normalize") as mock_norm:
            mock_df = MagicMock()
            mock_df.__len__ = lambda self: 1
            mock_df.columns = ["id", "name"]
            mock_norm.return_value = mock_df

            state = _make_state(api_url="https://api.example.com/data", question="Get users")
            result = agent_with_mock_llm.process(state)

    assert "csv_path" in result, f"Expected csv_path, got: {result}"
    assert "api_extract_" in result["csv_path"]


def test_api_agent_timeout(agent_with_mock_llm):
    import requests
    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent.requests.get", side_effect=requests.exceptions.Timeout):
        state = _make_state(api_url="https://api.example.com/slow", question="Get data")
        result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "timed out" in result["errors"][0].lower()


def test_api_agent_http_error(agent_with_mock_llm):
    import requests
    mock_response = MagicMock()
    mock_response.status_code = 403
    exc = requests.exceptions.HTTPError(response=mock_response)

    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent.requests.get", side_effect=exc):
        state = _make_state(api_url="https://api.example.com/forbidden", question="Get data")
        result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "403" in result["errors"][0]


def test_api_agent_empty_response(agent_with_mock_llm):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'[]'
    mock_response.json.return_value = []
    mock_response.headers = {}

    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent.requests.get", return_value=mock_response):
        state = _make_state(api_url="https://api.example.com/empty", question="Get data")
        result = agent_with_mock_llm.process(state)
    assert "errors" in result
    assert "no data" in result["errors"][0].lower()


def test_api_agent_with_bearer_auth(agent_with_mock_llm, tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'[{"id":1}]'
    mock_response.json.return_value = [{"id": 1}]
    mock_response.headers = {}

    with patch("src.agents.api_agent._is_private_ip", return_value=False), \
         patch("src.agents.api_agent.requests.get", return_value=mock_response) as mock_get, \
         patch("src.agents.api_agent.ensure_dir"), \
         patch("src.agents.api_agent.pd.json_normalize") as mock_norm, \
         patch("src.agents.api_agent.settings") as mock_settings:
        mock_settings.upload_dir = str(tmp_path)
        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 1
        mock_df.columns = ["id"]
        mock_norm.return_value = mock_df

        state = _make_state(
            api_url="https://api.example.com/data",
            api_auth={"type": "bearer", "token": "mytoken"},
            question="Get data",
        )
        result = agent_with_mock_llm.process(state)

    # Verify auth header was passed
    call_kwargs = mock_get.call_args
    assert "Authorization" in call_kwargs[1]["headers"]
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer mytoken"
