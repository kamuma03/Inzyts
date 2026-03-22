"""
Unit tests for ProfileLock mechanism.

Tests the ProfileLock class that serves as a gateway between Phase 1 and Phase 2,
ensuring immutability of data profiling results.

Coverage includes:
- Lock grant success/failure
- Lock immutability
- Integrity check
- Hash calculation
- State transitions
- Error conditions
"""

import pytest
from datetime import datetime

from src.models.state import (
    ProfileLock,
    LockStatus,
    ProfileNotLockedException
)
from src.models.handoffs import (
    ProfileToStrategyHandoff,
    ColumnProfile,
    DataType,
    NumericStats,
    TargetCandidate,
    AnalysisType
)
from src.models.cells import NotebookCell


@pytest.fixture
def sample_cells():
    """Create sample notebook cells."""
    return [
        NotebookCell(
            cell_type="markdown",
            source="# Data Profiling Report"
        ),
        NotebookCell(
            cell_type="code",
            source="import pandas as pd"
        ),
        NotebookCell(
            cell_type="code",
            source="df = pd.read_csv('test.csv')"
        )
    ]


@pytest.fixture
def sample_handoff():
    """Create sample ProfileToStrategyHandoff."""
    return ProfileToStrategyHandoff(
        phase1_quality_score=0.85,
        row_count=1000,
        column_count=3,
        column_profiles=(
            ColumnProfile(
                name="age",
                detected_type=DataType.NUMERIC_CONTINUOUS,
                detection_confidence=0.95,
                unique_count=50,
                null_percentage=0.0,
                statistics=NumericStats(mean=35.0, median=33.0, std=10.0)
            ),
            ColumnProfile(
                name="category",
                detected_type=DataType.CATEGORICAL,
                detection_confidence=0.90,
                unique_count=5,
                null_percentage=0.02
            )
        ),
        overall_quality_score=0.85,
        missing_value_summary={"age": 0.0, "category": 0.02},
        recommended_target_candidates=(
            TargetCandidate(
                column_name="category",
                suggested_analysis_type=AnalysisType.CLASSIFICATION,
                rationale="Categorical target with balanced classes",
                confidence=0.8
            ),
        ),
        identified_feature_types={"age": "numeric_continuous"}
    )


@pytest.fixture
def sample_validation_report():
    """Create sample validation report."""
    return {
        "quality_score": 0.85,
        "issues": [],
        "statistics_validated": True,
        "visualizations_validated": True
    }


class TestProfileLockInitialization:
    """Test ProfileLock initialization."""

    def test_lock_initialization_default(self):
        """Test default initialization of ProfileLock."""
        lock = ProfileLock()

        assert lock.status == LockStatus.UNLOCKED
        assert lock.locked_at is None
        assert lock.locked_by == "Profile Validator"
        assert lock.profile_cells == []
        assert lock.profile_handoff is None
        assert lock.phase1_quality_score == 0.0
        assert lock.phase1_validation_report is None
        assert lock.lock_reason == ""
        assert lock.iterations_to_lock == 0
        assert lock.lock_hash == ""

    def test_lock_initialization_custom_locked_by(self):
        """Test initialization with custom locked_by."""
        lock = ProfileLock(locked_by="CustomValidator")

        assert lock.locked_by == "CustomValidator"
        assert lock.status == LockStatus.UNLOCKED


class TestGrantLock:
    """Test lock granting mechanism."""

    def test_grant_lock_success(self, sample_cells, sample_handoff, sample_validation_report):
        """Test successful lock grant."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=3
        )

        assert result is True
        assert lock.status == LockStatus.LOCKED
        assert lock.locked_at is not None
        assert isinstance(lock.locked_at, datetime)
        assert lock.phase1_quality_score == 0.85
        assert lock.iterations_to_lock == 3
        assert lock.lock_reason == "Phase 1 quality threshold met"
        assert lock.lock_hash != ""

    def test_grant_lock_quality_threshold_exactly_80(self, sample_cells, sample_handoff, sample_validation_report):
        """Test lock grant with quality score exactly at threshold."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.80,
            report=sample_validation_report,
            iteration=2
        )

        assert result is True
        assert lock.status == LockStatus.LOCKED

    def test_grant_lock_failure_below_threshold(self, sample_cells, sample_handoff, sample_validation_report):
        """Test lock grant failure when quality below threshold."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.65,
            report=sample_validation_report,
            iteration=1
        )

        assert result is False
        assert lock.status == LockStatus.PENDING
        assert lock.locked_at is None

    def test_grant_lock_failure_very_low_quality(self, sample_cells, sample_handoff, sample_validation_report):
        """Test lock grant failure with very low quality."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )

        assert result is False
        assert lock.status == LockStatus.PENDING

    def test_grant_lock_stores_copies(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that grant_lock stores deep copies of data."""
        lock = ProfileLock()

        original_cells = sample_cells.copy()
        original_handoff = sample_handoff

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.90,
            report=sample_validation_report,
            iteration=1
        )

        # Verify copies were made
        assert lock.profile_cells is not sample_cells
        assert lock.profile_handoff is not sample_handoff

    def test_grant_lock_updates_all_fields(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that grant_lock updates all lock fields."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.92,
            report=sample_validation_report,
            iteration=4
        )

        assert lock.status == LockStatus.LOCKED
        assert lock.locked_at is not None
        assert len(lock.profile_cells) == len(sample_cells)
        assert lock.profile_handoff is not None
        assert lock.phase1_quality_score == 0.92
        assert lock.phase1_validation_report == sample_validation_report
        assert lock.iterations_to_lock == 4
        assert lock.lock_hash != ""


class TestDenyLock:
    """Test lock denial mechanism."""

    def test_deny_lock_basic(self):
        """Test basic lock denial."""
        lock = ProfileLock()

        lock.deny_lock("Maximum iterations reached without meeting quality threshold")

        assert lock.status == LockStatus.FAILED
        assert lock.lock_reason == "Maximum iterations reached without meeting quality threshold"

    def test_deny_lock_after_pending(self, sample_cells, sample_handoff, sample_validation_report):
        """Test denying lock after PENDING state."""
        lock = ProfileLock()

        # First, fail to grant (goes to PENDING)
        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )
        assert lock.status == LockStatus.PENDING

        # Then deny
        lock.deny_lock("Quality did not improve after max iterations")

        assert lock.status == LockStatus.FAILED
        assert "max iterations" in lock.lock_reason

    def test_deny_lock_with_custom_reason(self):
        """Test deny lock with custom reason."""
        lock = ProfileLock()

        lock.deny_lock("Critical validation errors detected")

        assert lock.status == LockStatus.FAILED
        assert lock.lock_reason == "Critical validation errors detected"


class TestIsLocked:
    """Test is_locked method."""

    def test_is_locked_when_unlocked(self):
        """Test is_locked returns False when UNLOCKED."""
        lock = ProfileLock()

        assert lock.is_locked() is False

    def test_is_locked_when_pending(self, sample_cells, sample_handoff, sample_validation_report):
        """Test is_locked returns False when PENDING."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )

        assert lock.status == LockStatus.PENDING
        assert lock.is_locked() is False

    def test_is_locked_when_locked(self, sample_cells, sample_handoff, sample_validation_report):
        """Test is_locked returns True when LOCKED."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=2
        )

        assert lock.status == LockStatus.LOCKED
        assert lock.is_locked() is True

    def test_is_locked_when_failed(self):
        """Test is_locked returns False when FAILED."""
        lock = ProfileLock()
        lock.deny_lock("Test failure")

        assert lock.status == LockStatus.FAILED
        assert lock.is_locked() is False


class TestGetLockedHandoff:
    """Test get_locked_handoff method."""

    def test_get_locked_handoff_success(self, sample_cells, sample_handoff, sample_validation_report):
        """Test retrieving locked handoff successfully."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.88,
            report=sample_validation_report,
            iteration=2
        )

        retrieved = lock.get_locked_handoff()

        assert retrieved is not None
        assert retrieved.row_count == 1000
        assert retrieved.column_count == 3

    def test_get_locked_handoff_raises_when_unlocked(self):
        """Test that get_locked_handoff raises when not locked."""
        lock = ProfileLock()

        with pytest.raises(ProfileNotLockedException) as exc_info:
            lock.get_locked_handoff()

        assert "not locked" in str(exc_info.value).lower()
        assert "unlocked" in str(exc_info.value).lower()

    def test_get_locked_handoff_raises_when_pending(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that get_locked_handoff raises when PENDING."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )

        with pytest.raises(ProfileNotLockedException) as exc_info:
            lock.get_locked_handoff()

        assert "pending" in str(exc_info.value).lower()

    def test_get_locked_handoff_raises_when_failed(self):
        """Test that get_locked_handoff raises when FAILED."""
        lock = ProfileLock()
        lock.deny_lock("Test failure")

        with pytest.raises(ProfileNotLockedException) as exc_info:
            lock.get_locked_handoff()

        assert "failed" in str(exc_info.value).lower()


class TestVerifyIntegrity:
    """Test lock integrity verification."""

    def test_verify_integrity_when_unlocked(self):
        """Test integrity check when unlocked returns True."""
        lock = ProfileLock()

        assert lock.verify_integrity() is True

    def test_verify_integrity_when_locked_and_unchanged(self, sample_cells, sample_handoff, sample_validation_report):
        """Test integrity check passes when data unchanged."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.90,
            report=sample_validation_report,
            iteration=1
        )

        assert lock.verify_integrity() is True

    def test_verify_integrity_detects_tampering(self, sample_cells, sample_handoff, sample_validation_report):
        """Test integrity check detects tampering."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.90,
            report=sample_validation_report,
            iteration=1
        )

        # Tamper with the handoff (simulate modification)
        original_hash = lock.lock_hash

        # Create a modified handoff with different data
        modified_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.95,  # Changed
            row_count=2000,  # Changed
            column_count=3,
            column_profiles=sample_handoff.column_profiles,
            overall_quality_score=0.95,
            missing_value_summary={"age": 0.0}
        )

        # Replace the handoff (simulating tampering)
        lock.profile_handoff = modified_handoff

        # Integrity check should fail
        assert lock.verify_integrity() is False

    def test_verify_integrity_with_none_handoff(self):
        """Test integrity check with None handoff."""
        lock = ProfileLock()
        lock.status = LockStatus.LOCKED
        lock.profile_handoff = None
        lock.lock_hash = ""

        # Should return True (both hash and handoff are empty/None)
        assert lock.verify_integrity() is True


class TestLockHash:
    """Test lock hash calculation."""

    def test_lock_hash_generated_on_grant(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that hash is generated when lock granted."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        assert lock.lock_hash != ""
        assert len(lock.lock_hash) > 0

    def test_lock_hash_consistent(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that hash is consistent for same data."""
        lock1 = ProfileLock()
        lock2 = ProfileLock()

        lock1.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        lock2.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        # Hashes should be identical for same data
        assert lock1.lock_hash == lock2.lock_hash

    def test_lock_hash_different_for_different_data(self, sample_cells, sample_validation_report):
        """Test that hash differs for different handoffs."""
        lock1 = ProfileLock()
        lock2 = ProfileLock()

        handoff1 = ProfileToStrategyHandoff(
            phase1_quality_score=0.85,
            row_count=1000,
            column_count=2,
            column_profiles=(
                ColumnProfile(
                    name="col1",
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.9,
                    unique_count=100,
                    null_percentage=0.0
                ),
            ),
            overall_quality_score=0.85,
            missing_value_summary={}
        )

        handoff2 = ProfileToStrategyHandoff(
            phase1_quality_score=0.90,
            row_count=2000,
            column_count=3,
            column_profiles=(
                ColumnProfile(
                    name="col2",
                    detected_type=DataType.CATEGORICAL,
                    detection_confidence=0.95,
                    unique_count=50,
                    null_percentage=0.1
                ),
            ),
            overall_quality_score=0.90,
            missing_value_summary={}
        )

        lock1.grant_lock(sample_cells, handoff1, 0.85, sample_validation_report, 1)
        lock2.grant_lock(sample_cells, handoff2, 0.90, sample_validation_report, 1)

        assert lock1.lock_hash != lock2.lock_hash


class TestLockStateTransitions:
    """Test state transitions of the lock."""

    def test_transition_unlocked_to_locked(self, sample_cells, sample_handoff, sample_validation_report):
        """Test transition from UNLOCKED to LOCKED."""
        lock = ProfileLock()
        assert lock.status == LockStatus.UNLOCKED

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        assert lock.status == LockStatus.LOCKED

    def test_transition_unlocked_to_pending(self, sample_cells, sample_handoff, sample_validation_report):
        """Test transition from UNLOCKED to PENDING."""
        lock = ProfileLock()
        assert lock.status == LockStatus.UNLOCKED

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )

        assert lock.status == LockStatus.PENDING

    def test_transition_unlocked_to_failed(self):
        """Test transition from UNLOCKED to FAILED."""
        lock = ProfileLock()
        assert lock.status == LockStatus.UNLOCKED

        lock.deny_lock("Quality threshold not met")

        assert lock.status == LockStatus.FAILED

    def test_transition_pending_to_failed(self, sample_cells, sample_handoff, sample_validation_report):
        """Test transition from PENDING to FAILED."""
        lock = ProfileLock()

        # Go to PENDING
        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )
        assert lock.status == LockStatus.PENDING

        # Then FAILED
        lock.deny_lock("Max iterations reached")
        assert lock.status == LockStatus.FAILED


class TestLockImmutability:
    """Test that locked data remains immutable."""

    def test_locked_cells_are_copies(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that locked cells are deep copies."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        # Modify original cells
        sample_cells[0].source = "# MODIFIED"

        # Locked cells should be unchanged
        assert lock.profile_cells[0].source == "# Data Profiling Report"

    def test_locked_handoff_is_immutable_tuple(self, sample_cells, sample_handoff, sample_validation_report):
        """Test that handoff column_profiles is immutable tuple."""
        lock = ProfileLock()

        lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        # Handoff column_profiles should be tuple (immutable)
        assert isinstance(lock.profile_handoff.column_profiles, tuple)


class TestLockEdgeCases:
    """Test edge cases for ProfileLock."""

    def test_grant_lock_with_empty_cells(self, sample_handoff, sample_validation_report):
        """Test granting lock with empty cells list."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=[],
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=1
        )

        assert result is True
        assert len(lock.profile_cells) == 0

    def test_grant_lock_with_zero_quality(self, sample_cells, sample_handoff, sample_validation_report):
        """Test granting lock with zero quality score."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.0,
            report=sample_validation_report,
            iteration=1
        )

        assert result is False
        assert lock.status == LockStatus.PENDING

    def test_grant_lock_with_perfect_quality(self, sample_cells, sample_handoff, sample_validation_report):
        """Test granting lock with perfect quality score."""
        lock = ProfileLock()

        result = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=1.0,
            report=sample_validation_report,
            iteration=1
        )

        assert result is True
        assert lock.status == LockStatus.LOCKED
        assert lock.phase1_quality_score == 1.0

    def test_multiple_grant_attempts(self, sample_cells, sample_handoff, sample_validation_report):
        """Test multiple grant attempts (simulating iterations)."""
        lock = ProfileLock()

        # First attempt - below threshold
        result1 = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.50,
            report=sample_validation_report,
            iteration=1
        )
        assert result1 is False
        assert lock.status == LockStatus.PENDING

        # Second attempt - still below
        result2 = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.60,
            report=sample_validation_report,
            iteration=2
        )
        assert result2 is False

        # Third attempt - meets threshold
        result3 = lock.grant_lock(
            cells=sample_cells,
            handoff=sample_handoff,
            quality_score=0.85,
            report=sample_validation_report,
            iteration=3
        )
        assert result3 is True
        assert lock.status == LockStatus.LOCKED
        assert lock.iterations_to_lock == 3
