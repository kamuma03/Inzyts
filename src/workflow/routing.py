"""
Recursion routing logic for Phase 1 and Phase 2.

This module contains the pure helper functions that determine the next step
in the workflow based on validation results, iteration counts, and quality
metrics. It implements the "Reflexion" pattern where agents are routed back
to improve their work upon failure.
"""

from typing import Dict, Optional, Tuple

from src.models.state import AnalysisState
from src.models.validation import (
    ProfileValidationResult,
    AnalysisValidationResult,
    calculate_phase1_quality,
    calculate_phase2_quality,
    has_data_understanding_issues,
    has_code_generation_issues,
    has_strategy_issues,
    has_systemic_issues,
)
from src.config import settings


def route_phase1_recursion(
    validation_result: ProfileValidationResult, state: AnalysisState
) -> Tuple[Optional[str], str]:
    """
    Determine the next agent in Phase 1 (Data Understanding).

    Logic:
    1. Calculate quality score.
    2. If score >= threshold -> GRANT_LOCK (next_agent = None).
    3. If max iterations reached -> Orchestrator (abort/finalize).
    4. Specific issue routing:
       - Data misunderstanding -> DataProfiler
       - Code syntax/logic errors -> ProfileCodeGenerator
       - Systemic failures -> Orchestrator

    Args:
        validation_result: The report from Profile Validator.
        state: Current analysis state.

    Returns:
        Tuple of (Next Agent Name | None, Reason String)
    """
    # 1. Check if the work meets the quality bar
    quality_score, should_lock = calculate_phase1_quality(validation_result)

    if should_lock:
        return None, "GRANT_LOCK"

    # 2. Check iteration safety limits
    if state.phase1_iteration >= settings.recursion.phase1_max_iterations:
        return "Orchestrator", "Phase 1 max iterations reached"

    # 3. Analyze specific issues to route correctly
    issues = validation_result.issues

    # If the Profiler misidentified types or missed columns, go back to Profiler
    if has_data_understanding_issues(issues):
        return "DataProfiler", "Data understanding needs improvement"

    # If the Profiler was correct but the Code Generator wrote bad code, go back to CodeGen
    if has_code_generation_issues(issues):
        return "ProfileCodeGenerator", "Code generation needs improvement"

    # If the same issues keep appearing despite retries, escalate
    if has_systemic_issues(issues, state.issue_frequency):
        return "Orchestrator", "Systemic issues in Phase 1"

    # Default Fallback: Assume it's a code generation issue
    return "ProfileCodeGenerator", "General improvement needed"


def route_phase2_recursion(
    validation_result: AnalysisValidationResult, state: AnalysisState
) -> Tuple[Optional[str], str]:
    """
    Determine the next agent in Phase 2 (Analysis & Modeling).

    Logic:
    1. Verify Profile Integrity (Safety Check).
    2. Calculate quality score.
    3. If score >= threshold -> COMPLETE (next_agent = None).
    4. If max iterations reached -> Orchestrator.
    5. Check for Quality Degradation (Rollback).
    6. Specific issue routing:
       - Bad Strategy -> StrategyAgent
       - Bad Code -> AnalysisCodeGenerator

    Args:
        validation_result: The report from Analysis Validator.
        state: Current analysis state.

    Returns:
        Tuple of (Next Agent Name | None, Reason String)
    """
    # 0. CRITICAL: Ensure Phase 1 Lock hasn't been violated
    if not state.profile_lock.verify_integrity():
        return "Orchestrator", "CRITICAL: Profile integrity violation detected"

    # 1. Check if the work meets the quality bar
    quality_score, is_complete = calculate_phase2_quality(validation_result)

    if is_complete:
        return None, "PHASE_2_COMPLETE"

    # 2. Check iteration safety limits
    if state.phase2_iteration >= settings.recursion.phase2_max_iterations:
        return "Orchestrator", "Phase 2 max iterations reached"

    # 3. Check for Rollback (did we make it worse?)
    previous_score = (
        state.phase2_quality_trajectory[-2]
        if len(state.phase2_quality_trajectory) >= 2
        else None
    )
    if should_rollback(quality_score, previous_score):
        # Trigger explicit rollback mechanism via Orchestrator
        return "Orchestrator", "ROLLBACK_TRIGGERED"

    # 4. Analyze specific issues to route correctly
    issues = validation_result.issues

    # Strategy was flawed (e.g., wrong model type selected)
    if has_strategy_issues(issues):
        return "StrategyAgent", "Strategy needs refinement"

    # Implementation was flawed (e.g., syntax error, API mismatch)
    if has_code_generation_issues(issues):
        return "AnalysisCodeGenerator", "Code needs improvement"

    # Systemic failures
    if has_systemic_issues(issues, state.issue_frequency):
        return "Orchestrator", "Systemic issues in Phase 2"

    # Default Fallback
    return "AnalysisCodeGenerator", "General improvement needed"


def update_issue_frequency(state: AnalysisState, issues: list) -> Dict[str, int]:
    """
    Update the frequency counter for different issue types.
    Used to detect systemic issues (e.g., failing the same check 3 times).

    Args:
        state: Current state (with history).
        issues: List of new issues from the validator.

    Returns:
        Updated frequency dictionary.
    """
    frequency = state.issue_frequency.copy()
    for issue in issues:
        issue_type = issue.type if hasattr(issue, "type") else str(issue)
        frequency[issue_type] = frequency.get(issue_type, 0) + 1
    return frequency


def should_rollback(
    current_score: float, previous_score: float | None, threshold: float = 0.05
) -> bool:
    """
    Determine if a rollback needs to be triggered.

    A rollback is triggered if the quality score drops significantly
    compared to the previous iteration ('Making it worse').

    Args:
        current_score: Score of the current iteration.
        previous_score: Score of the immediate previous iteration.
        threshold: How much drop is allowed before rollback.

    Returns:
        True if rollback is needed.
    """
    if previous_score is None:
        return False
    return (previous_score - current_score) > threshold


def detect_oscillation(trajectory: list, threshold: float = 0.02) -> bool:
    """
    Detect if quality scores are oscillating (bouncing up and down).

    Oscillation suggests the agents are stuck in a loop of fixing one thing
    but breaking another ("Whac-A-Mole").

    Args:
        trajectory: List of quality scores.
        threshold: delta for minimal variation.

    Returns:
        True if oscillation is detected.
    """
    if len(trajectory) < 3:
        return False

    # Check if last 3 scores form a pattern like High -> Low -> High
    recent = trajectory[-3:]
    # Simplistic check: A similar to C, but different from B
    if (
        abs(recent[0] - recent[2]) < threshold
        and abs(recent[1] - recent[0]) > threshold
    ):
        return True
    return False
