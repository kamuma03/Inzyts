"""Unit tests for the per-phase token-attribution helper in graph.py."""

from src.models.state import AnalysisState
from src.workflow.graph import _attribute_tokens


def test_attribute_phase1_sets_global_and_phase_buckets():
    state = AnalysisState()
    updates: dict = {}
    _attribute_tokens(updates, state, total=100, prompt=60, completion=40, phase="phase1")
    assert updates["total_tokens_used"] == 100
    assert updates["prompt_tokens_used"] == 60
    assert updates["completion_tokens_used"] == 40
    assert updates["phase1_tokens_used"] == 100
    assert updates["phase1_prompt_tokens"] == 60
    assert updates["phase1_completion_tokens"] == 40
    # Phase 2 / extensions buckets are untouched.
    assert "phase2_tokens_used" not in updates
    assert "extensions_tokens_used" not in updates


def test_attribute_phase2_routes_to_phase2_bucket():
    state = AnalysisState()
    updates: dict = {}
    _attribute_tokens(updates, state, total=200, prompt=120, completion=80, phase="phase2")
    assert updates["phase2_tokens_used"] == 200
    assert updates["phase2_prompt_tokens"] == 120
    assert updates["phase2_completion_tokens"] == 80
    # phase1 untouched
    assert "phase1_tokens_used" not in updates


def test_attribute_extensions_routes_to_extensions_bucket():
    state = AnalysisState()
    updates: dict = {}
    _attribute_tokens(updates, state, total=50, prompt=30, completion=20, phase="extensions")
    assert updates["extensions_tokens_used"] == 50
    assert updates["extensions_prompt_tokens"] == 30
    assert updates["extensions_completion_tokens"] == 20


def test_helper_adds_to_existing_state_counters():
    state = AnalysisState(
        total_tokens_used=500,
        prompt_tokens_used=300,
        completion_tokens_used=200,
        phase1_tokens_used=400,
        phase1_prompt_tokens=240,
        phase1_completion_tokens=160,
    )
    updates: dict = {}
    _attribute_tokens(updates, state, total=100, prompt=60, completion=40, phase="phase1")
    assert updates["total_tokens_used"] == 600
    assert updates["phase1_tokens_used"] == 500
    assert updates["phase1_prompt_tokens"] == 300


def test_sum_invariant_holds():
    """After attributing across all three phases, the sum of phase buckets
    equals the global total — the invariant the cost endpoint relies on."""
    # Simulate the workflow's state evolution: each phase's helper call
    # only writes its own bucket, so we accumulate them by carrying state forward.
    state = AnalysisState()
    u1: dict = {}
    _attribute_tokens(u1, state, total=100, prompt=60, completion=40, phase="phase1")
    state = state.model_copy(update=u1)

    u2: dict = {}
    _attribute_tokens(u2, state, total=50, prompt=30, completion=20, phase="extensions")
    state = state.model_copy(update=u2)

    u3: dict = {}
    _attribute_tokens(u3, state, total=200, prompt=120, completion=80, phase="phase2")
    state = state.model_copy(update=u3)

    assert state.total_tokens_used == 350
    assert (
        state.phase1_tokens_used
        + state.extensions_tokens_used
        + state.phase2_tokens_used
        == state.total_tokens_used
    )
