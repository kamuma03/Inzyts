"""
Tests for ComparativeExtensionAgent.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

from src.agents.extensions.comparative_extension_agent import ComparativeExtensionAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import ComparativeExtension


def _make_col_profile(name, detected_type, unique_count=5):
    p = MagicMock()
    p.name = name
    p.detected_type = detected_type
    p.unique_count = unique_count
    return p


def _make_state(csv_data=None, profile_locked=True, col_profiles=None):
    state = MagicMock(spec=AnalysisState)
    state.csv_data = csv_data
    state.user_intent = MagicMock()
    state.user_intent.model_dump.return_value = {"analysis_question": "Compare groups"}

    profile = MagicMock()
    profile.column_profiles = col_profiles or []
    state.profile_lock = MagicMock()
    state.profile_lock.is_locked.return_value = profile_locked
    state.profile_lock.get_locked_handoff.return_value = profile if profile_locked else None
    return state


def _make_comp_response(**overrides):
    """Build a valid ComparativeExtension with sensible defaults, overridden by kwargs."""
    defaults = dict(
        group_column="group",
        group_values=["A", "B"],
        baseline_group="A",
        treatment_groups=["B"],
        group_sizes={"A": 3, "B": 3},
        balance_ratio=1.0,
        is_balanced=True,
        numeric_metrics=["value"],
        categorical_metrics=[],
        recommended_primary_metric="value",
        recommended_tests=[],
        multiple_comparison_correction="bonferroni",
        created_at=datetime.now().isoformat(),
        csv_hash="abc123",
    )
    defaults.update(overrides)
    return ComparativeExtension(**defaults)


@pytest.fixture
def agent():
    with patch("src.agents.base.BaseAgent.__init__", lambda self, **kw: None):
        a = object.__new__(ComparativeExtensionAgent)
        a.name = "ComparativeExtensionAgent"
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
# Categorical candidate detection
# ---------------------------------------------------------------------------

class TestCategoricalDetection:

    def test_finds_categorical_candidates(self, agent):
        csv_data = {
            "group": ["A", "B", "A", "B", "A", "B"],
            "value": [10, 20, 15, 25, 12, 22],
        }
        col_profiles = [
            _make_col_profile("group", "categorical", unique_count=2),
            _make_col_profile("value", "numeric_continuous"),
        ]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        comp_response = _make_comp_response(
            group_column="group",
            group_values=["A", "B"],
            baseline_group="A",
            treatment_groups=["B"],
            group_sizes={"A": 3, "B": 3},
            balance_ratio=1.0,
            is_balanced=True,
            numeric_metrics=["value"],
        )
        agent.llm_agent.invoke_with_json.return_value = comp_response.model_dump_json()

        result = agent.process(state)
        assert "comparative_extension" in result
        assert result["confidence"] == 1.0

    def test_high_cardinality_excluded(self, agent):
        """Columns with unique_count >= 20 should not be candidates."""
        csv_data = {"id": list(range(30)), "val": list(range(30))}
        col_profiles = [
            _make_col_profile("id", "categorical", unique_count=30),
            _make_col_profile("val", "numeric_continuous"),
        ]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        comp_response = _make_comp_response(
            group_column="id",  # LLM might pick it, but no candidates found in data
            group_values=[],
            baseline_group="0",
            treatment_groups=[],
            group_sizes={},
            balance_ratio=0.0,
            is_balanced=False,
            numeric_metrics=["val"],
        )
        agent.llm_agent.invoke_with_json.return_value = comp_response.model_dump_json()

        result = agent.process(state)
        # Agent still returns a result (LLM decides), but group_summaries is empty
        assert "comparative_extension" in result


# ---------------------------------------------------------------------------
# Balance ratio calculation and hydration
# ---------------------------------------------------------------------------

class TestBalanceRatio:

    def test_balanced_groups(self, agent):
        csv_data = {
            "treatment": ["control"] * 50 + ["treatment"] * 50,
            "outcome": list(range(100)),
        }
        col_profiles = [
            _make_col_profile("treatment", "categorical_binary", unique_count=2),
            _make_col_profile("outcome", "numeric_continuous"),
        ]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        comp_response = _make_comp_response(
            group_column="treatment",
            group_values=["control", "treatment"],
            baseline_group="control",
            treatment_groups=["treatment"],
            group_sizes={},
            balance_ratio=0.0,
            is_balanced=False,
            numeric_metrics=["outcome"],
        )
        agent.llm_agent.invoke_with_json.return_value = comp_response.model_dump_json()

        result = agent.process(state)
        ext = result["comparative_extension"]
        # Hydration should set balance_ratio = 50/50 = 1.0
        assert ext.balance_ratio == 1.0
        assert ext.is_balanced is True
        assert ext.group_sizes == {"control": 50, "treatment": 50}

    def test_imbalanced_groups(self, agent):
        csv_data = {
            "group": ["A"] * 10 + ["B"] * 90,
            "metric": list(range(100)),
        }
        col_profiles = [
            _make_col_profile("group", "categorical", unique_count=2),
            _make_col_profile("metric", "numeric_continuous"),
        ]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)

        comp_response = _make_comp_response(
            group_column="group",
            group_values=["A", "B"],
            baseline_group="A",
            treatment_groups=["B"],
            group_sizes={},
            balance_ratio=0.0,
            is_balanced=True,
            numeric_metrics=["metric"],
        )
        agent.llm_agent.invoke_with_json.return_value = comp_response.model_dump_json()

        result = agent.process(state)
        ext = result["comparative_extension"]
        # 10/90 ~ 0.111
        assert ext.balance_ratio < 0.4
        assert ext.is_balanced is False


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

class TestLLMInteraction:

    def test_llm_invalid_json_raises(self, agent):
        csv_data = {"g": ["A", "B"], "v": [1, 2]}
        col_profiles = [
            _make_col_profile("g", "categorical", unique_count=2),
            _make_col_profile("v", "numeric_continuous"),
        ]
        state = _make_state(csv_data=csv_data, col_profiles=col_profiles)
        agent.llm_agent.invoke_with_json.return_value = "not json"

        with pytest.raises(Exception):
            agent.process(state)
