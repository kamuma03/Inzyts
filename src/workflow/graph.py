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
from functools import lru_cache
from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from src.config import settings
from src.models.handoffs import FinalAssemblyHandoff, PipelineMode
from src.models.state import AnalysisState
from src.utils.logger import get_logger
from src.workflow.agent_factory import AgentFactory
from src.workflow.routing import update_issue_frequency

logger = get_logger()

# Agent instances are now retrieved via AgentFactory to prevent global initialization cost


# ============================================================================
# Node Functions
# ============================================================================


def initialize_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Initialize the workflow execution.

    Role: Sets up the initial context, parses user intent, and prepares
    the state for Phase 1.

    Args:
        state: The initial state object.

    Returns:
        State updates from the Orchestrator's initialization process.
    """
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    start_tokens = orchestrator.llm_agent.total_tokens
    start_prompt = orchestrator.llm_agent.prompt_tokens
    start_completion = orchestrator.llm_agent.completion_tokens
    result = orchestrator.process(
        state,
        action="initialize",
        csv_path=state.csv_path,
        user_intent=state.user_intent.model_dump() if state.user_intent else None,
        mode=state.pipeline_mode,
        use_cache=state.using_cached_profile,
    )
    tokens_used = orchestrator.llm_agent.total_tokens - start_tokens
    prompt_used = orchestrator.llm_agent.prompt_tokens - start_prompt
    completion_used = orchestrator.llm_agent.completion_tokens - start_completion
    logger.log_execution_time("initialize_node", time.time() - start_time)

    # Update total tokens in result
    result["total_tokens_used"] = state.total_tokens_used + tokens_used
    result["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
    result["completion_tokens_used"] = state.completion_tokens_used + completion_used
    return result


def restore_cache_node(state: AnalysisState) -> Dict[str, Any]:
    """Unlock the workflow using a cached profile."""
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    start_tokens = orchestrator.llm_agent.total_tokens
    start_prompt = orchestrator.llm_agent.prompt_tokens
    start_completion = orchestrator.llm_agent.completion_tokens
    result = orchestrator.process(state, action="restore_cache")
    tokens_used = orchestrator.llm_agent.total_tokens - start_tokens
    prompt_used = orchestrator.llm_agent.prompt_tokens - start_prompt
    completion_used = orchestrator.llm_agent.completion_tokens - start_completion

    if isinstance(result, dict):
        result["total_tokens_used"] = state.total_tokens_used + tokens_used
        result["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
        result["completion_tokens_used"] = state.completion_tokens_used + completion_used

    logger.log_execution_time("restore_cache_node", time.time() - start_time)
    return result


def create_phase1_handoff_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Generate the initial handoff for the Data Profiler.

    Role: Orchestrator invokes this to package the CSV preview, row counts,
    and user intent into a structured format for the Profiler.
    """
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    start_tokens = orchestrator.llm_agent.total_tokens
    start_prompt = orchestrator.llm_agent.prompt_tokens
    start_completion = orchestrator.llm_agent.completion_tokens
    result = orchestrator.process(state, action="phase1_handoff")
    tokens_used = orchestrator.llm_agent.total_tokens - start_tokens
    prompt_used = orchestrator.llm_agent.prompt_tokens - start_prompt
    completion_used = orchestrator.llm_agent.completion_tokens - start_completion

    logger.log_execution_time("create_phase1_handoff_node", time.time() - start_time)

    # Update total tokens
    if isinstance(result, dict):
        result["total_tokens_used"] = state.total_tokens_used + tokens_used
        result["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
        result["completion_tokens_used"] = state.completion_tokens_used + completion_used

    return result


def data_profiler_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Data Profiler Agent.

    Role: Analyzes the raw CSV to identify types, quality issues, and
    requirements for statistical analysis.

    Input: Latest Orchestrator handoff or retry feedback.
    Output: Profiler Specification (ProfilerToCodeGenHandoff).
    """
    start_time = time.time()
    data_profiler = AgentFactory.get_agent("data_profiler")
    handoff = state.profiler_outputs[-1] if state.profiler_outputs else None
    start_tokens = data_profiler.llm_agent.total_tokens
    start_prompt = data_profiler.llm_agent.prompt_tokens
    start_completion = data_profiler.llm_agent.completion_tokens

    try:
        result = data_profiler.process(state, handoff=handoff)
        tokens_used = data_profiler.llm_agent.total_tokens - start_tokens
        prompt_used = data_profiler.llm_agent.prompt_tokens - start_prompt
        completion_used = data_profiler.llm_agent.completion_tokens - start_completion

        # Append the new result to the history of profiler outputs
        profiler_outputs = list(state.profiler_outputs)
        handoff = result.get("handoff")
        if handoff:
            profiler_outputs.append(handoff)

        updates = {
            "profiler_outputs": profiler_outputs,
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }

        if result.get("updated_csv_path"):
            updates["csv_path"] = result["updated_csv_path"]

        logger.log_execution_time("data_profiler_node", time.time() - start_time)
        return updates
    except Exception as e:
        # Capture tokens even on failure
        tokens_used = data_profiler.llm_agent.total_tokens - start_tokens
        prompt_used = data_profiler.llm_agent.prompt_tokens - start_prompt
        completion_used = data_profiler.llm_agent.completion_tokens - start_completion
        logger.log_execution_time(
            "data_profiler_node (FAILED)", time.time() - start_time
        )
        logger.critical(f"DataProfiler Node crashed: {e}", exc_info=True)
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"DataProfiler Crash: {str(e)}"],
        }


def profile_codegen_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Profile Code Generator Agent.

    Role: Converts the logical profile specification into executable
    Jupyter notebook code (cells).

    Input: Latest Profiler Specification.
    Output: Generated Code (ProfileCodeToValidatorHandoff).
    """
    start_time = time.time()
    # Use the most recent specification from the profiler
    spec = state.profiler_outputs[-1] if state.profiler_outputs else None

    profile_codegen = AgentFactory.get_agent("profile_codegen")
    start_tokens = profile_codegen.llm_agent.total_tokens
    start_prompt = profile_codegen.llm_agent.prompt_tokens
    start_completion = profile_codegen.llm_agent.completion_tokens

    try:
        result = profile_codegen.process(state, specification=spec)
        tokens_used = profile_codegen.llm_agent.total_tokens - start_tokens
        prompt_used = profile_codegen.llm_agent.prompt_tokens - start_prompt
        completion_used = profile_codegen.llm_agent.completion_tokens - start_completion

        # Store the generated code
        code_outputs = list(state.profile_code_outputs)
        handoff = result.get("handoff")
        if handoff:
            code_outputs.append(handoff)

        logger.log_execution_time("profile_codegen_node", time.time() - start_time)
        return {
            "profile_code_outputs": code_outputs,
            "phase1_iteration": state.phase1_iteration + 1,  # Increment iteration count
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = profile_codegen.llm_agent.total_tokens - start_tokens
        prompt_used = profile_codegen.llm_agent.prompt_tokens - start_prompt
        completion_used = profile_codegen.llm_agent.completion_tokens - start_completion
        logger.log_execution_time(
            "profile_codegen_node (FAILED)", time.time() - start_time
        )
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"ProfileCodeGen Crash: {str(e)}"],
        }


def profile_validator_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Profile Validator Agent.

    Role: Runs the generated code in a sandbox, checks for errors, and
    calculates a quality score. Decides if the profile is 'Locked'.

    Input: Latest generated code.
    Output: Validation Report & Potential Lock Grant.
    """

    profile_validator = AgentFactory.get_agent("profile_validator")

    code_handoff = (
        state.profile_code_outputs[-1] if state.profile_code_outputs else None
    )
    start_tokens = profile_validator.llm_agent.total_tokens
    start_prompt = profile_validator.llm_agent.prompt_tokens
    start_completion = profile_validator.llm_agent.completion_tokens

    try:
        result = profile_validator.process(state, code_handoff=code_handoff)
        tokens_used = profile_validator.llm_agent.total_tokens - start_tokens
        prompt_used = profile_validator.llm_agent.prompt_tokens - start_prompt
        completion_used = profile_validator.llm_agent.completion_tokens - start_completion

        # Append validation report
        validation_reports = list(state.profile_validation_reports)
        report = result.get("report")
        if report:
            validation_reports.append(report)

        # Update quality trajectory (for oscillation detection and rollback)
        quality_trajectory = list(state.phase1_quality_trajectory)
        quality_trajectory.append(result.get("quality_score", 0.0))

        # Update issue frequency table (for systemic issue detection)
        issue_frequency = update_issue_frequency(state, result.get("issues", []))

        # Check if the validator explicitly approved locking the profile
        profile_lock = state.profile_lock
        if result.get("should_lock"):
            # Grant the lock - this snapshots the profile state and makes it immutable
            profile_lock.grant_lock(
                cells=code_handoff.cells if code_handoff else [],
                handoff=result.get("strategy_handoff"),
                quality_score=result.get("quality_score", 0.0),
                report=result.get("report"),
                iteration=state.phase1_iteration,
            )
            # Cache is now saved in transition_to_phase2_node

        return {
            "profile_validation_reports": validation_reports,
            "phase1_quality_trajectory": quality_trajectory,
            "issue_frequency": issue_frequency,
            "profile_lock": profile_lock,
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = profile_validator.llm_agent.total_tokens - start_tokens
        prompt_used = profile_validator.llm_agent.prompt_tokens - start_prompt
        completion_used = profile_validator.llm_agent.completion_tokens - start_completion
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"ProfileValidator Crash: {str(e)}"],
        }


def extension_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute Extension Agents based on Pipeline Mode.

    Role: Runs specific pre-strategy analysis (forecasting, A/B testing checks)
    to enrich the context for the Strategy Agent.
    """
    start_time = time.time()
    mode = state.pipeline_mode
    updates = {}
    agent = None

    if mode == PipelineMode.FORECASTING:
        agent = AgentFactory.get_agent("forecasting_extension")
    elif mode == PipelineMode.COMPARATIVE:
        agent = AgentFactory.get_agent("comparative_extension")
    elif mode == PipelineMode.DIAGNOSTIC:
        agent = AgentFactory.get_agent("diagnostic_extension")

    mode_val = mode.value if mode else "unknown"
    if agent:
        start_tokens = agent.llm_agent.total_tokens
        start_prompt = agent.llm_agent.prompt_tokens
        start_completion = agent.llm_agent.completion_tokens
        try:
            updates = agent.process(state)
            tokens_used = agent.llm_agent.total_tokens - start_tokens
            prompt_used = agent.llm_agent.prompt_tokens - start_prompt
            completion_used = agent.llm_agent.completion_tokens - start_completion
            updates["total_tokens_used"] = state.total_tokens_used + tokens_used
            updates["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
            updates["completion_tokens_used"] = state.completion_tokens_used + completion_used
            logger.log_execution_time(
                f"extension_node ({mode_val})", time.time() - start_time
            )
        except Exception as e:
            tokens_used = agent.llm_agent.total_tokens - start_tokens
            prompt_used = agent.llm_agent.prompt_tokens - start_prompt
            completion_used = agent.llm_agent.completion_tokens - start_completion
            logger.error(f"Extension Agent {mode_val} failed: {e}")
            updates = {
                "errors": state.errors + [f"Extension {mode_val} failed: {e}"],
                "total_tokens_used": state.total_tokens_used + tokens_used,
                "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
                "completion_tokens_used": state.completion_tokens_used + completion_used,
            }
    else:
        # No extension agent for this mode (e.g. Predictive, Exploratory, Segmentation).
        # Log so that a missing registration for a new mode is immediately visible.
        logger.debug(f"extension_node: no extension agent registered for mode '{mode_val}', skipping.")

    return updates


def transition_to_phase2_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Transition logic from Phase 1 to Phase 2.

    Role: Orchestrator updates the global phase state, saves the profile cache,
    and prepares context for the Strategy Agent.
    """
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")

    # Save the locked profile to cache before transitioning.
    # Track its tokens separately so neither call's usage is lost.
    save_tokens = 0
    save_prompt = 0
    save_completion = 0
    if state.profile_lock and state.profile_lock.is_locked():
        save_start = orchestrator.llm_agent.total_tokens
        save_prompt_start = orchestrator.llm_agent.prompt_tokens
        save_completion_start = orchestrator.llm_agent.completion_tokens
        orchestrator.process(state, action="save_cache")
        save_tokens = orchestrator.llm_agent.total_tokens - save_start
        save_prompt = orchestrator.llm_agent.prompt_tokens - save_prompt_start
        save_completion = orchestrator.llm_agent.completion_tokens - save_completion_start

    transition_start = orchestrator.llm_agent.total_tokens
    transition_prompt_start = orchestrator.llm_agent.prompt_tokens
    transition_completion_start = orchestrator.llm_agent.completion_tokens
    result = orchestrator.process(state, action="transition_to_phase2")
    transition_tokens = orchestrator.llm_agent.total_tokens - transition_start
    transition_prompt = orchestrator.llm_agent.prompt_tokens - transition_prompt_start
    transition_completion = orchestrator.llm_agent.completion_tokens - transition_completion_start

    logger.log_execution_time("transition_to_phase2_node", time.time() - start_time)

    if isinstance(result, dict):
        result["total_tokens_used"] = state.total_tokens_used + save_tokens + transition_tokens
        result["prompt_tokens_used"] = state.prompt_tokens_used + save_prompt + transition_prompt
        result["completion_tokens_used"] = state.completion_tokens_used + save_completion + transition_completion

    return result


def strategy_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Strategy Agent.

    Role: Reads the LOCKED profile and designs a machine learning/analysis
    strategy. It CANNOT modify the profile data.

    Input: Locked Profile.
    Output: Analysis Strategy (StrategyToCodeGenHandoff).
    """
    start_time = time.time()

    # Select Agent based on Mode
    mode = state.pipeline_mode
    selected_agent = AgentFactory.get_agent("strategy")  # Default

    if mode == PipelineMode.FORECASTING:
        selected_agent = AgentFactory.get_agent("forecasting_strategy")
    elif mode == PipelineMode.COMPARATIVE:
        selected_agent = AgentFactory.get_agent("comparative_strategy")
    elif mode == PipelineMode.DIAGNOSTIC:
        selected_agent = AgentFactory.get_agent("diagnostic_strategy")
    elif mode == PipelineMode.SEGMENTATION:
        selected_agent = AgentFactory.get_agent("segmentation_strategy")
    elif mode == PipelineMode.DIMENSIONALITY:
        selected_agent = AgentFactory.get_agent("dimensionality_strategy")

    # Retrieve the immutable locked profile
    profile_handoff = state.profile_lock.get_locked_handoff()

    start_tokens = selected_agent.llm_agent.total_tokens
    start_prompt = selected_agent.llm_agent.prompt_tokens
    start_completion = selected_agent.llm_agent.completion_tokens

    try:
        result = selected_agent.process(state, profile_handoff=profile_handoff)
        tokens_used = selected_agent.llm_agent.total_tokens - start_tokens
        prompt_used = selected_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = selected_agent.llm_agent.completion_tokens - start_completion

        # Store outputs
        strategy_outputs = list(state.strategy_outputs)
        handoff = result.get("handoff")
        if handoff:
            strategy_outputs.append(handoff)

        logger.log_execution_time("strategy_node", time.time() - start_time)
        return {
            "strategy_outputs": strategy_outputs,
            "phase2_iteration": state.phase2_iteration + 1,
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = selected_agent.llm_agent.total_tokens - start_tokens
        prompt_used = selected_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = selected_agent.llm_agent.completion_tokens - start_completion
        logger.log_execution_time("strategy_node (FAILED)", time.time() - start_time)
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"Strategy Crash: {str(e)}"],
        }


def analysis_codegen_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Analysis Code Generator Agent.

    Role: Implements the strategy into executable code (model training,
    evaluation, visualization) based on the Strategy.

    Input: Latest Analysis Strategy.
    Output: Generated Analysis Code.
    """
    start_time = time.time()
    strategy = state.strategy_outputs[-1] if state.strategy_outputs else None

    analysis_codegen = AgentFactory.get_agent("analysis_codegen")
    start_tokens = analysis_codegen.llm_agent.total_tokens
    start_prompt = analysis_codegen.llm_agent.prompt_tokens
    start_completion = analysis_codegen.llm_agent.completion_tokens

    try:
        result = analysis_codegen.process(state, strategy=strategy)
        tokens_used = analysis_codegen.llm_agent.total_tokens - start_tokens
        prompt_used = analysis_codegen.llm_agent.prompt_tokens - start_prompt
        completion_used = analysis_codegen.llm_agent.completion_tokens - start_completion

        # Store output
        code_outputs = list(state.analysis_code_outputs)
        handoff = result.get("handoff")
        if handoff:
            code_outputs.append(handoff)

        logger.log_execution_time("analysis_codegen_node", time.time() - start_time)
        return {
            "analysis_code_outputs": code_outputs,
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = analysis_codegen.llm_agent.total_tokens - start_tokens
        prompt_used = analysis_codegen.llm_agent.prompt_tokens - start_prompt
        completion_used = analysis_codegen.llm_agent.completion_tokens - start_completion
        logger.log_execution_time(
            "analysis_codegen_node (FAILED)", time.time() - start_time
        )
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"AnalysisCodeGen Crash: {str(e)}"],
        }


def analysis_validator_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Analysis Validator Agent.

    Role: Validates the analysis code correctness, model performance, and
    adherence to the strategy.

    Input: Latest Analysis Code.
    Output: Validation Report & completion decision.
    """
    start_time = time.time()
    code_handoff = (
        state.analysis_code_outputs[-1] if state.analysis_code_outputs else None
    )
    analysis_validator = AgentFactory.get_agent("analysis_validator")
    start_tokens = analysis_validator.llm_agent.total_tokens
    start_prompt = analysis_validator.llm_agent.prompt_tokens
    start_completion = analysis_validator.llm_agent.completion_tokens

    try:
        result = analysis_validator.process(state, code_handoff=code_handoff)
        tokens_used = analysis_validator.llm_agent.total_tokens - start_tokens
        prompt_used = analysis_validator.llm_agent.prompt_tokens - start_prompt
        completion_used = analysis_validator.llm_agent.completion_tokens - start_completion

        # Store outputs
        validation_reports = list(state.analysis_validation_reports)
        report = result.get("report")
        if report:
            validation_reports.append(report)

        # Track quality for Phase 2
        quality_trajectory = list(state.phase2_quality_trajectory)
        quality_trajectory.append(result.get("quality_score", 0.0))

        # Update issue frequency (for systemic issue detection in routing)
        issue_frequency = update_issue_frequency(state, result.get("issues", []))

        logger.log_execution_time("analysis_validator_node", time.time() - start_time)
        return {
            "analysis_validation_reports": validation_reports,
            "phase2_quality_trajectory": quality_trajectory,
            "issue_frequency": issue_frequency,
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = analysis_validator.llm_agent.total_tokens - start_tokens
        prompt_used = analysis_validator.llm_agent.prompt_tokens - start_prompt
        completion_used = analysis_validator.llm_agent.completion_tokens - start_completion
        logger.log_execution_time(
            "analysis_validator_node (FAILED)", time.time() - start_time
        )
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"AnalysisValidator Crash: {str(e)}"],
        }


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
    start_tokens = orchestrator.llm_agent.total_tokens
    start_prompt = orchestrator.llm_agent.prompt_tokens
    start_completion = orchestrator.llm_agent.completion_tokens
    res = orchestrator.process(
        state, action="assemble_notebook", assembly_handoff=assembly_handoff
    )
    tokens_used = orchestrator.llm_agent.total_tokens - start_tokens
    prompt_used = orchestrator.llm_agent.prompt_tokens - start_prompt
    completion_used = orchestrator.llm_agent.completion_tokens - start_completion

    if isinstance(res, dict):
        res["total_tokens_used"] = state.total_tokens_used + tokens_used
        res["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
        res["completion_tokens_used"] = state.completion_tokens_used + completion_used

    logger.log_execution_time("assemble_notebook_node", time.time() - start_time)
    return res


def exploratory_conclusions_node(state: AnalysisState) -> Dict[str, Any]:
    """Execute Exploratory Conclusions Agent."""
    start_time = time.time()
    exploratory_agent = AgentFactory.get_agent("exploratory_conclusions")
    start_tokens = exploratory_agent.llm_agent.total_tokens
    start_prompt = exploratory_agent.llm_agent.prompt_tokens
    start_completion = exploratory_agent.llm_agent.completion_tokens

    try:
        res = exploratory_agent.process(state)
        tokens_used = exploratory_agent.llm_agent.total_tokens - start_tokens
        prompt_used = exploratory_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = exploratory_agent.llm_agent.completion_tokens - start_completion

        # Track tokens
        if isinstance(res, dict):
            res["total_tokens_used"] = state.total_tokens_used + tokens_used
            res["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
            res["completion_tokens_used"] = state.completion_tokens_used + completion_used

        logger.log_execution_time(
            "exploratory_conclusions_node", time.time() - start_time
        )
        return res
    except Exception as e:
        tokens_used = exploratory_agent.llm_agent.total_tokens - start_tokens
        prompt_used = exploratory_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = exploratory_agent.llm_agent.completion_tokens - start_completion
        logger.log_execution_time(
            "exploratory_conclusions_node (FAILED)", time.time() - start_time
        )
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"ExploratoryConclusions Crash: {str(e)}"],
        }


def rollback_recovery_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute Rollback Recovery.

    Role: Triggered when quality degrades significantly. Reverts state
    to a previous known-good point (if implemented completely) or
    aborts the current deficient branch.
    """
    start_time = time.time()
    orchestrator = AgentFactory.get_agent("orchestrator")
    start_tokens = orchestrator.llm_agent.total_tokens
    start_prompt = orchestrator.llm_agent.prompt_tokens
    start_completion = orchestrator.llm_agent.completion_tokens
    result = orchestrator.process(state, action="rollback_phase2")
    tokens_used = orchestrator.llm_agent.total_tokens - start_tokens
    prompt_used = orchestrator.llm_agent.prompt_tokens - start_prompt
    completion_used = orchestrator.llm_agent.completion_tokens - start_completion

    if isinstance(result, dict):
        result["total_tokens_used"] = state.total_tokens_used + tokens_used
        result["prompt_tokens_used"] = state.prompt_tokens_used + prompt_used
        result["completion_tokens_used"] = state.completion_tokens_used + completion_used

    logger.log_execution_time("rollback_recovery_node", time.time() - start_time)
    return result


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


def sql_extraction_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the SQL Extraction Agent.

    Role: Uses the LLM to generate a SELECT query from the database schema and
    user question, executes it, and saves the result as a CSV for the pipeline.

    Input: UserIntent with db_uri and analysis_question.
    Output: Updated csv_path in state pointing to the extracted CSV.
    """
    start_time = time.time()
    sql_agent = AgentFactory.get_agent("sql_extraction")
    start_tokens = sql_agent.llm_agent.total_tokens
    start_prompt = sql_agent.llm_agent.prompt_tokens
    start_completion = sql_agent.llm_agent.completion_tokens

    try:
        result = sql_agent.process(state)
        tokens_used = sql_agent.llm_agent.total_tokens - start_tokens
        prompt_used = sql_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = sql_agent.llm_agent.completion_tokens - start_completion

        logger.log_execution_time("sql_extraction_node", time.time() - start_time)

        updates: Dict[str, Any] = {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }

        if result.get("csv_path"):
            updates["csv_path"] = result["csv_path"]
        if result.get("errors"):
            updates["errors"] = state.errors + result["errors"]

        return updates
    except Exception as e:
        tokens_used = sql_agent.llm_agent.total_tokens - start_tokens
        prompt_used = sql_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = sql_agent.llm_agent.completion_tokens - start_completion
        logger.log_execution_time("sql_extraction_node (FAILED)", time.time() - start_time)
        logger.error(f"SQLExtraction Crash: {e}", exc_info=True)
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"SQLExtraction Crash: {str(e)}"],
        }


def data_merger_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the Data Merger Agent.

    Role: Merges multiple input files into a single dataset if required.
    """
    start_time = time.time()
    data_merger = AgentFactory.get_agent("data_merger")
    start_tokens = data_merger.llm_agent.total_tokens
    start_prompt = data_merger.llm_agent.prompt_tokens
    start_completion = data_merger.llm_agent.completion_tokens

    try:
        result = data_merger.process(state)
        tokens_used = data_merger.llm_agent.total_tokens - start_tokens
        prompt_used = data_merger.llm_agent.prompt_tokens - start_prompt
        completion_used = data_merger.llm_agent.completion_tokens - start_completion

        logger.log_execution_time("data_merger_node", time.time() - start_time)
        if "error" in result:
            return {
                "errors": state.errors + [result["error"]],
                "total_tokens_used": state.total_tokens_used + tokens_used,
                "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
                "completion_tokens_used": state.completion_tokens_used + completion_used,
            }

        return {
            "merged_dataset": result.get("merged_dataset"),
            "join_report": result.get("join_report"),
            "csv_path": result.get(
                "csv_path", state.csv_path
            ),  # Update path to merged file
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }
    except Exception as e:
        tokens_used = data_merger.llm_agent.total_tokens - start_tokens
        prompt_used = data_merger.llm_agent.prompt_tokens - start_prompt
        completion_used = data_merger.llm_agent.completion_tokens - start_completion
        logger.log_execution_time("data_merger_node (FAILED)", time.time() - start_time)
        logger.error(f"DataMerger Crash: {e}", exc_info=True)
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"DataMerger Crash: {str(e)}"],
        }


def api_extraction_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Execute the API Extraction Agent.

    Role: Fetches data from a REST API endpoint, handles pagination,
    and saves the result as a CSV for the pipeline.

    Input: UserIntent with api_url (and optional api_headers, api_auth, json_path).
    Output: Updated csv_path in state pointing to the extracted CSV.
    """
    start_time = time.time()
    api_agent = AgentFactory.get_agent("api_extraction")
    start_tokens = api_agent.llm_agent.total_tokens
    start_prompt = api_agent.llm_agent.prompt_tokens
    start_completion = api_agent.llm_agent.completion_tokens

    try:
        result = api_agent.process(state)
        tokens_used = api_agent.llm_agent.total_tokens - start_tokens
        prompt_used = api_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = api_agent.llm_agent.completion_tokens - start_completion

        logger.log_execution_time("api_extraction_node", time.time() - start_time)

        updates: Dict[str, Any] = {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
        }

        if result.get("csv_path"):
            updates["csv_path"] = result["csv_path"]
        if result.get("errors"):
            updates["errors"] = state.errors + result["errors"]

        return updates
    except Exception as e:
        tokens_used = api_agent.llm_agent.total_tokens - start_tokens
        prompt_used = api_agent.llm_agent.prompt_tokens - start_prompt
        completion_used = api_agent.llm_agent.completion_tokens - start_completion
        logger.log_execution_time("api_extraction_node (FAILED)", time.time() - start_time)
        logger.error(f"APIExtraction Crash: {e}", exc_info=True)
        return {
            "total_tokens_used": state.total_tokens_used + tokens_used,
            "prompt_tokens_used": state.prompt_tokens_used + prompt_used,
            "completion_tokens_used": state.completion_tokens_used + completion_used,
            "errors": state.errors + [f"APIExtraction Crash: {str(e)}"],
        }


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
