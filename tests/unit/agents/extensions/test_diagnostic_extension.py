"""
Tests for DiagnosticExtensionAgent.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from src.agents.extensions.diagnostic_extension_agent import DiagnosticExtensionAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import DiagnosticExtension


def _make_col_profile(name, detected_type, unique_count=10):
    p = MagicMock()
    p.name = name
    p.detected_type = detected_type
    p.unique_count = unique_count
    return p


def _make_state(csv_data=None, profile_locked=True, col_profiles=None):
    state = MagicMock(spec=AnalysisState)
    state.csv_data = csv_data
    state.user_intent = MagicMock()
    state.user_intent.model_dump.return_value = {"analysis_question": "Why did sales drop?"}

    profile = MagicMock()
    profile.column_profiles = col_profiles or []
    state.profile_lock = MagicMock()
    state.profile_lock.is_locked.return_value = profile_locked
    state.profile_lock.get_locked_handoff.return_value = profile if profile_locked else None
    return state


def _make_diag_response(**overrides):
    """Build a valid DiagnosticExtension with sensible defaults, overridden by kwargs."""
    defaults = dict(
        has_temporal_data=False,
        metric_columns=["metric_a"],
        primary_metric="metric_a",
        metric_direction="higher_is_better",
        dimension_columns=[],
        change_points_detected=[],
        anomalies_detected=[],
        recommended_analysis=[],
        created_at=datetime.now().isoformat(),
        csv_hash="abc123",
    )
    defaults.update(overrides)
    return DiagnosticExtension(**defaults)


@pytest.fixture
def agent():
    with patch("src.agents.base.BaseAgent.__init__", lambda self, **kw: None):
        a = object.__new__(DiagnosticExtensionAgent)
        a.name = "DiagnosticExtensionAgent"
        a.llm_agent = MagicMock()
        a.system_prompt = ""
        return a


# ---------------------------------------------------------------------------
# Guard clauses
# ---------------------------------------------------------------------------

class TestGuardClauses:

    def test_no_profile_lock(self, agent):
        state = _make_state(profile_locked=False)
        result = agent.process(state)
        assert "error" in result

    def test_no_csv_data(self, agent):
        state = _make_state(csv_data=None)
        result = agent.process(state)
        assert "error" in result


# ---------------------------------------------------------------------------
# Non-temporal anomaly detection
# ---------------------------------------------------------------------------

class TestNonTemporalAnomalies:

    def test_non_temporal_z_score_detection(self, agent):
        """Numeric columns with extreme outliers should be detected."""
        # Create data with clear outlier
        np.random.seed(42)
        normal_data = np.random.normal(100, 10, 100).tolist()
        normal_data[0] = 500  # Extreme outlier (Z > 3)

        csv_data = {"metric_a": normal_data}
        col_profiles = [_make_col_profile("metric_a", "numeric_continuous")]

        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        # Mock LLM response
        diag_response = _make_diag_response(
            has_temporal_data=False,
            metric_columns=["metric_a"],
            primary_metric="metric_a",
        )
        agent.llm_agent.invoke_with_json.return_value = diag_response.model_dump_json()

        result = agent.process(state)
        assert "diagnostic_extension" in result
        assert result["confidence"] == 1.0


# ---------------------------------------------------------------------------
# Temporal analysis
# ---------------------------------------------------------------------------

class TestTemporalAnalysis:

    def test_temporal_data_with_change_point(self, agent):
        """Data with a date column and big shift should detect change points."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        # First 15 days: low values, next 15: high values (>50% shift)
        values = [10.0] * 15 + [100.0] * 15

        csv_data = {
            "date": [str(d) for d in dates],
            "sales": values,
        }
        col_profiles = [
            _make_col_profile("date", "datetime"),
            _make_col_profile("sales", "numeric_continuous"),
        ]

        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        diag_response = _make_diag_response(
            has_temporal_data=True,
            temporal_column="date",
            metric_columns=["sales"],
            primary_metric="sales",
        )
        agent.llm_agent.invoke_with_json.return_value = diag_response.model_dump_json()

        result = agent.process(state)
        assert "diagnostic_extension" in result
        # LLM was called with context that includes change point info
        call_args = agent.llm_agent.invoke_with_json.call_args
        assert "change points" in str(call_args).lower() or "anomalies" in str(call_args).lower()

    def test_temporal_data_with_z_score_anomaly(self, agent):
        """Temporal data with extreme Z-score outliers."""
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        np.random.seed(42)
        values = np.random.normal(100, 5, 50).tolist()
        values[25] = 500  # Extreme outlier

        csv_data = {
            "date": [str(d) for d in dates],
            "revenue": values,
        }
        col_profiles = [
            _make_col_profile("date", "datetime"),
            _make_col_profile("revenue", "numeric_continuous"),
        ]

        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        diag_response = _make_diag_response(
            has_temporal_data=True,
            temporal_column="date",
            metric_columns=["revenue"],
            primary_metric="revenue",
        )
        agent.llm_agent.invoke_with_json.return_value = diag_response.model_dump_json()

        result = agent.process(state)
        assert "diagnostic_extension" in result


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

class TestLLMInteraction:

    def test_llm_called_with_context(self, agent):
        csv_data = {"val": [1, 2, 3, 4, 5]}
        col_profiles = [_make_col_profile("val", "numeric_continuous")]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        diag_response = _make_diag_response(
            metric_columns=["val"],
            primary_metric="val",
        )
        agent.llm_agent.invoke_with_json.return_value = diag_response.model_dump_json()

        result = agent.process(state)
        agent.llm_agent.invoke_with_json.assert_called_once()

    def test_llm_invalid_json_raises(self, agent):
        csv_data = {"val": [1, 2, 3]}
        col_profiles = [_make_col_profile("val", "numeric_continuous")]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        agent.llm_agent.invoke_with_json.return_value = "not valid json"

        with pytest.raises(Exception):
            agent.process(state)
