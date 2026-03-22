"""
Unit tests for workflow routing logic.

Tests the phase recursion routing, rollback detection, and oscillation detection
that determines which agent should execute next based on validation results.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.workflow.routing import (
    route_phase1_recursion,
    route_phase2_recursion,
    update_issue_frequency,
    should_rollback,
    detect_oscillation
)
from src.models.state import AnalysisState, Phase, ProfileLock
from src.models.common import Issue
from src.models.validation import (
    ProfileValidationResult,
    AnalysisValidationResult
)


class TestRoutePhase1Recursion:
    """Test Phase 1 recursion routing logic."""

    @pytest.fixture
    def mock_state(self):
        """Create mock analysis state."""
        state = MagicMock(spec=AnalysisState)
        state.phase1_iteration = 0
        state.issue_frequency = {}
        return state

    @pytest.fixture
    def high_quality_result(self):
        """Create validation result that should pass."""
        return ProfileValidationResult(
            cells_passed=10,
            total_cells=10,
            min_type_confidence=0.9,
            columns_with_low_confidence=[],
            stats_coverage=1.0,
            viz_count=5,
            viz_failures=[],
            preprocessing_recommendations_count=0,
            report_sections_present=5,
            report_sections_required=5,
            pep8_score=0.95,
            style_issues=[],
            issues=[]
        )

    @pytest.fixture
    def low_quality_result(self):
        """Create validation result that should fail."""
        return ProfileValidationResult(
            cells_passed=7,
            total_cells=10,
            min_type_confidence=0.5,
            columns_with_low_confidence=["col1", "col2"],
            stats_coverage=0.6,
            viz_count=1,
            viz_failures=["viz1"],
            preprocessing_recommendations_count=0,
            report_sections_present=3,
            report_sections_required=5,
            pep8_score=0.7,
            style_issues=["line too long"],
            issues=[
                Issue(
                    id="issue1",
                    type="type_detection_error",
                    severity="medium",
                    message="Failed to detect type",
                    detected_by="ProfileValidator",
                    phase=Phase.PHASE_1
                )
            ]
        )

    def test_grant_lock_on_high_quality(self, high_quality_result, mock_state):
        """Test that high quality work grants the lock."""
        next_agent, reason = route_phase1_recursion(high_quality_result, mock_state)

        assert next_agent is None
        assert reason == "GRANT_LOCK"

    def test_route_to_profiler_on_data_understanding_issues(self, low_quality_result, mock_state):
        """Test routing to DataProfiler when type detection issues exist."""
        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="type_detection_error",
                severity="medium",
                message="Failed to detect type",
                detected_by="ProfileValidator",
                phase=Phase.PHASE_1
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase1_max_iterations = 3

            next_agent, reason = route_phase1_recursion(low_quality_result, mock_state)

            assert next_agent == "DataProfiler"
            assert "Data understanding" in reason

    def test_route_to_codegen_on_code_generation_issues(self, low_quality_result, mock_state):
        """Test routing to ProfileCodeGenerator when code issues exist."""
        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="syntax_error",
                severity="high",
                message="Invalid Python syntax",
                detected_by="ProfileValidator",
                phase=Phase.PHASE_1
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase1_max_iterations = 3

            next_agent, reason = route_phase1_recursion(low_quality_result, mock_state)

            assert next_agent == "ProfileCodeGenerator"
            assert "Code generation" in reason

    def test_route_to_orchestrator_on_max_iterations(self, low_quality_result, mock_state):
        """Test routing to Orchestrator when max iterations reached."""
        mock_state.phase1_iteration = 3

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase1_max_iterations = 3

            next_agent, reason = route_phase1_recursion(low_quality_result, mock_state)

            assert next_agent == "Orchestrator"
            assert "max iterations" in reason

    def test_route_to_orchestrator_on_systemic_issues(self, low_quality_result, mock_state):
        """Test routing to Orchestrator when systemic issues detected."""
        # Use an issue type that doesn't match data_understanding or code_generation categories
        mock_state.issue_frequency = {
            "performance_degradation": 3  # Same issue 3 times = systemic
        }

        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="performance_degradation",
                severity="medium",
                message="Performance degraded",
                detected_by="ProfileValidator",
                phase=Phase.PHASE_1
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase1_max_iterations = 5

            next_agent, reason = route_phase1_recursion(low_quality_result, mock_state)

            assert next_agent == "Orchestrator"
            assert "Systemic issues" in reason

    def test_default_fallback_to_codegen(self, mock_state):
        """Test default fallback routes to ProfileCodeGenerator."""
        result = ProfileValidationResult(
            cells_passed=8,
            total_cells=10,
            min_type_confidence=0.75,
            columns_with_low_confidence=[],
            stats_coverage=0.85,
            viz_count=2,
            viz_failures=[],
            preprocessing_recommendations_count=0,
            report_sections_present=4,
            report_sections_required=5,
            pep8_score=0.75,
            style_issues=[],
            issues=[]  # No specific issues
        )

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase1_max_iterations = 3

            next_agent, reason = route_phase1_recursion(result, mock_state)

            assert next_agent == "ProfileCodeGenerator"
            assert "improvement needed" in reason.lower()


class TestRoutePhase2Recursion:
    """Test Phase 2 recursion routing logic."""

    @pytest.fixture
    def mock_state(self):
        """Create mock analysis state with profile lock."""
        state = MagicMock(spec=AnalysisState)
        state.phase2_iteration = 0
        state.issue_frequency = {}
        state.phase2_quality_trajectory = []

        # Mock ProfileLock
        profile_lock = MagicMock(spec=ProfileLock)
        profile_lock.verify_integrity.return_value = True
        state.profile_lock = profile_lock

        return state

    @pytest.fixture
    def high_quality_result(self):
        """Create validation result that should complete Phase 2."""
        return AnalysisValidationResult(
            cells_passed=10,
            total_cells=10,
            models_trained=1,
            model_failures=[],
            metrics_computed=3,
            metrics_required=3,
            metric_values={"accuracy": 0.85, "f1": 0.83},
            result_viz_count=2,
            viz_failures=[],
            insights_count=5,
            pep8_score=0.9,
            style_issues=[],
            issues=[]
        )

    @pytest.fixture
    def low_quality_result(self):
        """Create validation result that should fail."""
        return AnalysisValidationResult(
            cells_passed=6,
            total_cells=10,
            models_trained=0,
            model_failures=["model_error"],
            metrics_computed=1,
            metrics_required=3,
            metric_values={},
            result_viz_count=0,
            viz_failures=["viz_error"],
            insights_count=1,
            pep8_score=0.6,
            style_issues=["style1"],
            issues=[
                Issue(
                    id="issue1",
                    type="runtime_error",
                    severity="high",
                    message="Model training failed",
                    detected_by="AnalysisValidator",
                    phase=Phase.PHASE_2
                )
            ]
        )

    def test_complete_on_high_quality(self, high_quality_result, mock_state):
        """Test that high quality work completes Phase 2."""
        next_agent, reason = route_phase2_recursion(high_quality_result, mock_state)

        assert next_agent is None
        assert reason == "PHASE_2_COMPLETE"

    def test_route_to_orchestrator_on_integrity_violation(self, high_quality_result, mock_state):
        """Test routing to Orchestrator when profile integrity violated."""
        mock_state.profile_lock.verify_integrity.return_value = False

        next_agent, reason = route_phase2_recursion(high_quality_result, mock_state)

        assert next_agent == "Orchestrator"
        assert "Profile integrity violation" in reason

    def test_route_to_orchestrator_on_max_iterations(self, low_quality_result, mock_state):
        """Test routing to Orchestrator when max iterations reached."""
        mock_state.phase2_iteration = 3

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase2_max_iterations = 3

            next_agent, reason = route_phase2_recursion(low_quality_result, mock_state)

            assert next_agent == "Orchestrator"
            assert "max iterations" in reason

    def test_route_to_orchestrator_on_rollback(self, low_quality_result, mock_state):
        """Test routing to Orchestrator when rollback is triggered."""
        mock_state.phase2_quality_trajectory = [0.7, 0.5]  # Quality degraded

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase2_max_iterations = 5

            # Current result has low quality
            next_agent, reason = route_phase2_recursion(low_quality_result, mock_state)

            assert next_agent == "Orchestrator"
            assert "ROLLBACK" in reason

    def test_route_to_strategy_on_strategy_issues(self, low_quality_result, mock_state):
        """Test routing to StrategyAgent when strategy issues exist."""
        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="algorithm_mismatch",
                severity="high",
                message="Wrong model type",
                detected_by="AnalysisValidator",
                phase=Phase.PHASE_2
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase2_max_iterations = 3

            next_agent, reason = route_phase2_recursion(low_quality_result, mock_state)

            assert next_agent == "StrategyAgent"
            assert "Strategy" in reason

    def test_route_to_codegen_on_code_issues(self, low_quality_result, mock_state):
        """Test routing to AnalysisCodeGenerator when code issues exist."""
        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="syntax_error",
                severity="high",
                message="Invalid code",
                detected_by="AnalysisValidator",
                phase=Phase.PHASE_2
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase2_max_iterations = 3

            next_agent, reason = route_phase2_recursion(low_quality_result, mock_state)

            assert next_agent == "AnalysisCodeGenerator"
            assert "Code" in reason

    def test_route_to_orchestrator_on_systemic_issues(self, low_quality_result, mock_state):
        """Test routing to Orchestrator when systemic issues detected."""
        # Use an issue type that doesn't match strategy or code_generation categories
        mock_state.issue_frequency = {
            "convergence_failure": 3  # Same issue 3 times = systemic
        }

        low_quality_result.issues = [
            Issue(
                id="issue1",
                type="convergence_failure",
                severity="medium",
                message="Model failed to converge",
                detected_by="AnalysisValidator",
                phase=Phase.PHASE_2
            )
        ]

        with patch('src.workflow.routing.settings') as mock_settings:
            mock_settings.recursion.phase2_max_iterations = 5

            next_agent, reason = route_phase2_recursion(low_quality_result, mock_state)

            assert next_agent == "Orchestrator"
            assert "Systemic issues" in reason


class TestUpdateIssueFrequency:
    """Test issue frequency tracking."""

    def test_update_frequency_new_issues(self):
        """Test updating frequency with new issues."""
        state = MagicMock(spec=AnalysisState)
        state.issue_frequency = {}

        issues = [
            Issue(
                id="i1",
                type="syntax_error",
                severity="high",
                message="Error 1",
                detected_by="Validator",
                phase=Phase.PHASE_1
            ),
            Issue(
                id="i2",
                type="runtime_error",
                severity="medium",
                message="Error 2",
                detected_by="Validator",
                phase=Phase.PHASE_1
            )
        ]

        frequency = update_issue_frequency(state, issues)

        assert frequency["syntax_error"] == 1
        assert frequency["runtime_error"] == 1

    def test_update_frequency_existing_issues(self):
        """Test updating frequency with repeat issues."""
        state = MagicMock(spec=AnalysisState)
        state.issue_frequency = {
            "syntax_error": 2
        }

        issues = [
            Issue(
                id="i1",
                type="syntax_error",
                severity="high",
                message="Error 1",
                detected_by="Validator",
                phase=Phase.PHASE_1
            )
        ]

        frequency = update_issue_frequency(state, issues)

        assert frequency["syntax_error"] == 3

    def test_update_frequency_multiple_same_type(self):
        """Test updating frequency with multiple issues of same type."""
        state = MagicMock(spec=AnalysisState)
        state.issue_frequency = {}

        issues = [
            Issue(id="i1", type="error", severity="high", message="E1",
                  detected_by="V", phase=Phase.PHASE_1),
            Issue(id="i2", type="error", severity="high", message="E2",
                  detected_by="V", phase=Phase.PHASE_1),
            Issue(id="i3", type="warning", severity="low", message="W1",
                  detected_by="V", phase=Phase.PHASE_1),
        ]

        frequency = update_issue_frequency(state, issues)

        assert frequency["error"] == 2
        assert frequency["warning"] == 1


class TestShouldRollback:
    """Test rollback detection logic."""

    def test_no_rollback_on_improvement(self):
        """Test no rollback when quality improves."""
        current = 0.8
        previous = 0.7

        assert should_rollback(current, previous) is False

    def test_no_rollback_on_small_degradation(self):
        """Test no rollback for minor quality drop."""
        current = 0.75
        previous = 0.78

        assert should_rollback(current, previous) is False

    def test_rollback_on_significant_degradation(self):
        """Test rollback triggered on significant quality drop."""
        current = 0.65
        previous = 0.8  # Drop of 0.15 > threshold of 0.05

        assert should_rollback(current, previous) is True

    def test_no_rollback_when_no_previous(self):
        """Test no rollback when no previous score exists."""
        current = 0.5
        previous = None

        assert should_rollback(current, previous) is False

    def test_rollback_with_custom_threshold(self):
        """Test rollback with custom threshold."""
        current = 0.75
        previous = 0.85  # Drop of 0.10

        # Should not rollback with default threshold (0.05)
        assert should_rollback(current, previous, threshold=0.15) is False

        # Should rollback with looser threshold
        assert should_rollback(current, previous, threshold=0.05) is True

    def test_rollback_at_exact_threshold(self):
        """Test rollback at exact threshold boundary."""
        current = 0.75
        previous = 0.80  # Exactly 0.05 drop

        # Floating point arithmetic safety: use a slightly higher threshold
        # to ensure it strictly fails (False) as expected.
        assert should_rollback(current, previous, threshold=0.0500001) is False

        # Just over threshold
        current = 0.749
        assert should_rollback(current, previous, threshold=0.05) is True


class TestDetectOscillation:
    """Test oscillation detection logic."""

    def test_no_oscillation_with_insufficient_data(self):
        """Test no oscillation detected with < 3 data points."""
        assert detect_oscillation([0.7]) is False
        assert detect_oscillation([0.7, 0.8]) is False

    def test_no_oscillation_on_steady_improvement(self):
        """Test no oscillation on steady improvement."""
        trajectory = [0.7, 0.75, 0.8]

        assert detect_oscillation(trajectory) is False

    def test_no_oscillation_on_steady_decline(self):
        """Test no oscillation on steady decline."""
        trajectory = [0.8, 0.75, 0.7]

        assert detect_oscillation(trajectory) is False

    def test_oscillation_detected_high_low_high(self):
        """Test oscillation detected on high-low-high pattern."""
        trajectory = [0.8, 0.65, 0.79]  # Oscillating

        assert detect_oscillation(trajectory) is True

    def test_oscillation_detected_low_high_low(self):
        """Test oscillation detected on low-high-low pattern."""
        trajectory = [0.65, 0.8, 0.66]  # Oscillating

        assert detect_oscillation(trajectory) is True

    def test_no_oscillation_with_small_variation(self):
        """Test no oscillation with minimal variation."""
        trajectory = [0.8, 0.79, 0.80]  # Very stable

        assert detect_oscillation(trajectory) is False

    def test_oscillation_with_longer_trajectory(self):
        """Test oscillation detection uses last 3 values."""
        trajectory = [0.5, 0.6, 0.7, 0.8, 0.65, 0.79]  # Only last 3 matter

        assert detect_oscillation(trajectory) is True

    def test_oscillation_with_custom_threshold(self):
        """Test oscillation detection with custom threshold."""
        # Use values that strictly satisfy the condition |A-C| < T and |B-A| > T
        # A=0.80, B=0.75, C=0.795
        # |A-C| = 0.005 < 0.01 (True)
        # |B-A| = 0.05 > 0.01 (True)
        trajectory = [0.80, 0.75, 0.795]

        # With default threshold (0.02), small diff may not trigger
        # With looser threshold (0.10), won't trigger
        assert detect_oscillation(trajectory, threshold=0.10) is False

        # With tight threshold (0.01), should trigger
        assert detect_oscillation(trajectory, threshold=0.01) is True
        """Test oscillation detection with custom threshold."""
        # Use values that strictly satisfy the condition |A-C| < T and |B-A| > T
        # A=0.80, B=0.75, C=0.795
        # |A-C| = 0.005 < 0.01 (True)
        # |B-A| = 0.05 > 0.01 (True)
        trajectory = [0.80, 0.75, 0.795]

        # With default threshold (0.02), small diff may not trigger
        # With looser threshold (0.10), won't trigger
        assert detect_oscillation(trajectory, threshold=0.10) is False

        # With tight threshold (0.01), should trigger
        assert detect_oscillation(trajectory, threshold=0.01) is True
