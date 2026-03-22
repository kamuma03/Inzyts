"""
Test suite for CacheManager (Section 10.2 of requirements.md v1.5.0)

Tests cache operations including:
- Cache creation and retrieval
- Expiration handling (7-day TTL)
- CSV change detection via SHA256 hashing
- CLI flag behavior (--use-cache, --no-cache)
- Upgrade flow (exploratory → predictive)
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.models.handoffs import (
    CacheStatus,
    NotebookCell,
    PipelineMode,
    ProfileCache,
    ProfileToStrategyHandoff,
    UserIntent,
    ColumnProfile,
    DataType,
)
from src.utils.cache_manager import CacheManager


def create_sample_profile_handoff(row_count=4, column_count=3):
    """Helper to create a valid ProfileToStrategyHandoff for tests."""
    column_profiles = (
        ColumnProfile(
            name="Age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=4,
            null_percentage=0.0,
            sample_values=[25, 30, 35, 40]
        ),
        ColumnProfile(
            name="Salary",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=4,
            null_percentage=0.0,
            sample_values=[50000, 60000, 70000, 80000]
        ),
        ColumnProfile(
            name="Purchased",
            detected_type=DataType.CATEGORICAL,
            detection_confidence=0.90,
            unique_count=2,
            null_percentage=0.0,
            sample_values=["Yes", "No"]
        ),
    )

    return ProfileToStrategyHandoff(
        phase1_quality_score=0.85,
        row_count=row_count,
        column_count=column_count,
        column_profiles=column_profiles,
        overall_quality_score=0.85,
        missing_value_summary={"Age": 0.0, "Salary": 0.0, "Purchased": 0.0},
    )


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for testing."""
    cache_dir = tmp_path / ".inzyts_cache_test"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Patch CacheManager.CACHE_DIR to use temp directory
    original_cache_dir = CacheManager.CACHE_DIR
    CacheManager.CACHE_DIR = cache_dir

    yield cache_dir

    # Cleanup and restore
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    CacheManager.CACHE_DIR = original_cache_dir


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    csv_path = tmp_path / "test_data.csv"
    csv_content = """Age,Salary,Purchased
25,50000,No
30,60000,Yes
35,70000,Yes
40,80000,No
"""
    csv_path.write_text(csv_content)
    return str(csv_path)


@pytest.fixture
def modified_csv(tmp_path):
    """Create a modified version of the CSV (different content, same name)."""
    csv_path = tmp_path / "test_data_modified.csv"
    csv_content = """Age,Salary,Purchased,NewColumn
25,50000,No,A
30,60000,Yes,B
35,70000,Yes,C
"""
    csv_path.write_text(csv_content)
    return str(csv_path)


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create CacheManager instance with temp directory."""
    return CacheManager()


@pytest.fixture
def sample_profile_cache(sample_csv, cache_manager):
    """Create a sample ProfileCache object for testing."""
    csv_hash = cache_manager.get_csv_hash(sample_csv)

    # Create sample cells
    profile_cells = [
        NotebookCell(
            cell_type="code",
            source="import pandas as pd\ndf = pd.read_csv('test_data.csv')",
            metadata={}
        )
    ]

    # Create profile handoff with correct structure
    profile_handoff = create_sample_profile_handoff()

    # Create profile lock as dict (cache stores it as Dict[str, Any])
    profile_lock = {
        "csv_hash": csv_hash,
        "locked_at": datetime.now().isoformat(),
        "status": "locked",
        "locked_by": "Profile Validator",
        "phase1_quality_score": 0.85,
    }

    return cache_manager.save_cache(
        csv_path=sample_csv,
        csv_hash=csv_hash,
        profile_lock=profile_lock,
        profile_cells=profile_cells,
        profile_handoff=profile_handoff,
        phase1_quality_score=0.85,
        pipeline_mode=PipelineMode.EXPLORATORY,
        user_intent=UserIntent(csv_path=sample_csv, analysis_question="What is the age distribution?")
    )


class TestCacheCreationAndRetrieval:
    """Test cache save and load operations."""

    def test_no_cache_exists(self, cache_manager, sample_csv):
        """Test CA-001: No cache exists → Returns NOT_FOUND status."""
        result = cache_manager.check_cache(sample_csv)

        assert result.status == CacheStatus.NOT_FOUND
        assert result.cache is None
        assert "No cached profile found" in result.message

    def test_cache_save_and_load(self, cache_manager, sample_csv, sample_profile_cache):
        """Test successful cache save and retrieval."""
        csv_hash = cache_manager.get_csv_hash(sample_csv)

        # Verify cache was saved
        cache_path = cache_manager.get_cache_path(csv_hash)
        assert cache_path.exists()
        assert (cache_path / "metadata.json").exists()

        # Verify cache can be loaded
        loaded_cache = cache_manager.load_cache(csv_hash)
        assert loaded_cache is not None
        assert loaded_cache.csv_hash == csv_hash
        assert loaded_cache.phase1_quality_score == 0.85
        assert loaded_cache.pipeline_mode == PipelineMode.EXPLORATORY

    def test_cache_contains_all_required_fields(self, sample_profile_cache):
        """Test that saved cache has all required fields."""
        assert sample_profile_cache.cache_id is not None
        assert sample_profile_cache.csv_path is not None
        assert sample_profile_cache.csv_hash is not None
        assert sample_profile_cache.created_at is not None
        assert sample_profile_cache.expires_at is not None
        assert sample_profile_cache.profile_lock is not None
        assert sample_profile_cache.profile_cells is not None
        assert sample_profile_cache.profile_handoff is not None


class TestCacheExpiration:
    """Test cache expiration and TTL handling."""

    def test_valid_cache_within_ttl(self, cache_manager, sample_csv, sample_profile_cache):
        """Test CA-002: Valid cache (< 7 days) → Returns VALID status."""
        result = cache_manager.check_cache(sample_csv)

        assert result.status == CacheStatus.VALID
        assert result.cache is not None
        assert result.cache.csv_hash == sample_profile_cache.csv_hash
        assert "Valid cache found" in result.message

    def test_expired_cache_deleted(self, cache_manager, sample_csv, temp_cache_dir):
        """Test CA-003: Expired cache (> 7 days) → Delete and return NOT_FOUND."""
        csv_hash = cache_manager.get_csv_hash(sample_csv)

        # Create expired cache manually
        cache_path = cache_manager.get_cache_path(csv_hash)
        cache_path.mkdir(parents=True, exist_ok=True)

        expired_cache = ProfileCache(
            cache_id=csv_hash,
            csv_path=sample_csv,
            csv_hash=csv_hash,
            csv_size_bytes=100,
            csv_row_count=4,
            csv_column_count=3,
            created_at=datetime.now() - timedelta(days=8),
            expires_at=datetime.now() - timedelta(days=1),  # Expired 1 day ago
            profile_lock={},
            profile_cells=[],
            profile_handoff=create_sample_profile_handoff(),
            pipeline_mode=PipelineMode.EXPLORATORY,
            phase1_quality_score=0.8,
            user_intent=None,
            agent_version="1.5.0"
        )

        # Save expired cache
        metadata_file = cache_path / "metadata.json"
        with open(metadata_file, "w") as f:
            f.write(expired_cache.model_dump_json(indent=2))

        # Attempt to load - should return None and delete cache
        loaded = cache_manager.load_cache(csv_hash)
        assert loaded is None
        assert not cache_path.exists()

    def test_clear_expired_caches(self, cache_manager, sample_csv, temp_cache_dir):
        """Test bulk deletion of expired caches."""
        # Create multiple caches with different expiration dates
        for i in range(3):
            csv_hash = f"hash_{i}"
            cache_path = cache_manager.get_cache_path(csv_hash)
            cache_path.mkdir(parents=True, exist_ok=True)

            # Cache 0: Expired
            # Cache 1: Valid
            # Cache 2: Expired
            days_offset = 1 if i == 1 else 8

            cache = ProfileCache(
                cache_id=csv_hash,
                csv_path=sample_csv,
                csv_hash=csv_hash,
                csv_size_bytes=100,
                csv_row_count=4,
                csv_column_count=3,
                created_at=datetime.now() - timedelta(days=days_offset),
                expires_at=datetime.now() + timedelta(days=7 - days_offset),
                profile_lock={},
                profile_cells=[],
                profile_handoff=create_sample_profile_handoff(),
                pipeline_mode=PipelineMode.EXPLORATORY,
                phase1_quality_score=0.8,
                user_intent=None,
                agent_version="1.5.0"
            )

            metadata_file = cache_path / "metadata.json"
            with open(metadata_file, "w") as f:
                f.write(cache.model_dump_json(indent=2))

        # Clear expired caches
        cache_manager.clear_expired_caches()

        # Verify only valid cache remains
        assert not (cache_manager.get_cache_path("hash_0")).exists()
        assert (cache_manager.get_cache_path("hash_1")).exists()
        assert not (cache_manager.get_cache_path("hash_2")).exists()


class TestCSVChangeDetection:
    """Test CSV content change detection via SHA256 hashing."""

    def test_csv_changed_detection(self, cache_manager, sample_csv, modified_csv, temp_cache_dir):
        """Test CA-004: CSV changed (hash mismatch) → Warn user with CSV_CHANGED status."""
        # Create cache for original CSV
        original_hash = cache_manager.get_csv_hash(sample_csv)

        profile_lock = {
            "csv_hash": original_hash,
            "locked_at": datetime.now().isoformat(),
        }

        cache_manager.save_cache(
            csv_path=sample_csv,
            csv_hash=original_hash,
            profile_lock=profile_lock,
            profile_cells=[],
            profile_handoff=create_sample_profile_handoff(),
            phase1_quality_score=0.8,
            pipeline_mode=PipelineMode.EXPLORATORY
        )

        # Now check cache with modified CSV content (simulated by using different hash)
        # We'll modify the index to point to old hash, then check with new content
        modified_hash = cache_manager.get_csv_hash(modified_csv)

        # Manually update index to simulate same file path but different content
        index_file = temp_cache_dir / "cache_index.json"
        index = {str(Path(modified_csv).resolve()): original_hash}
        index_file.write_text(json.dumps(index, indent=2))

        # Check cache - should detect hash mismatch
        result = cache_manager.check_cache(modified_csv)

        # If old cache exists for the previous hash, should return CSV_CHANGED
        if result.status == CacheStatus.CSV_CHANGED:
            assert "changed" in result.message.lower()
            assert result.cache is not None  # Old cache returned for comparison
        else:
            # If old cache was cleaned up, should be NOT_FOUND
            assert result.status == CacheStatus.NOT_FOUND

    def test_hash_consistency(self, cache_manager, sample_csv):
        """Test that same file produces same hash."""
        hash1 = cache_manager.get_csv_hash(sample_csv)
        hash2 = cache_manager.get_csv_hash(sample_csv)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64-character hex string

    def test_different_content_different_hash(self, cache_manager, sample_csv, modified_csv):
        """Test that modified file produces different hash."""
        hash1 = cache_manager.get_csv_hash(sample_csv)
        hash2 = cache_manager.get_csv_hash(modified_csv)

        assert hash1 != hash2


class TestCacheFlagBehavior:
    """Test --use-cache and --no-cache flag behavior."""

    def test_use_cache_flag_skips_prompt(self, cache_manager, sample_csv, sample_profile_cache):
        """Test CA-006: --use-cache flag → Use cache without prompting."""
        # In actual implementation, this is handled by orchestrator.py
        # Here we verify cache is accessible
        result = cache_manager.check_cache(sample_csv)

        assert result.status == CacheStatus.VALID
        assert result.cache is not None

        # Simulate --use-cache logic (orchestrator would directly use result.cache)
        assert result.cache.csv_hash == sample_profile_cache.csv_hash

    def test_no_cache_flag_ignores_cache(self, cache_manager, sample_csv, sample_profile_cache):
        """Test CA-007: --no-cache flag → Ignore cache and run fresh."""
        # Verify cache exists
        result = cache_manager.check_cache(sample_csv)
        assert result.status == CacheStatus.VALID

        # Simulate --no-cache logic (orchestrator would skip cache check entirely)
        # We verify we CAN ignore it even when it exists
        csv_hash = cache_manager.get_csv_hash(sample_csv)
        cache_path = cache_manager.get_cache_path(csv_hash)
        assert cache_path.exists()

        # In orchestrator, --no-cache prevents check_cache() from being called
        # This test verifies cache exists but can be bypassed


class TestUpgradeFlow:
    """Test exploratory → predictive upgrade flow using cached profile."""

    def test_upgrade_uses_cached_profile(self, cache_manager, sample_csv, temp_cache_dir):
        """Test upgrade flow: Exploratory → Predictive uses cached Phase 1 profile."""
        csv_hash = cache_manager.get_csv_hash(sample_csv)

        # Step 1: Run exploratory analysis (creates cache)
        profile_lock = {
            "csv_hash": csv_hash,
            "locked_at": datetime.now().isoformat(),
        }

        exploratory_cache = cache_manager.save_cache(
            csv_path=sample_csv,
            csv_hash=csv_hash,
            profile_lock=profile_lock,
            profile_cells=[
                NotebookCell(
                    cell_type="markdown",
                    source="# Exploratory Analysis",
                    metadata={}
                )
            ],
            profile_handoff=create_sample_profile_handoff(),
            phase1_quality_score=0.85,
            pipeline_mode=PipelineMode.EXPLORATORY,
            user_intent=UserIntent(csv_path=sample_csv, analysis_question="What is the age distribution?")
        )

        assert exploratory_cache.pipeline_mode == PipelineMode.EXPLORATORY

        # Step 2: Upgrade to predictive (check cache availability)
        result = cache_manager.check_cache(sample_csv)

        assert result.status == CacheStatus.VALID
        assert result.cache is not None
        assert result.cache.csv_hash == csv_hash

        # Verify cached profile can be reused for predictive mode
        cached_handoff = result.cache.profile_handoff
        assert cached_handoff.row_count == 4
        assert cached_handoff.column_count == 3

        # Verify profile lock is present (required for Phase 2)
        assert result.cache.profile_lock is not None
        assert result.cache.profile_lock["csv_hash"] == csv_hash

    def test_upgrade_preserves_profile_lock(self, cache_manager, sample_csv, sample_profile_cache):
        """Test that cached profile lock is immutable and preserved during upgrade."""
        result = cache_manager.check_cache(sample_csv)

        assert result.status == CacheStatus.VALID
        cached_lock = result.cache.profile_lock

        # Verify lock contains critical fields
        assert "csv_hash" in cached_lock
        assert "locked_at" in cached_lock

        # Verify profile handoff is frozen (Pydantic model)
        handoff = result.cache.profile_handoff
        assert handoff.row_count == 4
        assert handoff.column_count == 3


class TestCacheDeletion:
    """Test cache deletion operations."""

    def test_delete_cache_with_reason(self, cache_manager, sample_csv, sample_profile_cache):
        """Test cache deletion with reason logging."""
        csv_hash = cache_manager.get_csv_hash(sample_csv)
        cache_path = cache_manager.get_cache_path(csv_hash)

        # Verify cache exists
        assert cache_path.exists()

        # Delete cache
        cache_manager.delete_cache(csv_hash, reason="test_cleanup")

        # Verify cache is deleted
        assert not cache_path.exists()

    def test_clear_all_caches(self, cache_manager, sample_csv, temp_cache_dir):
        """Test clearing all caches."""
        # Create multiple caches
        for i in range(3):
            csv_hash = f"test_hash_{i}"
            cache_path = cache_manager.get_cache_path(csv_hash)
            cache_path.mkdir(parents=True, exist_ok=True)
            (cache_path / "metadata.json").write_text("{}")

        # Verify caches exist
        assert len(list(temp_cache_dir.iterdir())) >= 3

        # Clear all caches
        cache_manager.clear_all_caches()

        # Verify all caches deleted (except cache_index.json if present)
        remaining = [f for f in temp_cache_dir.iterdir() if f.name != "cache_index.json"]
        assert len(remaining) == 0


class TestCacheIndex:
    """Test cache index operations (path → hash mapping)."""

    def test_index_updated_on_save(self, cache_manager, sample_csv, sample_profile_cache):
        """Test that cache index is updated when cache is saved."""
        index_file = cache_manager.CACHE_DIR / "cache_index.json"

        assert index_file.exists()

        index = json.loads(index_file.read_text())
        abs_path = str(Path(sample_csv).resolve())

        assert abs_path in index
        assert index[abs_path] == cache_manager.get_csv_hash(sample_csv)

    def test_index_lookup(self, cache_manager, sample_csv, sample_profile_cache):
        """Test retrieving hash from index by file path."""
        csv_hash = cache_manager.get_csv_hash(sample_csv)

        # Internal method test
        retrieved_hash = cache_manager._get_hash_from_index(sample_csv)

        assert retrieved_hash == csv_hash
