"""
Unit tests for state models.

Tests the core state models including AnalysisState, Issue, AgentOutput,
Phase enum, and PipelineMode enum.

Coverage includes:
- State initialization
- State updates
- Issue creation
- Phase enum values
- PipelineMode enum values
- JSON serialization
"""

from datetime import datetime

from src.models.state import (
    AnalysisState,
    Phase,
    LockStatus,
    ProfileLock
)
from src.models.common import Issue, AgentOutput, EscalationEvent
from src.models.handoffs import PipelineMode


class TestPhaseEnum:
    """Test Phase enumeration."""

    def test_phase_values(self):
        """Test that Phase enum has correct values."""
        assert Phase.INIT == "init"
        assert Phase.PHASE_1 == "data_understanding"
        assert Phase.EXPLORATORY_CONCLUSIONS == "exploratory_conclusions"
        assert Phase.PHASE_2 == "analysis_modeling"
        assert Phase.ASSEMBLY == "notebook_assembly"
        assert Phase.COMPLETE == "complete"

    def test_phase_enum_membership(self):
        """Test Phase enum membership."""
        assert "init" in [p.value for p in Phase]
        assert "data_understanding" in [p.value for p in Phase]
        assert "complete" in [p.value for p in Phase]

    def test_phase_comparison(self):
        """Test Phase enum comparison."""
        assert Phase.INIT == Phase.INIT
        assert Phase.PHASE_1 != Phase.PHASE_2
        assert Phase.COMPLETE == Phase.COMPLETE


class TestLockStatusEnum:
    """Test LockStatus enumeration."""

    def test_lock_status_values(self):
        """Test that LockStatus enum has correct values."""
        assert LockStatus.UNLOCKED == "unlocked"
        assert LockStatus.PENDING == "pending"
        assert LockStatus.LOCKED == "locked"
        assert LockStatus.FAILED == "failed"

    def test_lock_status_enum_membership(self):
        """Test LockStatus enum membership."""
        statuses = [s.value for s in LockStatus]
        assert "unlocked" in statuses
        assert "pending" in statuses
        assert "locked" in statuses
        assert "failed" in statuses


class TestIssueModel:
    """Test Issue model."""

    def test_issue_creation_minimal(self):
        """Test creating an issue with minimal fields."""
        issue = Issue(
            id="issue-001",
            type="missing_value",
            severity="medium",
            message="Column X has missing values"
        )

        assert issue.id == "issue-001"
        assert issue.type == "missing_value"
        assert issue.severity == "medium"
        assert issue.message == "Column X has missing values"
        assert issue.location is None
        assert issue.suggestion is None
        assert issue.detected_by is None
        assert issue.phase is None

    def test_issue_creation_full(self):
        """Test creating an issue with all fields."""
        issue = Issue(
            id="issue-002",
            type="syntax_error",
            severity="critical",
            message="Invalid Python syntax in cell 5",
            location="cell_5",
            suggestion="Check for unclosed parentheses",
            detected_by="ProfileValidator",
            phase=Phase.PHASE_1
        )

        assert issue.id == "issue-002"
        assert issue.type == "syntax_error"
        assert issue.severity == "critical"
        assert issue.message == "Invalid Python syntax in cell 5"
        assert issue.location == "cell_5"
        assert issue.suggestion == "Check for unclosed parentheses"
        assert issue.detected_by == "ProfileValidator"
        assert issue.phase == Phase.PHASE_1

    def test_issue_severity_levels(self):
        """Test different severity levels."""
        for severity in ["info", "warning", "error", "critical"]:
            issue = Issue(
                id=f"issue-{severity}",
                type="test",
                severity=severity,
                message=f"Test {severity} issue"
            )
            assert issue.severity == severity

    def test_issue_json_serialization(self):
        """Test Issue can be serialized to JSON."""
        issue = Issue(
            id="issue-003",
            type="data_quality",
            severity="warning",
            message="High percentage of missing values",
            location="age_column",
            phase=Phase.PHASE_1
        )

        # Pydantic v2 style
        if hasattr(issue, 'model_dump_json'):
            json_str = issue.model_dump_json()
        else:
            json_str = issue.json()

        assert "issue-003" in json_str
        assert "data_quality" in json_str
        assert "warning" in json_str


class TestEscalationEvent:
    """Test EscalationEvent model."""

    def test_escalation_event_creation(self):
        """Test creating an escalation event."""
        event = EscalationEvent(
            from_agent="ProfileValidator",
            reason="Quality threshold not met after 3 iterations",
            iteration=3,
            phase=Phase.PHASE_1
        )

        assert event.from_agent == "ProfileValidator"
        assert event.reason == "Quality threshold not met after 3 iterations"
        assert event.iteration == 3
        assert event.phase == Phase.PHASE_1
        assert isinstance(event.timestamp, datetime)

    def test_escalation_event_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated."""
        event1 = EscalationEvent(
            from_agent="Agent1",
            reason="Test",
            iteration=1,
            phase=Phase.PHASE_1
        )

        event2 = EscalationEvent(
            from_agent="Agent2",
            reason="Test",
            iteration=2,
            phase=Phase.PHASE_2
        )

        # Timestamps should be close but not identical
        assert isinstance(event1.timestamp, datetime)
        assert isinstance(event2.timestamp, datetime)


class TestAgentOutput:
    """Test AgentOutput model."""

    def test_agent_output_creation(self):
        """Test creating an agent output."""
        output = AgentOutput(
            agent_name="DataProfiler",
            phase=Phase.PHASE_1,
            result={"profiling": "complete"},
            confidence=0.95,
            issues=[],
            suggestions=["Consider removing outliers"],
            iteration=1,
            execution_time=2.5,
            tokens_used=1500
        )

        assert output.agent_name == "DataProfiler"
        assert output.phase == Phase.PHASE_1
        assert output.result == {"profiling": "complete"}
        assert output.confidence == 0.95
        assert len(output.issues) == 0
        assert len(output.suggestions) == 1
        assert output.iteration == 1
        assert output.execution_time == 2.5
        assert output.tokens_used == 1500

    def test_agent_output_with_issues(self):
        """Test agent output with issues."""
        issues = [
            Issue(
                id="issue-1",
                type="warning",
                severity="medium",
                message="Test issue"
            )
        ]

        output = AgentOutput(
            agent_name="TestAgent",
            phase=Phase.PHASE_2,
            result={},
            confidence=0.7,
            issues=issues,
            suggestions=[],
            iteration=2,
            execution_time=1.0,
            tokens_used=500
        )

        assert len(output.issues) == 1
        assert output.issues[0].id == "issue-1"


class TestAnalysisStateInitialization:
    """Test AnalysisState initialization."""

    def test_state_initialization_minimal(self):
        """Test state initialization with minimal parameters."""
        state = AnalysisState()

        assert state.csv_path == ""
        assert state.csv_data is None
        assert state.user_intent is None
        assert state.current_phase == Phase.PHASE_1
        assert isinstance(state.profile_lock, ProfileLock)
        assert state.profile_lock.status == LockStatus.UNLOCKED

    def test_state_initialization_with_csv_path(self):
        """Test state initialization with CSV path."""
        state = AnalysisState(csv_path="/data/test.csv")

        assert state.csv_path == "/data/test.csv"
        assert state.current_phase == Phase.PHASE_1

    def test_state_initialization_default_values(self):
        """Test that default values are set correctly."""
        state = AnalysisState()

        # Phase tracking
        assert state.current_phase == Phase.PHASE_1

        # Outputs
        assert state.profiler_outputs == []
        assert state.profile_code_outputs == []
        assert state.profile_validation_reports == []
        assert state.strategy_outputs == []
        assert state.analysis_code_outputs == []
        assert state.analysis_validation_reports == []

        # Recursion management
        assert state.phase1_iteration == 0
        assert state.phase2_iteration == 0
        assert state.phase1_quality_trajectory == []
        assert state.phase2_quality_trajectory == []
        assert state.issue_frequency == {}
        assert state.escalation_log == []

        # Resource tracking
        assert state.total_tokens_used == 0
        assert state.execution_time == 0.0

        # Final output
        assert state.final_notebook_path is None
        assert state.final_quality_score == 0.0
        assert state.errors == []
        assert state.warnings == []

    def test_state_initialization_with_phase(self):
        """Test state initialization with specific phase."""
        state = AnalysisState(current_phase=Phase.PHASE_2)

        assert state.current_phase == Phase.PHASE_2


class TestAnalysisStateUpdates:
    """Test AnalysisState updates."""

    def test_update_phase(self):
        """Test updating current phase."""
        state = AnalysisState()
        assert state.current_phase == Phase.PHASE_1

        state.current_phase = Phase.PHASE_2
        assert state.current_phase == Phase.PHASE_2

    def test_update_profiler_outputs(self):
        """Test updating profiler outputs."""
        state = AnalysisState()
        assert len(state.profiler_outputs) == 0

        state.profiler_outputs.append({"test": "output"})
        assert len(state.profiler_outputs) == 1
        assert state.profiler_outputs[0] == {"test": "output"}

    def test_update_iterations(self):
        """Test updating iteration counters."""
        state = AnalysisState()
        assert state.phase1_iteration == 0
        assert state.phase2_iteration == 0

        state.phase1_iteration = 3
        state.phase2_iteration = 2

        assert state.phase1_iteration == 3
        assert state.phase2_iteration == 2

    def test_update_quality_trajectory(self):
        """Test updating quality trajectories."""
        state = AnalysisState()

        state.phase1_quality_trajectory.append(0.7)
        state.phase1_quality_trajectory.append(0.8)
        state.phase1_quality_trajectory.append(0.9)

        assert len(state.phase1_quality_trajectory) == 3
        assert state.phase1_quality_trajectory[-1] == 0.9

    def test_update_tokens_used(self):
        """Test updating total tokens used."""
        state = AnalysisState()
        assert state.total_tokens_used == 0

        state.total_tokens_used += 1000
        state.total_tokens_used += 500

        assert state.total_tokens_used == 1500

    def test_update_errors_and_warnings(self):
        """Test updating errors and warnings."""
        state = AnalysisState()

        state.errors.append("Critical error occurred")
        state.warnings.append("Quality threshold not met")

        assert len(state.errors) == 1
        assert len(state.warnings) == 1
        assert state.errors[0] == "Critical error occurred"

    def test_update_escalation_log(self):
        """Test updating escalation log."""
        state = AnalysisState()

        event = EscalationEvent(
            from_agent="TestAgent",
            reason="Max iterations reached",
            iteration=5,
            phase=Phase.PHASE_1
        )

        state.escalation_log.append(event)

        assert len(state.escalation_log) == 1
        assert state.escalation_log[0].from_agent == "TestAgent"


class TestAnalysisStateExtensions:
    """Test v1.5.0 and v1.6.0 extensions to AnalysisState."""

    def test_pipeline_mode_field(self):
        """Test pipeline mode field."""
        state = AnalysisState(pipeline_mode=PipelineMode.EXPLORATORY)

        assert state.pipeline_mode == PipelineMode.EXPLORATORY

    def test_cache_fields(self):
        """Test cache-related fields."""
        state = AnalysisState()

        assert state.cache_status is None
        assert state.using_cached_profile is False
        assert state.cache is None

        state.using_cached_profile = True
        assert state.using_cached_profile is True

    def test_exploratory_conclusions_field(self):
        """Test exploratory conclusions field."""
        state = AnalysisState()

        assert state.exploratory_conclusions is None

        state.exploratory_conclusions = {"conclusions": "test"}
        assert state.exploratory_conclusions == {"conclusions": "test"}

    def test_extension_fields(self):
        """Test v1.6.0 extension fields."""
        state = AnalysisState()

        assert state.forecasting_extension is None
        assert state.comparative_extension is None
        assert state.diagnostic_extension is None

        assert state.segmentation_outputs == []
        assert state.forecasting_outputs == []
        assert state.comparative_outputs == []
        assert state.diagnostic_outputs == []


class TestAnalysisStatePhase2BestState:
    """Test Phase 2 best state tracking."""

    def test_phase2_best_state_initialization(self):
        """Test Phase 2 best state fields initialize correctly."""
        state = AnalysisState()

        assert state.phase2_best_score == 0.0
        assert state.phase2_best_strategy is None
        assert state.phase2_best_code is None

    def test_phase2_best_state_updates(self):
        """Test updating Phase 2 best state."""
        state = AnalysisState()

        state.phase2_best_score = 0.85
        state.phase2_best_strategy = {"strategy": "test"}
        state.phase2_best_code = {"code": "test"}

        assert state.phase2_best_score == 0.85
        assert state.phase2_best_strategy == {"strategy": "test"}
        assert state.phase2_best_code == {"code": "test"}


class TestAnalysisStateIssueFrequency:
    """Test issue frequency tracking."""

    def test_issue_frequency_initialization(self):
        """Test issue frequency dict initializes empty."""
        state = AnalysisState()

        assert state.issue_frequency == {}

    def test_issue_frequency_tracking(self):
        """Test tracking issue frequencies."""
        state = AnalysisState()

        state.issue_frequency["missing_values"] = 3
        state.issue_frequency["syntax_error"] = 1
        state.issue_frequency["data_quality"] = 2

        assert state.issue_frequency["missing_values"] == 3
        assert state.issue_frequency["syntax_error"] == 1
        assert len(state.issue_frequency) == 3


class TestAnalysisStateJSONSerialization:
    """Test JSON serialization of AnalysisState."""

    def test_state_json_serialization_basic(self):
        """Test basic state can be serialized to JSON."""
        state = AnalysisState(
            csv_path="/data/test.csv",
            current_phase=Phase.PHASE_1
        )

        # Pydantic v2 style
        if hasattr(state, 'model_dump_json'):
            json_str = state.model_dump_json()
        else:
            json_str = state.json()

        assert "/data/test.csv" in json_str
        assert "data_understanding" in json_str

    def test_state_json_serialization_with_data(self):
        """Test state with data can be serialized."""
        state = AnalysisState(
            csv_path="/data/test.csv",
            current_phase=Phase.PHASE_2,
            phase1_iteration=3,
            total_tokens_used=5000,
            execution_time=10.5
        )

        if hasattr(state, 'model_dump_json'):
            json_str = state.model_dump_json()
        else:
            json_str = state.json()

        assert "5000" in json_str
        assert "10.5" in json_str

    def test_state_json_deserialization(self):
        """Test state can be deserialized from JSON."""
        state = AnalysisState(
            csv_path="/data/test.csv",
            phase1_iteration=2
        )

        # Serialize
        if hasattr(state, 'model_dump_json'):
            json_str = state.model_dump_json()
        else:
            json_str = state.json()

        # Deserialize
        if hasattr(AnalysisState, 'model_validate_json'):
            restored = AnalysisState.model_validate_json(json_str)
        else:
            restored = AnalysisState.parse_raw(json_str)

        assert restored.csv_path == "/data/test.csv"
        assert restored.phase1_iteration == 2


class TestAnalysisStateArbitraryTypes:
    """Test that AnalysisState allows arbitrary types."""

    def test_state_allows_arbitrary_types(self):
        """Test that state config allows arbitrary types."""
        state = AnalysisState()

        # Should be able to store complex objects
        state.csv_data = {"complex": "object"}
        state.user_intent = {"intent": "data"}

        assert state.csv_data == {"complex": "object"}
        assert state.user_intent == {"intent": "data"}


class TestPipelineModeEnum:
    """Test PipelineMode enumeration (from handoffs)."""

    def test_pipeline_mode_values(self):
        """Test PipelineMode enum values."""
        assert PipelineMode.EXPLORATORY == "exploratory"
        assert PipelineMode.PREDICTIVE == "predictive"
        assert PipelineMode.DIAGNOSTIC == "diagnostic"
        assert PipelineMode.COMPARATIVE == "comparative"
        assert PipelineMode.FORECASTING == "forecasting"
        assert PipelineMode.SEGMENTATION == "segmentation"

    def test_pipeline_mode_membership(self):
        """Test PipelineMode enum membership."""
        modes = [m.value for m in PipelineMode]
        assert "exploratory" in modes
        assert "predictive" in modes
        assert "forecasting" in modes


class TestStateCompleteWorkflow:
    """Test state through a complete workflow simulation."""

    def test_state_workflow_phase1_to_phase2(self):
        """Test state updates through Phase 1 to Phase 2."""
        # Initialize
        state = AnalysisState(csv_path="/data/test.csv")
        assert state.current_phase == Phase.PHASE_1

        # Phase 1 iteration 1
        state.phase1_iteration = 1
        state.phase1_quality_trajectory.append(0.7)
        state.profiler_outputs.append({"iteration": 1})

        # Phase 1 iteration 2
        state.phase1_iteration = 2
        state.phase1_quality_trajectory.append(0.85)

        # Lock granted, move to Phase 2
        state.current_phase = Phase.PHASE_2
        state.phase2_iteration = 1
        state.phase2_quality_trajectory.append(0.8)

        # Verify state
        assert state.phase1_iteration == 2
        assert state.phase2_iteration == 1
        assert len(state.phase1_quality_trajectory) == 2
        assert state.phase1_quality_trajectory[-1] == 0.85
        assert state.current_phase == Phase.PHASE_2

    def test_state_workflow_with_escalation(self):
        """Test state with escalation events."""
        state = AnalysisState(csv_path="/data/test.csv")

        # Phase 1 iterations with escalation
        for i in range(1, 6):
            state.phase1_iteration = i
            state.phase1_quality_trajectory.append(0.6 + i * 0.05)

        # Escalate after max iterations
        event = EscalationEvent(
            from_agent="ProfileValidator",
            reason="Max iterations reached",
            iteration=5,
            phase=Phase.PHASE_1
        )
        state.escalation_log.append(event)

        assert len(state.escalation_log) == 1
        assert state.phase1_iteration == 5
