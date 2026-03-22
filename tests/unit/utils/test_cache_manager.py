import pytest
import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from src.utils.cache_manager import CacheManager, CacheCheckResult
from src.models.handoffs import CacheStatus, ProfileCache, ProfileToStrategyHandoff, PipelineMode, NotebookCell

@pytest.fixture
def cache_dir(tmp_path):
    """Fixture to provide a temporary cache directory."""
    # We patch CacheManager.CACHE_DIR to use tmp_path
    original_dir = CacheManager.CACHE_DIR
    CacheManager.CACHE_DIR = tmp_path
    yield tmp_path
    CacheManager.CACHE_DIR = original_dir

@pytest.fixture
def csv_file(tmp_path):
    """Create a temporary CSV file for testing."""
    file_path = tmp_path / "test.csv"
    file_path.write_text("a,b,c\n1,2,3")
    return str(file_path)

@pytest.fixture
def cache_manager(cache_dir):
    """Provide a CacheManager instance with mocked directory."""
    return CacheManager()

@pytest.fixture
def mock_handoff():
    """Provide a minimal mock handoff object."""
    return ProfileToStrategyHandoff(
        row_count=100,
        column_count=3,
        columns=[],
        data_types={},
        memory_usage=1024,
        numeric_columns=[],
        categorical_columns=[],
        datetime_columns=[],
        missing_values={},
        high_cardinality=[],
        quality_issues=[],
        suggested_operations=[],
        profile_time=1.0,
        phase1_quality_score=9.5,
        column_profiles=(),
        overall_quality_score=9.5,
        missing_value_summary={}
    )

def test_cache_dir_creation(cache_manager, cache_dir):
    """Test that the cache manager creates its directory."""
    assert cache_dir.exists()

def test_get_csv_hash(cache_manager, csv_file):
    """Test CSV hashing and caching."""
    hash1 = cache_manager.get_csv_hash(csv_file)
    assert hash1 != ""
    
    # Second call should hit the cache dict
    hash2 = cache_manager.get_csv_hash(csv_file)
    assert hash1 == hash2

def test_get_csv_hash_missing_file(cache_manager):
    """Test hashing a file that does not exist."""
    assert cache_manager.get_csv_hash("does_not_exist.csv") == ""

def test_compute_combined_hash(cache_manager, csv_file, tmp_path):
    """Test hashing multiple files."""
    file2 = tmp_path / "test2.csv"
    file2.write_text("d,e,f\n4,5,6")
    file2_path = str(file2)
    
    combined = cache_manager.compute_combined_hash([csv_file, file2_path])
    assert combined != ""
    assert isinstance(combined, str)

def test_save_and_load_cache(cache_manager, csv_file, mock_handoff):
    """Test saving and then loading a profile cache."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    profile_lock = {"locked": True} # Mock dictionary representation of lock
    cells = [NotebookCell(cell_type="code", source="print('Test')")]
    
    saved_cache = cache_manager.save_cache(
        csv_path=csv_file,
        csv_hash=csv_hash,
        profile_lock=profile_lock,
        profile_cells=cells,
        profile_handoff=mock_handoff,
        phase1_quality_score=9.5,
        pipeline_mode=PipelineMode.EXPLORATORY
    )
    
    assert saved_cache is not None
    assert saved_cache.cache_id == csv_hash
    assert saved_cache.csv_hash == csv_hash
    assert saved_cache.phase1_quality_score == 9.5
    
    # Now try to load it
    loaded_cache = cache_manager.load_cache(csv_hash)
    assert loaded_cache is not None
    assert loaded_cache.csv_hash == csv_hash
    assert loaded_cache.phase1_quality_score == 9.5
    assert len(loaded_cache.profile_cells) == 1

def test_check_cache_not_found(cache_manager):
    """Test check_cache when no file or cache exists."""
    result = cache_manager.check_cache("missing.csv")
    assert result.status == CacheStatus.NOT_FOUND
    assert result.cache is None

def test_check_cache_valid(cache_manager, csv_file, mock_handoff):
    """Test check_cache when a valid cache exists."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    
    cache_manager.save_cache(
        csv_path=csv_file,
        csv_hash=csv_hash,
        profile_lock={},
        profile_cells=[],
        profile_handoff=mock_handoff,
        phase1_quality_score=8.0
    )
    
    result = cache_manager.check_cache(csv_file)
    assert result.status == CacheStatus.VALID
    assert result.cache is not None
    assert result.cache.csv_hash == csv_hash

def test_delete_cache(cache_manager, csv_file, mock_handoff):
    """Test cache deletion."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    
    # Save first
    cache_manager.save_cache(
        csv_path=csv_file,
        csv_hash=csv_hash,
        profile_lock={},
        profile_cells=[],
        profile_handoff=mock_handoff,
        phase1_quality_score=8.0
    )
    
    # Ensure it exists
    assert cache_manager.load_cache(csv_hash) is not None
    
    # Delete and verify
    cache_manager.delete_cache(csv_hash)
    assert cache_manager.load_cache(csv_hash) is None

def test_clear_all_caches(cache_manager, csv_file, mock_handoff):
    """Test clearing all cache directories."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    cache_manager.save_cache(
        csv_path=csv_file,
        csv_hash=csv_hash,
        profile_lock={},
        profile_cells=[],
        profile_handoff=mock_handoff,
        phase1_quality_score=8.0
    )
    
    cache_manager.clear_all_caches()
    assert cache_manager.load_cache(csv_hash) is None

def test_save_and_load_artifact(cache_manager, csv_file):
    """Test saving/loading generic artifacts."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    artifact_name = "test_artifact"
    data = {"key": "value", "list": [1, 2, 3]}
    
    cache_manager.save_artifact(csv_hash, artifact_name, data)
    
    loaded = cache_manager.load_artifact(csv_hash, artifact_name)
    assert loaded == data

def test_load_artifact_missing(cache_manager, csv_file):
    """Test loading missing artifact."""
    csv_hash = cache_manager.get_csv_hash(csv_file)
    loaded = cache_manager.load_artifact(csv_hash, "missing_artifact")
    assert loaded is None

def test_clear_expired_caches(cache_manager, csv_file, mock_handoff):
    csv_hash = cache_manager.get_csv_hash(csv_file)
    cache_manager.save_cache(
        csv_path=csv_file, csv_hash=csv_hash, profile_lock={},
        profile_cells=[], profile_handoff=mock_handoff, phase1_quality_score=8.0
    )
    
    cache_path = cache_manager.get_cache_path(csv_hash)
    metadata_file = cache_path / "metadata.json"
    data = json.loads(metadata_file.read_text())
    data["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    metadata_file.write_text(json.dumps(data))
    
    cache_manager.clear_expired_caches()
    assert not cache_path.exists()

def test_clear_expired_caches_corrupt_json(cache_manager, csv_file, mock_handoff):
    csv_hash = cache_manager.get_csv_hash(csv_file)
    cache_manager.save_cache(
        csv_path=csv_file, csv_hash=csv_hash, profile_lock={},
        profile_cells=[], profile_handoff=mock_handoff, phase1_quality_score=8.0
    )
    cache_path = cache_manager.get_cache_path(csv_hash)
    metadata_file = cache_path / "metadata.json"
    metadata_file.write_text("INVALID JSON")
    
    cache_manager.clear_expired_caches()
    assert cache_path.exists()

def test_check_cache_hash_mismatch(cache_manager, csv_file, mock_handoff):
    csv_hash = cache_manager.get_csv_hash(csv_file)
    cache_manager.save_cache(
        csv_path=csv_file, csv_hash=csv_hash, profile_lock={},
        profile_cells=[], profile_handoff=mock_handoff, phase1_quality_score=8.0
    )
    
    with open(csv_file, "a") as f:
        f.write("\nnew_data,yes,no")
    
    cache_manager._hash_cache.clear()
    
    result = cache_manager.check_cache(csv_file)
    assert result.status == CacheStatus.CSV_CHANGED

def test_check_cache_expired(cache_manager, csv_file, mock_handoff):
    csv_hash = cache_manager.get_csv_hash(csv_file)
    cache_manager.save_cache(
        csv_path=csv_file, csv_hash=csv_hash, profile_lock={},
        profile_cells=[], profile_handoff=mock_handoff, phase1_quality_score=8.0
    )
    
    cache_path = cache_manager.get_cache_path(csv_hash)
    metadata_file = cache_path / "metadata.json"
    data = json.loads(metadata_file.read_text())
    data["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    metadata_file.write_text(json.dumps(data))
    
    result = cache_manager.check_cache(csv_file)
    assert result.status == CacheStatus.NOT_FOUND

def test_save_cache_exception(cache_manager, csv_file, mock_handoff):
    csv_hash = cache_manager.get_csv_hash(csv_file)
    
    cache_manager.CACHE_DIR.chmod(0o555) 
    
    try:
        saved_cache = cache_manager.save_cache(
            csv_path=csv_file, csv_hash=csv_hash, profile_lock={},
            profile_cells=[], profile_handoff=mock_handoff, phase1_quality_score=8.0
        )
        assert saved_cache is not None 
    finally:
        cache_manager.CACHE_DIR.chmod(0o755)
