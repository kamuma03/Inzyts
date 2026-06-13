"""
Unit tests for graph workflow orchestration.

Covers node execution, conditional routing, token tracking, error
propagation, and state transitions.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.workflow.graph import (
    initialize_node,
    restore_cache_node,
    create_phase1_handoff_node,
    data_profiler_node,
    profile_codegen_node,
    profile_validator_node,
    extension_node,
    transition_to_phase2_node,
    strategy_node,
    analysis_codegen_node,
    analysis_validator_node,
    assemble_notebook_node,
    exploratory_conclusions_node,
    rollback_recovery_node,
    route_after_profile_validation,
    route_after_initialize,
    route_after_analysis_validation,
    build_workflow,
)
from src.models.state import AnalysisState, ProfileLock, PipelineMode
from src.models.handoffs import UserIntent
from src.models.cells import NotebookCell
from tests.factories import make_analysis_state


# ---------------------------------------------------------------------------
# Test helpers — collapse the per-test setup that previously dominated this
# file. Both factories return MagicMocks pre-configured with the token
# counters and zeroed running totals that every node touches.
# ---------------------------------------------------------------------------


def make_state(**overrides):
    """Build a make_analysis_state() with the running-totals fields
    every node reads zeroed, plus any per-test overrides."""
    state = make_analysis_state()
    state.total_tokens_used = 0
    state.prompt_tokens_used = 0
    state.completion_tokens_used = 0
    state.errors = []
    # Orchestrator→profiler handoff field (read by data_profiler_node); default
    # to None so tests that don't exercise it don't need to set it explicitly.
    state.profiler_handoff = None
    # Phase-2 rollback snapshot baseline (read by analysis_validator_node's
    # best-score check); mirrors the real AnalysisState default of 0.0.
    state.phase2_best_score = 0.0
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


def make_agent(return_value=None, side_effect=None, start_tokens=100):
    """Build a mock agent matching the BaseAgent surface our nodes touch."""
    agent = MagicMock()
    agent.llm_agent.total_tokens = start_tokens
    agent.llm_agent.prompt_tokens = start_tokens // 2
    agent.llm_agent.completion_tokens = start_tokens - start_tokens // 2
    if side_effect is not None:
        agent.process.side_effect = side_effect
    else:
        agent.process.return_value = return_value if return_value is not None else {}
    return agent


# ---------------------------------------------------------------------------
# Initialize / restore / handoff
# ---------------------------------------------------------------------------


class TestInitializeNode:
    @patch("src.workflow.graph.AgentFactory")
    def test_initialize_node_success(self, mock_factory):
        state = make_state(
            csv_path="data.csv",
            user_intent=UserIntent(query="Analyze data", mode="exploratory", csv_path="data.csv"),
            pipeline_mode=PipelineMode.EXPLORATORY,
            using_cached_profile=False,
        )
        mock_factory.get_agent.return_value = make_agent(return_value={"status": "initialized"})
        result = initialize_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        assert result["total_tokens_used"] >= 0

    @patch("src.workflow.graph.AgentFactory")
    def test_initialize_node_token_tracking(self, mock_factory):
        state = make_state(
            csv_path="data.csv", user_intent=None,
            pipeline_mode=PipelineMode.PREDICTIVE, using_cached_profile=False,
            total_tokens_used=50, prompt_tokens_used=25, completion_tokens_used=25,
        )
        agent = make_agent()

        def increase_tokens(*args, **kwargs):
            agent.llm_agent.total_tokens = 150
            return {"status": "initialized"}
        agent.process.side_effect = increase_tokens
        mock_factory.get_agent.return_value = agent

        result = initialize_node(state)
        assert result["total_tokens_used"] == 100  # 50 base + (150-100) delta


class TestRestoreCacheNode:
    @patch("src.workflow.graph.AgentFactory")
    def test_restore_cache_success(self, mock_factory):
        state = make_state(cache=MagicMock())
        mock_factory.get_agent.return_value = make_agent(return_value={"profile_lock": MagicMock()})
        result = restore_cache_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        assert "total_tokens_used" in result

    @patch("src.workflow.graph.AgentFactory")
    def test_restore_cache_no_cache(self, mock_factory):
        state = make_state(cache=None)
        mock_factory.get_agent.return_value = make_agent(return_value={"error": "No cache"})
        result = restore_cache_node(state)
        assert "total_tokens_used" in result


# ---------------------------------------------------------------------------
# Phase 1 nodes — success + failure paths shared via parametrize
# ---------------------------------------------------------------------------


class TestPhase1Nodes:
    @patch("src.workflow.graph.AgentFactory")
    def test_create_phase1_handoff_node(self, mock_factory):
        state = make_state()
        agent = make_agent(return_value={"handoff": "created"})
        mock_factory.get_agent.return_value = agent
        result = create_phase1_handoff_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        agent.process.assert_called_once_with(state, action="phase1_handoff")
        assert "total_tokens_used" in result

    @patch("src.workflow.graph.AgentFactory")
    def test_data_profiler_node_success(self, mock_factory):
        state = make_state(profiler_outputs=[])
        mock_factory.get_agent.return_value = make_agent(return_value={"handoff": MagicMock()})
        result = data_profiler_node(state)
        mock_factory.get_agent.assert_called_with("data_profiler")
        assert len(result["profiler_outputs"]) == 1
        assert "total_tokens_used" in result

    @patch("src.workflow.graph.AgentFactory")
    def test_profile_codegen_node_success(self, mock_factory):
        state = make_state(profiler_outputs=[MagicMock()], profile_code_outputs=[], phase1_iteration=0)
        mock_factory.get_agent.return_value = make_agent(return_value={"handoff": MagicMock()})
        result = profile_codegen_node(state)
        mock_factory.get_agent.assert_called_with("profile_codegen")
        assert result["phase1_iteration"] == 1

    @patch("src.workflow.graph.AgentFactory")
    @patch("src.workflow.graph.update_issue_frequency")
    def test_profile_validator_node_success(self, mock_update_freq, mock_factory):
        state = make_state(
            profile_code_outputs=[MagicMock()],
            profile_validation_reports=[],
            phase1_quality_trajectory=[],
            phase1_iteration=1,
            csv_path="data.csv",
            pipeline_mode=PipelineMode.PREDICTIVE,
            user_intent=MagicMock(),
            profile_lock=MagicMock(spec=ProfileLock),
        )
        mock_factory.get_agent.return_value = make_agent(return_value={
            "report": MagicMock(),
            "quality_score": 0.9,
            "issues": [],
            "should_lock": True,
            "strategy_handoff": MagicMock(),
        })
        mock_update_freq.return_value = {}
        result = profile_validator_node(state)
        mock_factory.get_agent.assert_called_with("profile_validator")
        assert "profile_lock" in result
        assert len(result["phase1_quality_trajectory"]) == 1


# Failure paths share an identical shape: process() raises → result["errors"]
# ends with "<Label> Crash: ...".
@pytest.mark.parametrize("node, expected_agent, state_extra, crash_prefix", [
    (data_profiler_node,    "data_profiler",     {"profiler_outputs": []}, "DataProfiler Crash"),
    (profile_codegen_node,  "profile_codegen",   {"profiler_outputs": [MagicMock()], "profile_code_outputs": []}, "ProfileCodeGen Crash"),
    (profile_validator_node,"profile_validator", {"profile_code_outputs": [MagicMock()]}, "ProfileValidator Crash"),
    (analysis_codegen_node, "analysis_codegen",  {"strategy_outputs": [MagicMock()]}, "AnalysisCodeGen Crash"),
    (analysis_validator_node,"analysis_validator", {"analysis_code_outputs": [MagicMock()]}, "AnalysisValidator Crash"),
    (exploratory_conclusions_node, "exploratory_conclusions", {}, "ExploratoryConclusions Crash"),
])
@patch("src.workflow.graph.AgentFactory")
def test_node_failure_appends_crash(mock_factory, node, expected_agent, state_extra, crash_prefix):
    state = make_state(**state_extra)
    mock_factory.get_agent.return_value = make_agent(side_effect=Exception(f"{crash_prefix} test"))
    result = node(state)
    assert "errors" in result and crash_prefix in result["errors"][0]


# ---------------------------------------------------------------------------
# Extension node — parametrized over modes
# ---------------------------------------------------------------------------


class TestExtensionNode:
    @pytest.mark.parametrize("mode, expected_agent", [
        (PipelineMode.FORECASTING, "forecasting_extension"),
        (PipelineMode.COMPARATIVE, "comparative_extension"),
        (PipelineMode.DIAGNOSTIC,  "diagnostic_extension"),
    ])
    @patch("src.workflow.graph.AgentFactory")
    def test_extension_node_routes_by_mode(self, mock_factory, mode, expected_agent):
        state = make_state(pipeline_mode=mode)
        agent = make_agent(return_value={"extension_data": expected_agent})
        mock_factory.get_agent.return_value = agent
        result = extension_node(state)
        mock_factory.get_agent.assert_called_with(expected_agent)
        agent.process.assert_called_once_with(state)
        assert result["extension_data"] == expected_agent

    def test_extension_node_no_extension_needed(self):
        # PREDICTIVE / SEGMENTATION / etc. have no pre-strategy extension.
        state = make_state(pipeline_mode=PipelineMode.PREDICTIVE)
        result = extension_node(state)
        assert isinstance(result, dict)

    @patch("src.workflow.graph.AgentFactory")
    def test_extension_node_error_handling(self, mock_factory):
        state = make_state(pipeline_mode=PipelineMode.FORECASTING)
        mock_factory.get_agent.return_value = make_agent(side_effect=Exception("boom"))
        result = extension_node(state)
        # Match the recorded error regardless of phrasing ("Extension <mode>
        # failed" vs a decorator-style "Extension Crash") so the assertion holds
        # across the node's two error-message formats.
        assert "Extension" in result["errors"][0]


# ---------------------------------------------------------------------------
# Phase 2 nodes — strategy mode dispatch is the most repetitive piece
# ---------------------------------------------------------------------------


class TestPhase2Nodes:
    @patch("src.workflow.graph.AgentFactory")
    def test_transition_to_phase2_node(self, mock_factory):
        state = make_state(profile_lock=MagicMock())
        mock_factory.get_agent.return_value = make_agent(return_value={"phase": "2"})
        result = transition_to_phase2_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        assert "total_tokens_used" in result

    @pytest.mark.parametrize("mode, expected_agent", [
        (PipelineMode.PREDICTIVE,       "strategy"),
        (PipelineMode.FORECASTING,      "forecasting_strategy"),
        (PipelineMode.COMPARATIVE,      "comparative_strategy"),
        (PipelineMode.DIAGNOSTIC,       "diagnostic_strategy"),
        (PipelineMode.SEGMENTATION,     "segmentation_strategy"),
    ])
    @patch("src.workflow.graph.AgentFactory")
    def test_strategy_node_dispatch(self, mock_factory, mode, expected_agent):
        profile_lock = MagicMock()
        profile_lock.get_locked_handoff.return_value = MagicMock()
        state = make_state(
            pipeline_mode=mode,
            profile_lock=profile_lock,
            strategy_outputs=[],
            phase2_iteration=0,
        )
        agent = make_agent(return_value={"handoff": MagicMock()})
        mock_factory.get_agent.return_value = agent
        result = strategy_node(state)
        mock_factory.get_agent.assert_called_with(expected_agent)
        agent.process.assert_called_once()
        if mode == PipelineMode.PREDICTIVE:
            assert "strategy_outputs" in result
            assert result["phase2_iteration"] == 1

    @patch("src.workflow.graph.AgentFactory")
    def test_analysis_codegen_node_success(self, mock_factory):
        state = make_state(strategy_outputs=[MagicMock()], analysis_code_outputs=[])
        mock_factory.get_agent.return_value = make_agent(return_value={"handoff": MagicMock()})
        result = analysis_codegen_node(state)
        mock_factory.get_agent.assert_called_with("analysis_codegen")
        assert len(result["analysis_code_outputs"]) == 1

    @patch("src.workflow.graph.AgentFactory")
    def test_analysis_validator_node_success(self, mock_factory):
        state = make_state(
            analysis_code_outputs=[MagicMock()],
            analysis_validation_reports=[],
            phase2_quality_trajectory=[],
            issue_frequency={},
            strategy_outputs=[],
        )
        mock_factory.get_agent.return_value = make_agent(return_value={
            "report": MagicMock(), "quality_score": 0.85,
        })
        result = analysis_validator_node(state)
        mock_factory.get_agent.assert_called_with("analysis_validator")
        assert result["phase2_quality_trajectory"][0] == 0.85


# ---------------------------------------------------------------------------
# Assembly / exploratory / rollback — each is a thin wrapper around the
# orchestrator/agent, so one happy-path test each is sufficient.
# ---------------------------------------------------------------------------


class TestAssemblyNode:
    @patch("src.workflow.graph.AgentFactory")
    def test_assemble_notebook_node(self, mock_factory):
        state = make_state(
            profile_lock=MagicMock(profile_cells=[NotebookCell(cell_type="code", source="print(1)")]),
            analysis_code_outputs=[MagicMock(cells=[NotebookCell(cell_type="markdown", source="# Analysis")])],
            exploratory_conclusions=None,
            phase1_quality_trajectory=[0.9],
            phase2_quality_trajectory=[0.85],
            csv_path="data.csv",
            execution_time=120.5,
            phase1_iteration=2,
            phase2_iteration=1,
            total_tokens_used=1000,
            prompt_tokens_used=600,
            completion_tokens_used=400,
            user_intent=MagicMock(title="Test Title"),
        )
        agent = make_agent(return_value={"notebook_path": "output.ipynb"}, start_tokens=1000)
        mock_factory.get_agent.return_value = agent
        result = assemble_notebook_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        agent.process.assert_called_once()
        assert "total_tokens_used" in result


class TestExploratoryConclusionsNode:
    @patch("src.workflow.graph.AgentFactory")
    def test_exploratory_conclusions_success(self, mock_factory):
        state = make_state()
        agent = make_agent(return_value={"conclusions": "data analysis complete"})
        mock_factory.get_agent.return_value = agent
        result = exploratory_conclusions_node(state)
        mock_factory.get_agent.assert_called_with("exploratory_conclusions")
        agent.process.assert_called_once_with(state)
        assert "total_tokens_used" in result


class TestRollbackRecoveryNode:
    @patch("src.workflow.graph.AgentFactory")
    def test_rollback_recovery_node(self, mock_factory):
        state = make_state()
        agent = make_agent(return_value={"rollback": "complete"})
        mock_factory.get_agent.return_value = agent
        result = rollback_recovery_node(state)
        mock_factory.get_agent.assert_called_with("orchestrator")
        agent.process.assert_called_once_with(state, action="rollback_phase2")
        assert "total_tokens_used" in result


# ---------------------------------------------------------------------------
# Conditional routing — pure functions, no agent mocking needed
# ---------------------------------------------------------------------------


class TestConditionalRouting:
    @pytest.mark.parametrize("mode", [PipelineMode.PREDICTIVE, PipelineMode.EXPLORATORY])
    def test_route_after_profile_validation_lock_granted(self, mode):
        state = make_analysis_state()
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = True
        state.pipeline_mode = mode
        assert route_after_profile_validation(state) == "exploratory_conclusions"

    @pytest.mark.parametrize("route_to, expected", [
        ("DataProfiler",         "data_profiler"),
        ("ProfileCodeGenerator", "profile_codegen"),
        ("Orchestrator",         "end"),
    ])
    def test_route_after_profile_validation_routes(self, route_to, expected):
        state = make_analysis_state()
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = [MagicMock(route_to=route_to)]
        assert route_after_profile_validation(state) == expected

    def test_route_after_profile_validation_default_fallback(self):
        state = make_analysis_state()
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = []
        assert route_after_profile_validation(state) == "profile_codegen"

    def test_route_after_initialize_with_cache(self):
        state = make_analysis_state()
        state.using_cached_profile = True
        state.cache = MagicMock()
        assert route_after_initialize(state) == "restore_cache"

    def test_route_after_initialize_without_cache(self):
        state = make_analysis_state()
        state.using_cached_profile = False
        state.user_intent = MagicMock(db_uri=None, api_url=None, multi_file_input=None)
        assert route_after_initialize(state) == "create_phase1_handoff"

    @pytest.mark.parametrize("route_to, route_reason, expected", [
        ("PHASE_2_COMPLETE",      None,                "assemble_notebook"),
        ("StrategyAgent",         None,                "strategy"),
        ("AnalysisCodeGenerator", None,                "analysis_codegen"),
        ("Orchestrator",          "ROLLBACK_TRIGGERED","rollback_recovery"),
        ("Orchestrator",          "Max iterations",    "assemble_notebook"),
    ])
    def test_route_after_analysis_validation(self, route_to, route_reason, expected):
        state = make_analysis_state()
        state.analysis_validation_reports = [MagicMock(route_to=route_to, route_reason=route_reason)]
        assert route_after_analysis_validation(state) == expected

    def test_route_after_analysis_validation_default_fallback(self):
        state = make_analysis_state()
        state.analysis_validation_reports = []
        assert route_after_analysis_validation(state) == "assemble_notebook"


# ---------------------------------------------------------------------------
# Workflow build smoke-tests
# ---------------------------------------------------------------------------


class TestBuildWorkflow:
    def test_build_workflow_creates_graph(self):
        workflow = build_workflow()
        assert workflow is not None
        assert len(workflow.nodes) > 0

    def test_build_workflow_has_all_nodes(self):
        workflow = build_workflow()
        expected = [
            "initialize", "create_phase1_handoff", "data_profiler", "profile_codegen",
            "profile_validator", "transition_to_phase2", "extension_node", "strategy",
            "analysis_codegen", "analysis_validator", "exploratory_conclusions",
            "restore_cache", "rollback_recovery", "assemble_notebook",
        ]
        for n in expected:
            assert n in workflow.nodes, f"Node {n} not found in workflow"


# ---------------------------------------------------------------------------
# Token tracking + state transitions — the few tests that actually exercise
# delta accumulation rather than just node wiring.
# ---------------------------------------------------------------------------


class TestTokenTracking:
    @patch("src.workflow.graph.AgentFactory")
    def test_token_tracking_single_node(self, mock_factory):
        state = make_state(
            csv_path="data.csv", user_intent=None, pipeline_mode=PipelineMode.PREDICTIVE,
            using_cached_profile=False,
        )
        agent = make_agent()

        def increase(*a, **kw):
            agent.llm_agent.total_tokens = 200
            return {"status": "ok"}
        agent.process.side_effect = increase
        mock_factory.get_agent.return_value = agent

        result = initialize_node(state)
        assert result["total_tokens_used"] == 100  # 200 - 100

    @patch("src.workflow.graph.AgentFactory")
    def test_token_tracking_multiple_nodes(self, mock_factory):
        # Profiler: uses 50 tokens.
        profiler = make_agent()

        def profiler_side(*a, **kw):
            profiler.llm_agent.total_tokens = 150
            return {"handoff": MagicMock()}
        profiler.process.side_effect = profiler_side

        # Codegen: uses 30 tokens.
        codegen = make_agent(start_tokens=200)

        def codegen_side(*a, **kw):
            codegen.llm_agent.total_tokens = 230
            return {"handoff": MagicMock()}
        codegen.process.side_effect = codegen_side

        mock_factory.get_agent.side_effect = lambda name: {
            "data_profiler": profiler, "profile_codegen": codegen,
        }.get(name, MagicMock())

        state1 = make_state(profiler_outputs=[])
        result1 = data_profiler_node(state1)
        assert result1["total_tokens_used"] == 50

        state2 = make_state(
            profiler_outputs=[result1.get("handoff")],
            profile_code_outputs=[],
            phase1_iteration=0,
            total_tokens_used=50, prompt_tokens_used=25, completion_tokens_used=25,
        )
        result2 = profile_codegen_node(state2)
        assert result2["total_tokens_used"] == 80  # 50 + 30


class TestErrorPropagation:
    @patch("src.workflow.graph.AgentFactory")
    def test_error_propagation_preserves_state(self, mock_factory):
        state = make_state(
            profiler_outputs=[],
            total_tokens_used=100, prompt_tokens_used=60, completion_tokens_used=40,
            errors=["Previous error"],
        )
        mock_factory.get_agent.return_value = make_agent(
            side_effect=Exception("New error"), start_tokens=200,
        )
        result = data_profiler_node(state)
        assert result["total_tokens_used"] >= 100
        assert "errors" in result


class TestStateTransitions:
    @patch("src.workflow.graph.AgentFactory")
    @patch("src.workflow.graph.update_issue_frequency")
    def test_state_transition_phase1_to_phase2(self, mock_update_freq, mock_factory):
        state = make_state(
            profile_code_outputs=[MagicMock()],
            profile_validation_reports=[],
            phase1_quality_trajectory=[],
            phase1_iteration=1,
            csv_path="data.csv",
            pipeline_mode=PipelineMode.PREDICTIVE,
            user_intent=MagicMock(),
            total_tokens_used=100, prompt_tokens_used=60, completion_tokens_used=40,
            profile_lock=MagicMock(spec=ProfileLock),
        )
        mock_factory.get_agent.return_value = make_agent(return_value={
            "report": MagicMock(), "quality_score": 0.9, "issues": [],
            "should_lock": True, "strategy_handoff": MagicMock(),
        }, start_tokens=200)
        mock_update_freq.return_value = {}

        result = profile_validator_node(state)
        state.profile_lock.grant_lock.assert_called_once()
        assert state.profile_lock.is_locked.return_value or result.get("profile_lock")

    @patch("src.workflow.graph.AgentFactory")
    def test_state_transition_phase1_iteration_increment(self, mock_factory):
        state = make_state(
            profiler_outputs=[MagicMock()], profile_code_outputs=[], phase1_iteration=2,
        )
        mock_factory.get_agent.return_value = make_agent(return_value={"handoff": MagicMock()})
        result = profile_codegen_node(state)
        assert result["phase1_iteration"] == 3

    @patch("src.workflow.graph.AgentFactory")
    def test_state_transition_phase2_iteration_increment(self, mock_factory):
        profile_lock = MagicMock()
        profile_lock.get_locked_handoff.return_value = MagicMock()
        state = make_state(
            pipeline_mode=PipelineMode.PREDICTIVE,
            profile_lock=profile_lock, strategy_outputs=[], phase2_iteration=1,
        )
        mock_factory.get_agent.return_value = make_agent(return_value={"handoff": MagicMock()})
        result = strategy_node(state)
        assert result["phase2_iteration"] == 2
