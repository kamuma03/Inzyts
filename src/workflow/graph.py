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
from functools import lru_cache, wraps
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
#
# Most nodes share one scaffold: resolve an agent, run it under ``_track`` (so
# its token cost is attributed even on failure), convert an uncaught exception
# into a ``"<Label> Crash: …"`` entry on ``errors``, and log execution time.
# ``@_node`` factors that out; a decorated body receives ``(state, agent)`` and
# returns the dict of state updates to merge (token totals are added by _track).


def _node(agent, phase: Phase, label: str):
    """Wrap a node body with the shared agent/track/error/timing scaffold.

    ``agent`` is the agent name, or a callable ``(state) -> name`` for nodes that
    pick an agent by pipeline mode. ``label`` produces the ``"<label> Crash"``
    error text on an uncaught exception (kept identical to the pre-refactor
    messages that routing and tests rely on).
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(state: AnalysisState) -> Dict[str, Any]:
            start_time = time.time()
            agent_name = agent(state) if callable(agent) else agent
            if not agent_name:
                # A dynamic resolver may decline this node — e.g. a pipeline mode
                # with no pre-strategy extension. Skip cleanly: no agent fetch,
                # no LLM call, no token attribution.
                logger.debug(f"{label} node: no agent for this mode, skipping.")
                return {}
            agent_instance = AgentFactory.get_agent(agent_name)
            with _track(agent_instance, state, phase) as updates:
                try:
                    body_updates = fn(state, agent_instance)
                    if isinstance(body_updates, dict):
                        updates.update(body_updates)
                except Exception as e:
                    logger.critical(f"{label} Node crashed: {e}", exc_info=True)
                    updates["errors"] = state.errors + [f"{label} Crash: {str(e)}"]
            logger.log_execution_time(fn.__name__, time.time() - start_time)
            return updates

        return wrapper

    return decorator


@_node("orchestrator", "phase1", "Initialize")
def initialize_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Initialize the workflow execution (Orchestrator setup → Phase 1)."""
    result = agent.process(
        state,
        action="initialize",
        csv_path=state.csv_path,
        user_intent=state.user_intent.model_dump() if state.user_intent else None,
        mode=state.pipeline_mode,
        use_cache=state.using_cached_profile,
    )
    return result if isinstance(result, dict) else {}


@_node("orchestrator", "phase1", "RestoreCache")
def restore_cache_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Unlock the workflow using a cached profile."""
    result = agent.process(state, action="restore_cache")
    return result if isinstance(result, dict) else {}


@_node("orchestrator", "phase1", "Phase1Handoff")
def create_phase1_handoff_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Orchestrator packages CSV preview + intent for the Data Profiler."""
    result = agent.process(state, action="phase1_handoff")
    return result if isinstance(result, dict) else {}


@_node("data_profiler", "phase1", "DataProfiler")
def data_profiler_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Data Profiler — type/quality EDA → ProfilerToCodeGenHandoff."""
    # Use the orchestrator's handoff (CSV preview + extended metadata), not the
    # profiler's own previous output — they are different handoff types. Reading
    # profiler_outputs[-1] here fed the profiler a ProfilerToCodeGenHandoff on
    # retries and crashed on its missing is_multi_file attribute.
    result = agent.process(state, handoff=state.profiler_handoff)
    outputs = list(state.profiler_outputs)
    if result.get("handoff"):
        outputs.append(result["handoff"])
    updates: Dict[str, Any] = {"profiler_outputs": outputs}
    if result.get("updated_csv_path"):
        updates["csv_path"] = result["updated_csv_path"]
    return updates


@_node("profile_codegen", "phase1", "ProfileCodeGen")
def profile_codegen_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Profile Code Generator — spec → notebook cells."""
    spec = state.profiler_outputs[-1] if state.profiler_outputs else None
    result = agent.process(state, specification=spec)
    code_outputs = list(state.profile_code_outputs)
    if result.get("handoff"):
        code_outputs.append(result["handoff"])
    return {
        "profile_code_outputs": code_outputs,
        "phase1_iteration": state.phase1_iteration + 1,
    }


@_node("profile_validator", "phase1", "ProfileValidator")
def profile_validator_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Profile Validator — sandbox-execute, score, possibly lock."""
    code_handoff = state.profile_code_outputs[-1] if state.profile_code_outputs else None
    result = agent.process(state, code_handoff=code_handoff)

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

    return {
        "profile_validation_reports": reports,
        "phase1_quality_trajectory": trajectory,
        "issue_frequency": update_issue_frequency(state, result.get("issues", [])),
        "profile_lock": profile_lock,
    }


_EXTENSION_AGENTS = {
    PipelineMode.FORECASTING: "forecasting_extension",
    PipelineMode.COMPARATIVE: "comparative_extension",
    PipelineMode.DIAGNOSTIC: "diagnostic_extension",
}


@_node(lambda state: _EXTENSION_AGENTS.get(state.pipeline_mode), "extensions", "Extension")
def extension_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run mode-specific pre-strategy extension (forecasting / A-B / diagnostic).

    Modes with no entry in ``_EXTENSION_AGENTS`` resolve to ``None`` and ``@_node``
    skips the node without touching the factory.
    """
    return agent.process(state)


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

    # Token accounting must survive a mid-call crash, so each snapshot is
    # converted to a delta in ``finally`` — whether the call returned or threw,
    # the tokens it burned are still attributed to the right phase bucket.
    save_delta = (0, 0, 0)
    transition_delta = (0, 0, 0)
    result: Any = {}
    error: str | None = None

    save_snap = None
    trans_snap = None
    try:
        # Phase-1 accounting: the save-cache call.
        if state.profile_lock and state.profile_lock.is_locked():
            save_snap = _llm_snapshot(orchestrator)
            orchestrator.process(state, action="save_cache")
            save_delta = _llm_delta(orchestrator, save_snap)
            save_snap = None

        # Phase-2 accounting: the transition itself.
        trans_snap = _llm_snapshot(orchestrator)
        result = orchestrator.process(state, action="transition_to_phase2")
        transition_delta = _llm_delta(orchestrator, trans_snap)
        trans_snap = None
    except Exception as e:
        logger.critical(f"Transition Node crashed: {e}", exc_info=True)
        error = f"Transition Crash: {str(e)}"
    finally:
        if save_snap is not None:
            save_delta = _llm_delta(orchestrator, save_snap)
        if trans_snap is not None:
            transition_delta = _llm_delta(orchestrator, trans_snap)

    updates: Dict[str, Any] = dict(result) if isinstance(result, dict) else {}
    if error:
        updates["errors"] = state.errors + [error]
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


@_node(lambda state: _STRATEGY_AGENTS.get(state.pipeline_mode, "strategy"), "phase2", "Strategy")
def strategy_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Strategy Agent (mode-specific) over the locked profile."""
    profile_handoff = state.profile_lock.get_locked_handoff()
    result = agent.process(state, profile_handoff=profile_handoff)
    outputs = list(state.strategy_outputs)
    if result.get("handoff"):
        outputs.append(result["handoff"])
    return {
        "strategy_outputs": outputs,
        "phase2_iteration": state.phase2_iteration + 1,
    }


@_node("analysis_codegen", "phase2", "AnalysisCodeGen")
def analysis_codegen_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Analysis Code Generator — strategy → executable code cells."""
    strategy = state.strategy_outputs[-1] if state.strategy_outputs else None
    result = agent.process(state, strategy=strategy)
    outputs = list(state.analysis_code_outputs)
    if result.get("handoff"):
        outputs.append(result["handoff"])
    return {"analysis_code_outputs": outputs}


@_node("analysis_validator", "phase2", "AnalysisValidator")
def analysis_validator_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Run the Analysis Validator — sandbox-execute, score, route."""
    code_handoff = state.analysis_code_outputs[-1] if state.analysis_code_outputs else None
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

    updates: Dict[str, Any] = {
        "analysis_validation_reports": reports,
        "phase2_quality_trajectory": trajectory,
        "issue_frequency": update_issue_frequency(state, result.get("issues", [])),
    }

    # Snapshot the best-so-far strategy/code whenever quality improves, so
    # route_phase2_recursion's rollback path has something real to restore.
    # Without this the phase2_best_* fields stay at their defaults and a
    # rollback silently reverts to nothing.
    current_score = result.get("quality_score", 0.0)
    current_strategy = state.strategy_outputs[-1] if state.strategy_outputs else None
    if current_score > state.phase2_best_score and code_handoff is not None:
        updates["phase2_best_score"] = current_score
        updates["phase2_best_code"] = code_handoff
        if current_strategy is not None:
            updates["phase2_best_strategy"] = current_strategy

    # Prune old phase-2 outputs — best state lives in phase2_best_*.
    try:
        if isinstance(state.strategy_outputs, list) and len(state.strategy_outputs) > 2:
            updates["strategy_outputs"] = state.strategy_outputs[-1:]
        if isinstance(state.analysis_code_outputs, list) and len(state.analysis_code_outputs) > 2:
            updates["analysis_code_outputs"] = state.analysis_code_outputs[-1:]
    except (TypeError, AttributeError):
        pass

    return updates


@_node("orchestrator", "phase2", "AssembleNotebook")
def assemble_notebook_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
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

    # 4. Invoke Orchestrator to finalize and save (token-tracked by @_node).
    res = agent.process(state, action="assemble_notebook", assembly_handoff=assembly_handoff)
    return res if isinstance(res, dict) else {}


@_node("exploratory_conclusions", "phase2", "ExploratoryConclusions")
def exploratory_conclusions_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Execute Exploratory Conclusions Agent."""
    res = agent.process(state)
    return res if isinstance(res, dict) else {}


@_node("orchestrator", "phase2", "Rollback")
def rollback_recovery_node(state: AnalysisState, agent: Any) -> Dict[str, Any]:
    """Revert phase-2 state to a known-good point on quality degradation."""
    result = agent.process(state, action="rollback_phase2")
    return result if isinstance(result, dict) else {}


# ============================================================================
# Routing Functions
# ============================================================================


def _over_token_budget(state: AnalysisState) -> bool:
    """True if the run has burned its global token budget.

    The per-phase iteration caps bound *how many* loops run, but a single
    pathological loop (e.g. the LLM repeatedly emitting near-miss JSON at a high
    max_tokens) can still burn unbounded cost within those caps. This is the hard
    kill-switch the configured ``max_tokens_per_run`` was always meant to be.
    """
    budget = settings.recursion.max_tokens_per_run
    used = getattr(state, "total_tokens_used", 0) or 0
    if budget and used >= budget:
        logger.warning(
            f"Token budget exhausted: {used} >= {budget}; "
            "halting recursion and salvaging current output."
        )
        return True
    return False


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

    # Hard cost ceiling: stop retrying Phase 1 once the token budget is spent.
    if _over_token_budget(state):
        return "end"

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
            else:
                logger.warning(
                    f"route_after_profile_validation: unrecognised route_to "
                    f"'{report.route_to}' — retrying profile_codegen."
                )

    # Default: no lock yet and no explicit route → retry code generation.
    logger.debug("route_after_profile_validation: default → profile_codegen")
    return "profile_codegen"


def route_after_restore_cache(
    state: AnalysisState,
) -> Literal["exploratory_conclusions", "create_phase1_handoff"]:
    """Route out of the cache-restore node.

    On a healthy restore the profile lock is rebuilt and LOCKED, so we proceed to
    exploratory conclusions like any locked Phase 1. If the cached payload was
    corrupt or partial and the lock did not come back LOCKED, restart Phase 1
    cleanly instead of falling through to profile_codegen — which would read an
    empty profiler_outputs and spin in a no-lock retry loop.
    """
    if state.profile_lock.is_locked():
        return "exploratory_conclusions"
    logger.warning(
        "restore_cache produced an unlocked profile (corrupt/partial cache); "
        "restarting Phase 1 from a fresh handoff."
    )
    return "create_phase1_handoff"


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
    # Hard cost ceiling: salvage whatever we have rather than loop on cost.
    if _over_token_budget(state):
        return "assemble_notebook"

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
            else:
                logger.warning(
                    f"route_after_analysis_validation: unrecognised route_to "
                    f"'{report.route_to}' — assembling notebook."
                )

    # Default: nothing actionable left → assemble whatever we have.
    logger.debug("route_after_analysis_validation: default → assemble_notebook")
    return "assemble_notebook"


# ============================================================================
# Build Graph
# ============================================================================


def _register_nodes(workflow: StateGraph) -> None:
    """Register every node (entry/ingestion, Phase 1, transition, Phase 2, final)."""
    # Entry + data ingestion
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("sql_extraction", sql_extraction_node)
    workflow.add_node("api_extraction", api_extraction_node)
    workflow.add_node("data_merger", data_merger_node)
    workflow.add_node("create_phase1_handoff", create_phase1_handoff_node)
    workflow.add_node("restore_cache", restore_cache_node)

    # Phase 1 — data understanding
    workflow.add_node("data_profiler", data_profiler_node)
    workflow.add_node("profile_codegen", profile_codegen_node)
    workflow.add_node("profile_validator", profile_validator_node)
    workflow.add_node("exploratory_conclusions", exploratory_conclusions_node)

    # Transition + Phase 2 — analysis & modeling
    workflow.add_node("transition_to_phase2", transition_to_phase2_node)
    workflow.add_node("extension_node", extension_node)
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("analysis_codegen", analysis_codegen_node)
    workflow.add_node("analysis_validator", analysis_validator_node)

    # Final / recovery
    workflow.add_node("rollback_recovery", rollback_recovery_node)
    workflow.add_node("assemble_notebook", assemble_notebook_node)


def _register_phase1_edges(workflow: StateGraph) -> None:
    """Entry routing, data-ingestion fan-in, and the Phase 1 recursion loop."""
    # Conditional start: cache / SQL / API / multi-file / standard.
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

    # All ingestion paths converge on the profiler handoff.
    workflow.add_edge("sql_extraction", "create_phase1_handoff")
    workflow.add_edge("api_extraction", "create_phase1_handoff")
    workflow.add_edge("data_merger", "create_phase1_handoff")

    workflow.add_conditional_edges(
        "restore_cache",
        route_after_restore_cache,
        {
            "exploratory_conclusions": "exploratory_conclusions",
            "create_phase1_handoff": "create_phase1_handoff",
        },
    )

    # Standard Phase 1 linear flow → validation, then the recursion loop.
    workflow.add_edge("create_phase1_handoff", "data_profiler")
    workflow.add_edge("data_profiler", "profile_codegen")
    workflow.add_edge("profile_codegen", "profile_validator")
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


def _register_phase2_edges(workflow: StateGraph) -> None:
    """Exploratory branch, the Phase 2 recursion loop, and final assembly."""
    # Exploratory conclusions either finish (exploratory mode) or enter Phase 2.
    workflow.add_conditional_edges(
        "exploratory_conclusions",
        route_after_exploratory_conclusions,
        {
            "assemble_notebook": "assemble_notebook",
            "transition_to_phase2": "transition_to_phase2",
        },
    )

    # Phase 2 linear flow → validation, then the recursion loop.
    workflow.add_edge("transition_to_phase2", "extension_node")
    workflow.add_edge("extension_node", "strategy")
    workflow.add_edge("strategy", "analysis_codegen")
    workflow.add_edge("analysis_codegen", "analysis_validator")
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

    # Final edges.
    workflow.add_edge("rollback_recovery", "assemble_notebook")  # Recover then save
    workflow.add_edge("assemble_notebook", END)


def build_workflow() -> StateGraph:
    """Construct the StateGraph: nodes (agents/actions) and edges (transitions)."""
    workflow = StateGraph(AnalysisState)
    _register_nodes(workflow)
    workflow.set_entry_point("initialize")
    _register_phase1_edges(workflow)
    _register_phase2_edges(workflow)
    return workflow


def _recursion_limit() -> int:
    """Derive an explicit LangGraph recursion limit from the iteration caps.

    LangGraph's default of 25 super-steps can be hit by a legitimate run (Phase 1
    retries + Phase 2's validation ceiling of ``phase2_max_iterations * 3`` plus
    the linear node chain), surfacing as an opaque ``GraphRecursionError``. We set
    a generous explicit budget so the iteration caps and the token kill-switch are
    the real stopping conditions, with this only as a final structural backstop.
    """
    r = settings.recursion
    phase1 = r.phase1_max_iterations * 3      # profiler/codegen/validator per loop
    phase2 = r.phase2_max_iterations * 3 + 6  # validation ceiling + strategy hops
    fixed_chain = 12                          # init, extraction, assembly, etc.
    return phase1 + phase2 + fixed_chain


def compile_workflow():
    """Compile the workflow for execution."""
    workflow = build_workflow()
    return workflow.compile().with_config(recursion_limit=_recursion_limit())


@lru_cache(maxsize=1)
def get_graph():
    """Compile and cache the workflow graph (thread-safe via lru_cache)."""
    return compile_workflow()
