"""
Main LangGraph workflow for the Multi-Agent Data Analysis System.

This module defines the stateful execution graph that orchestrates the
interaction between all agents. It implements a two-phase architecture:
1. Phase 1: Data Understanding (Profiling, Code Gen, Validation)
2. Phase 2: Analysis & Modeling (Strategy, Code Gen, Validation)

The workflow supports:
- Recursive improvement loops within phases.
- Cross-phase constraints (Profile Lock).
- Rollback mechanisms for quality degradation.
- Conditional routing based on validation feedback.
"""

import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Dict, Iterator, Literal

from langgraph.graph import END, StateGraph

from src.config import settings
from src.models.handoffs import FinalAssemblyHandoff, PipelineMode
from src.models.state import AnalysisState
from src.utils.logger import get_logger
from src.workflow.agent_factory import AgentFactory
from src.workflow.routing import update_issue_frequency

logger = get_logger()

Phase = Literal["phase1", "phase2", "extensions"]


def _attribute_tokens(
    updates: Dict[str, Any],
    state: AnalysisState,
    total: int,
    prompt: int,
    completion: int,
    phase: Phase,
) -> None:
    """Add token deltas to the global counters and a phase-specific bucket.

    The sum of the three phase buckets equals the global ``total_tokens_used``
    (invariant verified by the cost endpoint). ``getattr(..., 0)`` keeps the
    helper robust against partial test mocks.
    """
    updates["total_tokens_used"] = state.total_tokens_used + total
    updates["prompt_tokens_used"] = state.prompt_tokens_used + prompt
    updates["completion_tokens_used"] = state.completion_tokens_used + completion
    for suffix, delta in (
        ("tokens_used", total),
        ("prompt_tokens", prompt),
        ("completion_tokens", completion),
    ):
        key = f"{phase}_{suffix}"
        updates[key] = getattr(state, key, 0) + delta


@contextmanager
def _track(
    agent: Any, state: AnalysisState, phase: Phase
) -> Iterator[Dict[str, Any]]:
    """Context manager: snapshot tokens, yield an updates dict, and on exit
    attribute the delta to ``phase``.

    Usage::

        with _track(agent, state, "phase1") as updates:
            result = agent.process(state, ...)
            updates.update(result)  # caller decides what state changes survive
        return updates

    The caller mutates ``updates`` directly. On normal exit *and* on
    exception, the token delta is recorded so failure paths still attribute
    their LLM cost (matches the previous try/except behaviour).
    """
    a = agent.llm_agent
    start_total, start_prompt, start_completion = (
        a.total_tokens, a.prompt_tokens, a.completion_tokens,
    )
    updates: Dict[str, Any] = {}
    try:
        yield updates
    finally:
        _attribute_tokens(
            updates, state,
            a.total_tokens - start_total,
            a.prompt_tokens - start_prompt,
            a.completion_tokens - start_completion,
            phase,
        )


# ============================================================================
# Node Functions
# ============================================================================


def initialize_node(state: AnalysisState) -> Dict[str, Any]:
    """Initialize the workflow execution (Orchestrator setup → Phase 1)."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    with _track(orchestrator, state, "phase1") as updates:
        result = orchestrator.process(
            state,
            action="initialize",
            csv_path=state.csv_path,
            user_intent=state.user_intent.model_dump() if state.user_intent else None,
            mode=state.pipeline_mode,
            use_cache=state.using_cached_profile,
        )
        if isinstance(result, dict):
            updates.update(result)
    logger.log_execution_time("initialize_node", time.time() - start_time)
    return updates


def restore_cache_node(state: AnalysisState) -> Dict[str, Any]:
    """Unlock the workflow using a cached profile."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    with _track(orchestrator, state, "phase1") as updates:
        result = orchestrator.process(state, action="restore_cache")
        if isinstance(result, dict):
            updates.update(result)
    logger.log_execution_time("restore_cache_node", time.time() - start_time)
    return updates


def create_phase1_handoff_node(state: AnalysisState) -> Dict[str, Any]:
    """Orchestrator packages CSV preview + intent for the Data Profiler."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    with _track(orchestrator, state, "phase1") as updates:
        result = orchestrator.process(state, action="phase1_handoff")
        if isinstance(result, dict):
            updates.update(result)
    logger.log_execution_time("create_phase1_handoff_node", time.time() - start_time)
    return updates


def data_profiler_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Data Profiler — type/quality EDA → ProfilerToCodeGenHandoff."""
    start_time = time.time()
    data_profiler = AgentFactory.get_agent("data_profiler")
    in_handoff = state.profiler_outputs[-1] if state.profiler_outputs else None
    with _track(data_profiler, state, "phase1") as updates:
        try:
            result = data_profiler.process(state, handoff=in_handoff)
            outputs = list(state.profiler_outputs)
            if result.get("handoff"):
                outputs.append(result["handoff"])
            updates["profiler_outputs"] = outputs
            if result.get("updated_csv_path"):
                updates["csv_path"] = result["updated_csv_path"]
            logger.log_execution_time("data_profiler_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("data_profiler_node (FAILED)", time.time() - start_time)
            logger.critical(f"DataProfiler Node crashed: {e}", exc_info=True)
            updates["errors"] = state.errors + [f"DataProfiler Crash: {str(e)}"]
    return updates


def profile_codegen_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Profile Code Generator — spec → notebook cells."""
    start_time = time.time()
    spec = state.profiler_outputs[-1] if state.profiler_outputs else None
    profile_codegen = AgentFactory.get_agent("profile_codegen")
    with _track(profile_codegen, state, "phase1") as updates:
        try:
            result = profile_codegen.process(state, specification=spec)
            code_outputs = list(state.profile_code_outputs)
            if result.get("handoff"):
                code_outputs.append(result["handoff"])
            updates["profile_code_outputs"] = code_outputs
            updates["phase1_iteration"] = state.phase1_iteration + 1
            logger.log_execution_time("profile_codegen_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("profile_codegen_node (FAILED)", time.time() - start_time)
            updates["errors"] = state.errors + [f"ProfileCodeGen Crash: {str(e)}"]
    return updates


def profile_validator_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Profile Validator — sandbox-execute, score, possibly lock."""
    profile_validator = AgentFactory.get_agent("profile_validator")
    code_handoff = state.profile_code_outputs[-1] if state.profile_code_outputs else None
    with _track(profile_validator, state, "phase1") as updates:
        try:
            result = profile_validator.process(state, code_handoff=code_handoff)

            reports = list(state.profile_validation_reports)
            if result.get("report"):
                reports.append(result["report"])

            trajectory = list(state.phase1_quality_trajectory)
            trajectory.append(result.get("quality_score", 0.0))

            profile_lock = state.profile_lock
            if result.get("should_lock"):
                profile_lock.grant_lock(
                    cells=code_handoff.cells if code_handoff else [],
                    handoff=result.get("strategy_handoff"),
                    quality_score=result.get("quality_score", 0.0),
                    report=result.get("report"),
                    iteration=state.phase1_iteration,
                )

            updates["profile_validation_reports"] = reports
            updates["phase1_quality_trajectory"] = trajectory
            updates["issue_frequency"] = update_issue_frequency(state, result.get("issues", []))
            updates["profile_lock"] = profile_lock
        except Exception as e:
            updates["errors"] = state.errors + [f"ProfileValidator Crash: {str(e)}"]
    return updates


_EXTENSION_AGENTS = {
    PipelineMode.FORECASTING: "forecasting_extension",
    PipelineMode.COMPARATIVE: "comparative_extension",
    PipelineMode.DIAGNOSTIC: "diagnostic_extension",
}


def extension_node(state: AnalysisState) -> Dict[str, Any]:
    """Run mode-specific pre-strategy extension (forecasting / A-B / diagnostic)."""
    start_time = time.time()
    mode = state.pipeline_mode
    mode_val = mode.value if mode else "unknown"
    agent_name = _EXTENSION_AGENTS.get(mode)
    if agent_name is None:
        logger.debug(f"extension_node: no extension agent registered for mode '{mode_val}', skipping.")
        return {}

    agent = AgentFactory.get_agent(agent_name)
    with _track(agent, state, "extensions") as updates:
        try:
            result = agent.process(state)
            if isinstance(result, dict):
                updates.update(result)
            logger.log_execution_time(f"extension_node ({mode_val})", time.time() - start_time)
        except Exception as e:
            logger.error(f"Extension Agent {mode_val} failed: {e}")
            updates["errors"] = state.errors + [f"Extension {mode_val} failed: {e}"]
    return updates


def _llm_delta(agent: Any, snapshot: tuple) -> tuple:
    """Return (total, prompt, completion) deltas since `snapshot`."""
    a = agent.llm_agent
    return (a.total_tokens - snapshot[0], a.prompt_tokens - snapshot[1], a.completion_tokens - snapshot[2])


def _llm_snapshot(agent: Any) -> tuple:
    a = agent.llm_agent
    return (a.total_tokens, a.prompt_tokens, a.completion_tokens)


def transition_to_phase2_node(state: AnalysisState) -> Dict[str, Any]:
    """Phase-1→2 transition. save_cache cost is phase1; transition cost is phase2."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")

    # Phase-1 accounting: the save-cache call.
    save_delta = (0, 0, 0)
    if state.profile_lock and state.profile_lock.is_locked():
        snap = _llm_snapshot(orchestrator)
        orchestrator.process(state, action="save_cache")
        save_delta = _llm_delta(orchestrator, snap)

    # Phase-2 accounting: the transition itself.
    snap = _llm_snapshot(orchestrator)
    result = orchestrator.process(state, action="transition_to_phase2")
    transition_delta = _llm_delta(orchestrator, snap)

    updates: Dict[str, Any] = dict(result) if isinstance(result, dict) else {}
    _attribute_tokens(updates, state, *save_delta, "phase1")
    # _attribute_tokens has now written totals = state + save_delta; layer
    # the transition delta on top and bucket it under phase2.
    for key, delta in (
        ("total_tokens_used", transition_delta[0]),
        ("prompt_tokens_used", transition_delta[1]),
        ("completion_tokens_used", transition_delta[2]),
    ):
        updates[key] = updates.get(key, getattr(state, key, 0)) + delta
    for suffix, delta in (
        ("tokens_used", transition_delta[0]),
        ("prompt_tokens", transition_delta[1]),
        ("completion_tokens", transition_delta[2]),
    ):
        key = f"phase2_{suffix}"
        updates[key] = getattr(state, key, 0) + delta

    # Prune Phase 1 iteration history — profile lock has everything Phase 2 needs.
    for key in ("profiler_outputs", "profile_code_outputs", "profile_validation_reports"):
        items = getattr(state, key, [])
        if len(items) > 1:
            updates[key] = items[-1:]

    logger.log_execution_time("transition_to_phase2_node", time.time() - start_time)
    return updates


_STRATEGY_AGENTS = {
    PipelineMode.FORECASTING: "forecasting_strategy",
    PipelineMode.COMPARATIVE: "comparative_strategy",
    PipelineMode.DIAGNOSTIC: "diagnostic_strategy",
    PipelineMode.SEGMENTATION: "segmentation_strategy",
    PipelineMode.DIMENSIONALITY: "dimensionality_strategy",
}


def strategy_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Strategy Agent (mode-specific) over the locked profile."""
    start_time = time.time()
    agent_name = _STRATEGY_AGENTS.get(state.pipeline_mode, "strategy")
    agent = AgentFactory.get_agent(agent_name)
    profile_handoff = state.profile_lock.get_locked_handoff()
    with _track(agent, state, "phase2") as updates:
        try:
            result = agent.process(state, profile_handoff=profile_handoff)
            outputs = list(state.strategy_outputs)
            if result.get("handoff"):
                outputs.append(result["handoff"])
            updates["strategy_outputs"] = outputs
            updates["phase2_iteration"] = state.phase2_iteration + 1
            logger.log_execution_time("strategy_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("strategy_node (FAILED)", time.time() - start_time)
            updates["errors"] = state.errors + [f"Strategy Crash: {str(e)}"]
    return updates


def analysis_codegen_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Analysis Code Generator — strategy → executable code cells."""
    start_time = time.time()
    strategy = state.strategy_outputs[-1] if state.strategy_outputs else None
    agent = AgentFactory.get_agent("analysis_codegen")
    with _track(agent, state, "phase2") as updates:
        try:
            result = agent.process(state, strategy=strategy)
            outputs = list(state.analysis_code_outputs)
            if result.get("handoff"):
                outputs.append(result["handoff"])
            updates["analysis_code_outputs"] = outputs
            logger.log_execution_time("analysis_codegen_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("analysis_codegen_node (FAILED)", time.time() - start_time)
            updates["errors"] = state.errors + [f"AnalysisCodeGen Crash: {str(e)}"]
    return updates


def analysis_validator_node(state: AnalysisState) -> Dict[str, Any]:
    """Run the Analysis Validator — sandbox-execute, score, route."""
    start_time = time.time()
    code_handoff = state.analysis_code_outputs[-1] if state.analysis_code_outputs else None
    agent = AgentFactory.get_agent("analysis_validator")
    with _track(agent, state, "phase2") as updates:
        try:
            result = agent.process(state, code_handoff=code_handoff)

            reports = list(state.analysis_validation_reports)
            if result.get("report"):
                reports.append(result["report"])
            # Keep only the last two so retry prompts can reference the most
            # recent failure; older reports are already consumed.
            if len(reports) > 2:
                reports = reports[-2:]

            trajectory = list(state.phase2_quality_trajectory)
            trajectory.append(result.get("quality_score", 0.0))

            updates["analysis_validation_reports"] = reports
            updates["phase2_quality_trajectory"] = trajectory
            updates["issue_frequency"] = update_issue_frequency(state, result.get("issues", []))

            # Prune old phase-2 outputs — best state lives in phase2_best_*.
            try:
                if isinstance(state.strategy_outputs, list) and len(state.strategy_outputs) > 2:
                    updates["strategy_outputs"] = state.strategy_outputs[-1:]
                if isinstance(state.analysis_code_outputs, list) and len(state.analysis_code_outputs) > 2:
                    updates["analysis_code_outputs"] = state.analysis_code_outputs[-1:]
            except (TypeError, AttributeError):
                pass

            logger.log_execution_time("analysis_validator_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("analysis_validator_node (FAILED)", time.time() - start_time)
            updates["errors"] = state.errors + [f"AnalysisValidator Crash: {str(e)}"]
    return updates


def assemble_notebook_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Assemble the final Jupyter Notebook.

    Role: Combines Phase 1 (Profile) cells and Phase 2 (Analysis) cells
    into a single artifact, adding markdown headers and metadata.

    Input: Locked Profile cells + Best/Final Analysis cells.
    Output: Final Notebook structure to save to disk.
    """
    # 1. Retrieve Phase 1 cells from the lock (guaranteed valid)
    profile_cells = []
    if state.profile_lock.profile_cells:
        profile_cells = list(state.profile_lock.profile_cells)

    # 2. Retrieve Phase 2 cells (latest generated)
    analysis_cells = []
    if state.analysis_code_outputs:
        latest_code = state.analysis_code_outputs[-1]
        if getattr(latest_code, "cells", None):
            analysis_cells = list(latest_code.cells)

    # 3. Retrieve Exploratory cells (if exists)
    exploratory_cells = []
    if state.exploratory_conclusions:
        # Combine conclusions and visualizations
        if hasattr(state.exploratory_conclusions, "conclusions_cells"):
            exploratory_cells.extend(state.exploratory_conclusions.conclusions_cells)
        if hasattr(state.exploratory_conclusions, "visualization_cells"):
            exploratory_cells.extend(state.exploratory_conclusions.visualization_cells)

    # 4. Create assembly package
    assembly_handoff = FinalAssemblyHandoff(
        profile_cells=profile_cells,
        phase1_quality_score=state.phase1_quality_trajectory[-1]
        if state.phase1_quality_trajectory
        else 0.0,
        analysis_cells=analysis_cells,
        exploratory_cells=exploratory_cells,
        phase2_quality_score=state.phase2_quality_trajectory[-1]
        if state.phase2_quality_trajectory
        else 0.0,
        notebook_title=state.user_intent.title
        if state.user_intent and state.user_intent.title
        else f"Data Analysis: {state.csv_path}",
        introduction_content=f"This notebook contains automated data analysis generated by the Multi-Agent Data Analysis System ({settings.app_version}).",
        conclusion_content="Analysis complete. Review the insights and recommendations above.",
        total_execution_time=state.execution_time,
        total_iterations=state.phase1_iteration + state.phase2_iteration,
        total_tokens_used=state.total_tokens_used,
    )

    # 4. Invoke Orchestrator to finalize and save
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    with _track(orchestrator, state, "phase2") as updates:
        res = orchestrator.process(state, action="assemble_notebook", assembly_handoff=assembly_handoff)
        if isinstance(res, dict):
            updates.update(res)
    logger.log_execution_time("assemble_notebook_node", time.time() - start_time)
    return updates


def exploratory_conclusions_node(state: AnalysisState) -> Dict[str, Any]:
    """Execute Exploratory Conclusions Agent."""
    start_time = time.time()
    agent = AgentFactory.get_agent("exploratory_conclusions")
    with _track(agent, state, "phase2") as updates:
        try:
            res = agent.process(state)
            if isinstance(res, dict):
                updates.update(res)
            logger.log_execution_time("exploratory_conclusions_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("exploratory_conclusions_node (FAILED)", time.time() - start_time)
            updates["errors"] = state.errors + [f"ExploratoryConclusions Crash: {str(e)}"]
    return updates


def rollback_recovery_node(state: AnalysisState) -> Dict[str, Any]:
    """Revert phase-2 state to a known-good point on quality degradation."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    with _track(orchestrator, state, "phase2") as updates:
        result = orchestrator.process(state, action="rollback_phase2")
        if isinstance(result, dict):
            updates.update(result)
    logger.log_execution_time("rollback_recovery_node", time.time() - start_time)
    return updates


# ============================================================================
# Routing Functions
# ============================================================================


def route_after_profile_validation(
    state: AnalysisState,
) -> Literal["exploratory_conclusions", "data_profiler", "profile_codegen", "end"]:
    """
    Determine the next step after Profile Validation (Phase 1).

    Logic:
    1. If Lock is granted -> Always go to exploratory_conclusions first.
    2. If Validator requests specific rerun -> Route to that agent.
    3. If max iterations reached -> End/Assemble.
    4. Default -> Retry Code Gen.
    """
    # Success Path - always run exploratory conclusions for all modes
    if state.profile_lock.is_locked():
        return "exploratory_conclusions"

    # Failure/Retry Path
    if state.profile_validation_reports:
        report = state.profile_validation_reports[-1]
        if report and report.route_to:
            if report.route_to == "DataProfiler":
                return "data_profiler"
            elif report.route_to == "ProfileCodeGenerator":
                return "profile_codegen"
            elif report.route_to == "Orchestrator":
                # Max iterations or systemic issue - stop here
                return "end"

    # Default fallback
    return "profile_codegen"


def _extraction_node(state: AnalysisState, agent_key: str, label: str) -> Dict[str, Any]:
    """Shared body for SQL / API extraction (LLM-driven, returns csv_path)."""
    start_time = time.time()
    agent = AgentFactory.get_agent(agent_key)
    with _track(agent, state, "phase1") as updates:
        try:
            result = agent.process(state)
            if result.get("csv_path"):
                updates["csv_path"] = result["csv_path"]
            if result.get("errors"):
                updates["errors"] = state.errors + result["errors"]
            logger.log_execution_time(f"{label}_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time(f"{label}_node (FAILED)", time.time() - start_time)
            logger.error(f"{label} Crash: {e}", exc_info=True)
            updates["errors"] = state.errors + [f"{label} Crash: {str(e)}"]
    return updates


def sql_extraction_node(state: AnalysisState) -> Dict[str, Any]:
    """SQL Extraction: schema + question → SELECT → CSV for the pipeline."""
    return _extraction_node(state, "sql_extraction", "SQLExtraction")


def api_extraction_node(state: AnalysisState) -> Dict[str, Any]:
    """API Extraction: REST endpoint → CSV for the pipeline."""
    return _extraction_node(state, "api_extraction", "APIExtraction")


def data_merger_node(state: AnalysisState) -> Dict[str, Any]:
    """Merge multiple input files into one dataset."""
    start_time = time.time()
    agent = AgentFactory.get_agent("data_merger")
    with _track(agent, state, "phase1") as updates:
        try:
            result = agent.process(state)
            if "error" in result:
                updates["errors"] = state.errors + [result["error"]]
            else:
                updates["merged_dataset"] = result.get("merged_dataset")
                updates["join_report"] = result.get("join_report")
                updates["csv_path"] = result.get("csv_path", state.csv_path)
            logger.log_execution_time("data_merger_node", time.time() - start_time)
        except Exception as e:
            logger.log_execution_time("data_merger_node (FAILED)", time.time() - start_time)
            logger.error(f"DataMerger Crash: {e}", exc_info=True)
            updates["errors"] = state.errors + [f"DataMerger Crash: {str(e)}"]
    return updates


def route_after_initialize(
    state: AnalysisState,
) -> Literal["restore_cache", "sql_extraction", "api_extraction", "data_merger", "create_phase1_handoff"]:
    """
    Determine path after initialization.
    """
    if state.using_cached_profile and state.cache:
        return "restore_cache"

    if state.user_intent and getattr(state.user_intent, "db_uri", None):
        return "sql_extraction"

    if state.user_intent and getattr(state.user_intent, "api_url", None):
        return "api_extraction"

    if (
        state.user_intent
        and state.user_intent.multi_file_input
        and len(state.user_intent.multi_file_input.files) > 1
    ):
        return "data_merger"

    return "create_phase1_handoff"


def route_after_exploratory_conclusions(
    state: AnalysisState,
) -> Literal["assemble_notebook", "transition_to_phase2"]:
    """
    Determine the next step after Exploratory Conclusions.

    Logic:
    1. If EXPLORATORY mode -> Go straight to assemble_notebook (no Phase 2).
    2. For all other modes -> Proceed to transition_to_phase2 for modeling.
    """
    if state.pipeline_mode == PipelineMode.EXPLORATORY:
        return "assemble_notebook"
    else:
        return "transition_to_phase2"


def route_after_analysis_validation(
    state: AnalysisState,
) -> Literal["assemble_notebook", "strategy", "analysis_codegen", "rollback_recovery"]:
    """
    Determine the next step after Analysis Validation (Phase 2).

    Logic:
    1. If Phase 2 is marked complete -> Assemble Notebook.
    2. If logic flaws found -> Route to Strategy or Code Gen.
    3. If quality dropped sharply -> Trigger Rollback.
    """
    if state.analysis_validation_reports:
        report = state.analysis_validation_reports[-1]
        if report:
            if report.route_to == "PHASE_2_COMPLETE":
                return "assemble_notebook"
            elif report.route_to == "StrategyAgent":
                return "strategy"
            elif report.route_to == "AnalysisCodeGenerator":
                return "analysis_codegen"
            elif report.route_to == "Orchestrator":
                # Check reason for Orchestrator routing
                if report.route_reason == "ROLLBACK_TRIGGERED":
                    return "rollback_recovery"
                # Else likely max iterations
                return "assemble_notebook"

    # Default fallback
    return "assemble_notebook"


# ============================================================================
# Build Graph
# ============================================================================


def build_workflow() -> StateGraph:
    """
    Construct the StateGraph logic.

    Defines the nodes (agents/actions) and edges (transitions) of the
    application.
    """

    # Create graph with state schema
    workflow = StateGraph(AnalysisState)

    # --- Add Nodes ---
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("sql_extraction", sql_extraction_node)
    workflow.add_node("api_extraction", api_extraction_node)
    workflow.add_node("data_merger", data_merger_node)
    workflow.add_node("create_phase1_handoff", create_phase1_handoff_node)

    # Phase 1 Nodes
    workflow.add_node("data_profiler", data_profiler_node)
    workflow.add_node("profile_codegen", profile_codegen_node)
    workflow.add_node("profile_validator", profile_validator_node)

    # Transition
    workflow.add_node("transition_to_phase2", transition_to_phase2_node)

    # Extension Node (New)
    workflow.add_node("extension_node", extension_node)

    # Phase 2 Nodes
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("analysis_codegen", analysis_codegen_node)
    workflow.add_node("analysis_validator", analysis_validator_node)

    # New Nodes (v0.10.0)
    workflow.add_node("exploratory_conclusions", exploratory_conclusions_node)
    workflow.add_node("restore_cache", restore_cache_node)

    # Special Nodes
    workflow.add_node("rollback_recovery", rollback_recovery_node)
    workflow.add_node("assemble_notebook", assemble_notebook_node)

    # --- Set Entry Point ---
    workflow.set_entry_point("initialize")

    # --- Phase 1 Edges ---
    # Linear flow until validation
    # v0.10.0: Conditional start based on cache
    workflow.add_conditional_edges(
        "initialize",
        route_after_initialize,
        {
            "restore_cache": "restore_cache",
            "sql_extraction": "sql_extraction",
            "api_extraction": "api_extraction",
            "data_merger": "data_merger",
            "create_phase1_handoff": "create_phase1_handoff",
        },
    )

    workflow.add_edge("sql_extraction", "create_phase1_handoff")
    workflow.add_edge("api_extraction", "create_phase1_handoff")
    workflow.add_edge("data_merger", "create_phase1_handoff")

    workflow.add_conditional_edges(
        "restore_cache",
        route_after_profile_validation,
        {
            "exploratory_conclusions": "exploratory_conclusions",
            "profile_codegen": "profile_codegen",
            "data_profiler": "data_profiler",
            "end": END,
        },
    )

    # Standard Phase 1 flow
    workflow.add_edge("create_phase1_handoff", "data_profiler")
    workflow.add_edge("data_profiler", "profile_codegen")
    workflow.add_edge("profile_codegen", "profile_validator")

    # Conditional Routing (Recursion) for Phase 1
    workflow.add_conditional_edges(
        "profile_validator",
        route_after_profile_validation,
        {
            "exploratory_conclusions": "exploratory_conclusions",
            "data_profiler": "data_profiler",
            "profile_codegen": "profile_codegen",
            "end": END,
        },
    )

    # --- Phase 2 Edges ---
    # Linear flow until validation
    workflow.add_edge("transition_to_phase2", "extension_node")
    workflow.add_edge("extension_node", "strategy")
    workflow.add_edge("strategy", "analysis_codegen")
    workflow.add_edge("analysis_codegen", "analysis_validator")

    # Conditional Routing (Recursion) for Phase 2
    workflow.add_conditional_edges(
        "analysis_validator",
        route_after_analysis_validation,
        {
            "assemble_notebook": "assemble_notebook",
            "strategy": "strategy",
            "analysis_codegen": "analysis_codegen",
            "rollback_recovery": "rollback_recovery",
        },
    )

    # --- Exploratory Conclusions Routing ---
    # After exploratory conclusions, either go to Phase 2 or directly to assembly
    workflow.add_conditional_edges(
        "exploratory_conclusions",
        route_after_exploratory_conclusions,
        {
            "assemble_notebook": "assemble_notebook",
            "transition_to_phase2": "transition_to_phase2",
        },
    )

    # --- Final Edges ---
    workflow.add_edge("rollback_recovery", "assemble_notebook")  # Recover then save
    workflow.add_edge("assemble_notebook", END)  # Done

    return workflow


def compile_workflow():
    """Compile the workflow for execution."""
    workflow = build_workflow()
    return workflow.compile()


@lru_cache(maxsize=1)
def get_graph():
    """Compile and cache the workflow graph (thread-safe via lru_cache)."""
    return compile_workflow()
