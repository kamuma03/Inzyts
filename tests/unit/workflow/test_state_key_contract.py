"""Regression guard against silently-dropped LangGraph state keys.

LangGraph's state reducer drops any key returned by a node that is not a
declared field on ``AnalysisState`` — no error, no warning. Three production
features (the extension subsystem, the orchestrator→profiler handoff, and the
Phase-2 rollback) were silently inert for exactly this reason: a node returned a
dict whose key did not exist on the state schema, so the value vanished.

These tests statically scan the workflow graph and the orchestrator for the
string keys they emit into state and assert every one is a real ``AnalysisState``
field (or an explicitly-allowlisted node-local key that a node consumes itself
and never persists). If someone adds ``return {"new_thing": ...}`` from a node
without adding ``new_thing`` to the state model, this test fails loudly instead
of the feature dying in silence.
"""

import ast
from pathlib import Path

import pytest

from src.models.state import AnalysisState

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_PY = REPO_ROOT / "src" / "workflow" / "graph.py"
ORCHESTRATOR_PY = REPO_ROOT / "src" / "agents" / "orchestrator.py"

STATE_FIELDS = set(AnalysisState.model_fields.keys())

# Keys a node returns but deliberately consumes locally — they are unpacked by
# the calling node (e.g. ``result.get("handoff")``) and never written straight
# into state, so they are exempt from the "must be a state field" rule.
NODE_LOCAL_KEYS = {
    "handoff",          # profiler / codegen output, appended into *_outputs lists
    "report",           # validation report, appended into *_reports lists
    "quality_score",    # consumed to build the quality trajectory
    "issues",           # consumed by update_issue_frequency
    "should_lock",      # consumed to build the profile lock
    "confidence",       # advisory signal, never persisted
    "error",            # surfaced into errors list by the node, not stored as-is
    "updated_csv_path", # mapped onto csv_path by the node
    "csv_data",         # legacy: orchestrator clears it, node ignores the key
}


def _string_keys_in_returned_dicts(source_path: Path) -> set[str]:
    """Collect constant string keys from every ``return {<dict literal>}``."""
    tree = ast.parse(source_path.read_text())
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _subscript_assigned_keys(source_path: Path) -> set[str]:
    """Collect keys from ``updates["x"] = ...`` style assignments."""
    tree = ast.parse(source_path.read_text())
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if isinstance(node.slice.value, str):
                keys.add(node.slice.value)
    return keys


def test_graph_subscript_assignments_are_state_fields():
    """Every ``updates["key"] = ...`` in graph.py must target a real field."""
    assigned = _subscript_assigned_keys(GRAPH_PY)
    # Restrict to keys that look like state writes (intersect with the union of
    # state fields and node-local keys; flag anything outside both).
    unknown = assigned - STATE_FIELDS - NODE_LOCAL_KEYS
    # Subscript scan also catches unrelated dict indexing (e.g. result["..."]);
    # only fail on keys that are clearly intended as state writes — i.e. ones
    # that collide with neither a known field nor a documented local key AND are
    # assigned via the `updates[...]` target specifically.
    updates_writes = {
        n.slice.value
        for n in ast.walk(ast.parse(GRAPH_PY.read_text()))
        if isinstance(n, ast.Subscript)
        and isinstance(n.slice, ast.Constant)
        and isinstance(n.slice.value, str)
        and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name)
        and n.value.id == "updates"
    }
    bad = updates_writes - STATE_FIELDS
    assert not bad, (
        f"graph.py writes updates[...] keys that are not AnalysisState fields "
        f"(LangGraph will silently drop them): {sorted(bad)}"
    )


def test_orchestrator_returned_keys_are_state_fields_or_local():
    """Orchestrator action results are blind-merged into state by their nodes
    (``updates.update(result)``), so every returned dict key must be a state
    field or an allowlisted node-local key."""
    returned = _string_keys_in_returned_dicts(ORCHESTRATOR_PY)
    bad = returned - STATE_FIELDS - NODE_LOCAL_KEYS
    assert not bad, (
        f"orchestrator.py returns dict keys that are neither AnalysisState "
        f"fields nor documented node-local keys — these are silently dropped "
        f"by LangGraph. Add them to the state model or to NODE_LOCAL_KEYS if "
        f"intentionally ephemeral: {sorted(bad)}"
    )


@pytest.mark.parametrize(
    "field",
    [
        "profiler_handoff",      # H-4: orchestrator → profiler handoff
        "phase2_best_score",     # H-5: rollback snapshot
        "phase2_best_strategy",
        "phase2_best_code",
        "forecasting_extension",  # C-1: extension outputs
        "comparative_extension",
        "diagnostic_extension",
    ],
)
def test_critical_handoff_fields_exist(field):
    """Lock in the specific fields whose absence caused silent feature death."""
    assert field in STATE_FIELDS, f"AnalysisState lost the {field!r} field"
