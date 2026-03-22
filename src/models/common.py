"""
Common models and enums shared across the application.
Extracted from state.py to resolve circular dependencies.
"""

from enum import Enum
from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Phase(str, Enum):
    """
    Current phase of the analysis workflow.

    Attributes:
        INIT: Initialization.
        PHASE_1: Data Understanding (Profiling, Quality Check).
        EXPLORATORY_CONCLUSIONS: Generating insights without modeling.
        PHASE_2: Analysis & Modeling (Strategy, Code Gen, Validation).
        ASSEMBLY: Final notebook construction.
        COMPLETE: Workflow finished successfully.
    """

    INIT = "init"
    PHASE_1 = "data_understanding"
    EXPLORATORY_CONCLUSIONS = "exploratory_conclusions"
    PHASE_2 = "analysis_modeling"
    ASSEMBLY = "notebook_assembly"
    COMPLETE = "complete"


class LockStatus(str, Enum):
    """Status of the Profile Lock."""

    UNLOCKED = "unlocked"  # Phase 1 in progress
    PENDING = "pending"  # Awaiting validation
    LOCKED = "locked"  # Phase 1 complete, immutable
    FAILED = "failed"  # Phase 1 failed, cannot proceed


class Issue(BaseModel):
    """Represents an issue found during validation."""

    id: str
    type: str
    severity: str  # "error", "warning", "info"
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    detected_by: Optional[str] = None
    phase: Optional[Phase] = None


class EscalationEvent(BaseModel):
    """Records an escalation to the Orchestrator."""

    timestamp: datetime = Field(default_factory=datetime.now)
    from_agent: str
    reason: str
    iteration: int
    phase: Phase


class AgentOutput(BaseModel):
    """Standard output format for all agents."""

    agent_name: str
    phase: Phase
    result: Any
    confidence: float
    issues: List[Issue] = []
    suggestions: List[str] = []
    iteration: int
    execution_time: float
    tokens_used: int
