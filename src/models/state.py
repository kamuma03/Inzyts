"""
State models for the Multi-Agent Data Analysis System.

Defines the central AnalysisState, Phase enum, and ProfileLock mechanism.
"""

import hashlib
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from src.models.handoffs import (
    UserIntent,
    ProfilerToCodeGenHandoff,
    ProfileCodeToValidatorHandoff,
    StrategyToCodeGenHandoff,
    RootCauseStrategy,
    DimensionalityStrategyHandoff,
    AnalysisCodeToValidatorHandoff,
    ProfileToStrategyHandoff,
    PipelineMode,
    ExploratoryConclusionsOutput,
    ForecastingExtension,
    ComparativeExtension,
    DiagnosticExtension,
    RemediationPlan,
    ProfileCache,
)
from src.models.validation import ValidationReport
from src.models.multi_file import MultiFileInput, MergedDataset, JoinExecutionReport


from src.models.common import Phase, LockStatus, EscalationEvent


class ProfileLock(BaseModel):
    """
    Immutable lock on Phase 1 outputs.

    The ProfileLock serves as a "gateway" between Phase 1 and Phase 2.
    Once granted, it ensures that the Data Profiling results (schema, data types,
    quality assessment) cannot be modified by downstream agents. This prevents
    hallucinations or drift where the Strategy Agent might "imagine" columns
    that don't exist.

    Attributes:
        status: Current lock status (UNLOCKED, PENDING, LOCKED, FAILED).
        locked_at: Timestamp when lock was granted.
        locked_by: Agent ID that granted the lock (usually Profile Validator).
    """

    status: LockStatus = LockStatus.UNLOCKED
    locked_at: Optional[datetime] = None
    locked_by: str = "Profile Validator"

    # Locked artifacts (set on lock)
    profile_cells: List[Any] = []  # List[NotebookCell]
    profile_handoff: Optional["ProfileToStrategyHandoff"] = (
        None  # ProfileToStrategyHandoff
    )
    phase1_quality_score: float = 0.0
    phase1_validation_report: Optional[Any] = None  # ValidationReport

    # Lock metadata
    lock_reason: str = ""
    iterations_to_lock: int = 0

    # Lock integrity
    lock_hash: str = ""

    @staticmethod
    def _compute_handoff_hash(handoff: Any) -> str:
        """Compute a deterministic integrity hash for the profile handoff.

        Excludes ``profile_cells`` (presentation-only) from the hash to
        reduce serialisation cost — only the data-integrity fields (column
        profiles, quality scores, feature types, etc.) are hashed.
        """
        if not handoff:
            return ""
        # Exclude bulky presentation-only fields from the hash
        data = handoff.model_dump_json(exclude={"profile_cells"})
        return hashlib.sha256(data.encode()).hexdigest()

    def grant_lock(
        self,
        cells: List[Any],
        handoff: Any,
        quality_score: float,
        report: Any,
        iteration: int,
    ) -> bool:
        """
        Grant profile lock if validation passes.
        Returns True if lock granted, False otherwise.
        """
        from src.config import settings
        if quality_score < settings.phase1.quality_threshold:
            self.status = LockStatus.PENDING
            return False

        self.status = LockStatus.LOCKED
        self.locked_at = datetime.now()
        self.profile_cells = deepcopy(cells)  # Immutable copy
        self.profile_handoff = deepcopy(handoff)  # Immutable copy
        self.phase1_quality_score = quality_score
        self.phase1_validation_report = report
        self.lock_reason = "Phase 1 quality threshold met"
        self.iterations_to_lock = iteration
        # Deterministic hash for integrity verification
        try:
            self.lock_hash = self._compute_handoff_hash(self.profile_handoff)
        except Exception as e:
            from src.utils.logger import get_logger
            get_logger().error(f"Hash computation failed during lock grant: {e}")
            self.lock_hash = "hash_error"
            self.status = LockStatus.FAILED
            self.lock_reason = "Hash computation failed"
            return False

        return True

    def verify_integrity(self) -> bool:
        """Check if locked profile has been tampered with."""
        if not self.is_locked():
            return True
        try:
            return self._compute_handoff_hash(self.profile_handoff) == self.lock_hash
        except Exception:
            return False

    def deny_lock(self, reason: str) -> None:
        """Mark lock as failed after max iterations."""
        self.status = LockStatus.FAILED
        self.lock_reason = reason

    def is_locked(self) -> bool:
        """Check if profile is locked."""
        return self.status == LockStatus.LOCKED

    def get_locked_handoff(self) -> Any:
        """
        Retrieve locked handoff for Phase 2.
        Raises if not locked.
        """
        if not self.is_locked():
            raise ProfileNotLockedException(
                f"Profile not locked. Status: {self.status}"
            )
        return self.profile_handoff


class ProfileNotLockedException(Exception):
    """Raised when trying to access locked profile before lock is granted."""

    pass


class ProfileModificationAttemptException(Exception):
    """Raised when Phase 2 agent attempts to modify locked profile."""

    pass


class AnalysisState(BaseModel):
    """
    Central state object shared across all agents and phases.

    This is the main "Context" passed through the LangGraph workflow.
    It functions as a blackboard where agents write their outputs.
    Key components:
    - User Intent: What the user wants to solve.
    - Phase Inputs/Outputs: Storage for each agent's work.
    - Profile Lock: The immutable contract between Phase 1 and 2.
    - Recursion State: Tracking iterations and quality scores.
    """

    # Input
    csv_path: str = ""
    csv_data: Optional[Dict[str, Any]] = (
        None  # DataFrame (stored as dict for serialization)
    )

    _df: Optional[Any] = PrivateAttr(default=None)

    user_intent: Optional["UserIntent"] = None

    # Phase Tracking
    current_phase: Phase = Phase.PHASE_1
    profile_lock: ProfileLock = Field(default_factory=ProfileLock)

    # Phase 1 Outputs
    profiler_outputs: List["ProfilerToCodeGenHandoff"] = []
    profile_code_outputs: List["ProfileCodeToValidatorHandoff"] = []
    profile_validation_reports: List["ValidationReport"] = []

    # Phase 2 Outputs
    # Strategy can vary by mode, so we Union known strategy types
    strategy_outputs: List[
        Union[
            "StrategyToCodeGenHandoff",
            "RootCauseStrategy",
            "DimensionalityStrategyHandoff",
        ]
    ] = []
    analysis_code_outputs: List["AnalysisCodeToValidatorHandoff"] = []
    analysis_validation_reports: List["ValidationReport"] = []

    # Phase 2 Best State (for rollback)
    phase2_best_score: float = 0.0
    phase2_best_strategy: Optional[
        Union[
            "StrategyToCodeGenHandoff",
            "RootCauseStrategy",
            "DimensionalityStrategyHandoff",
        ]
    ] = None
    phase2_best_code: Optional["AnalysisCodeToValidatorHandoff"] = None

    # Recursion Management (per phase)
    phase1_iteration: int = 0
    phase2_iteration: int = 0
    phase1_quality_trajectory: List[float] = []
    phase2_quality_trajectory: List[float] = []
    issue_frequency: Dict[str, int] = {}
    escalation_log: List[EscalationEvent] = []

    # Resource Tracking
    total_tokens_used: int = 0
    prompt_tokens_used: int = 0
    completion_tokens_used: int = 0
    execution_time: float = 0.0

    # Final Output
    final_notebook_path: Optional[str] = None
    final_quality_score: float = 0.0

    errors: List[str] = []
    warnings: List[str] = []

    # v0.10.0: Pipeline Mode & Cache
    pipeline_mode: Optional["PipelineMode"] = None
    cache_status: Optional[Any] = (
        None  # CacheStatus - Avoiding extra import for enum if strictly not needed, but ideally should match. Keeping Any for safety/Enum handling.
    )
    using_cached_profile: bool = False
    cache: Optional["ProfileCache"] = None

    # v0.10.0: Exploratory Output
    exploratory_conclusions: Optional["ExploratoryConclusionsOutput"] = None

    # v1.6.0: Extension Outputs
    forecasting_extension: Optional["ForecastingExtension"] = None
    comparative_extension: Optional["ComparativeExtension"] = None
    diagnostic_extension: Optional["DiagnosticExtension"] = None

    # v1.6.0: Phase 2 Specific Outputs (Explicit storage)
    # These might duplicates strategy outputs but specialized
    segmentation_outputs: List[Any] = []
    forecasting_outputs: List[Any] = []
    comparative_outputs: List[Any] = []
    diagnostic_outputs: List[Any] = []

    # v1.8.0: Multi-File Support
    multi_file_input: Optional[MultiFileInput] = None
    merged_dataset: Optional[MergedDataset] = None
    join_report: Optional[JoinExecutionReport] = None

    # v1.9.0: Data Remediation
    remediation_plans: List["RemediationPlan"] = []

    # v1.9.0: Dimensionality Reduction
    dimensionality_outputs: List[Any] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)
