"""
Cache Manager for Multi-Agent Data Analysis System.

Handles storage and retrieval of Phase 1 profiles to support:
1. Resume/Upgrade capabilities (Exploratory -> Predictive).
2. Avoiding redundant computation.
"""

import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.models.handoffs import (
    ProfileCache,
    CacheStatus,
    PipelineMode,
    ProfileToStrategyHandoff,
    UserIntent,
    NotebookCell,
)
from src.utils.logger import get_logger
from src.utils.path_validator import ensure_dir

# Note: We avoid importing ProfileLock from models.state at module level to prevent circular imports
# if state imports this module. But typically utils are leaves.
# We will use "Any" for the lock arguments.

# Initialize logger
logger = get_logger()


class CacheCheckResult(BaseModel):
    status: CacheStatus
    cache: Optional[ProfileCache]
    message: str


class CacheManager:
    """Manages profile cache for upgrade path and efficiency."""

    # Use project-mounted .cache directory for Docker accessibility
    # This allows clearing cache from host: rm -rf .cache/inzyts
    CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "inzyts"
    CACHE_TTL_DAYS = 7
    VERSION = "1.5.0"

    def __init__(self):
        ensure_dir(self.CACHE_DIR)
        self._hash_cache: Dict[
            str, str
        ] = {}  # Cache hash results to avoid recomputation

    def get_csv_hash(self, csv_path: str) -> str:
        """Calculate SHA256 hash of CSV file content. Results are cached."""
        # Check cache first
        if csv_path in self._hash_cache:
            return self._hash_cache[csv_path]

        sha256_hash = hashlib.sha256()
        try:
            with open(csv_path, "rb") as f:
                # Read in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            result = sha256_hash.hexdigest()
            self._hash_cache[csv_path] = result  # Store in cache
            return result
        except FileNotFoundError:
            return ""

    def compute_combined_hash(self, file_paths: List[str]) -> str:
        """
        Compute a single deterministic hash for multiple files.
        hashes = [hash(f) for f in files] -> sort -> combine -> hash
        """
        hashes = []
        for p in file_paths:
            h = self.get_csv_hash(p)
            if h:
                hashes.append(h)

        if not hashes:
            return ""

        # Sort to ensure order independence (e.g. A,B vs B,A)
        # Note: If order matters for joins, we might NOT want to sort.
        # But JoinStrategy usually works on content.
        # If user specifies explicit joins, order might matter?
        # For now, sorting is safer for "Set of files".
        hashes.sort()
        combined = "".join(hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_cache_path(self, csv_hash: str) -> Path:
        """Get cache directory for a given CSV hash."""
        return self.CACHE_DIR / csv_hash

    def load_cache(self, csv_hash: str) -> Optional[ProfileCache]:
        """Load cache if exists and not expired."""
        cache_path = self.get_cache_path(csv_hash)
        metadata_file = cache_path / "metadata.json"

        if not metadata_file.exists():
            return None

        try:
            # Pydantic v2 style preferred, fallback if v1
            if hasattr(ProfileCache, "model_validate_json"):
                cache = ProfileCache.model_validate_json(metadata_file.read_text())
            else:
                cache = ProfileCache.parse_file(metadata_file)

            if cache.is_expired():
                self.delete_cache(csv_hash)
                return None

            return cache
        except Exception as e:
            # Corrupt cache
            logger.warning(f"Failed to load cache: {e}")
            self.delete_cache(csv_hash)
            return None

    def save_cache(
        self,
        csv_path: str,
        csv_hash: str,
        profile_lock: Any,  # ProfileLock object
        profile_cells: List[NotebookCell],
        profile_handoff: ProfileToStrategyHandoff,
        phase1_quality_score: float,
        pipeline_mode: PipelineMode = PipelineMode.EXPLORATORY,
        user_intent: Optional[UserIntent] = None,
    ) -> ProfileCache:
        """
        Save validated Phase 1 profile outputs to the persistent disk cache.

        This serialized the profile metadata, handoffs, and profile lock into a
        JSON structure stored in `~/.multi_agent_cache/<sha256>`.

        Args:
            csv_path: Origin path of the CSV (for indexing).
            csv_hash: SHA256 hash of the CSV content (used as cache ID).
            profile_lock: The lock object ensuring data immutability.
            profile_cells: Generated notebook cells describing the data.
            profile_handoff: Structured data summary for Phase 2/Exploration.
            phase1_quality_score: Quality score of the profile.
            pipeline_mode: Mode the profile was generated in.
            user_intent: Original user intent (optional).

        Returns:
            The created ProfileCache object.
        """
        from datetime import timezone

        cache_path = self.get_cache_path(csv_hash)
        try:
            ensure_dir(cache_path)
        except Exception as e:
            logger.error(f"Failed to create cache directory: {e}")
            # Continue anyway, let the file write fail downstream

        # Get CSV metadata
        try:
            csv_stat = Path(csv_path).stat()
            csv_size = csv_stat.st_size
        except (OSError, FileNotFoundError):
            csv_size = 0

        # Serialize ProfileLock to dict (it's a Pydantic model)
        # We handle this manually to ensure it's JSON serializable
        if isinstance(profile_lock, dict):
            lock_dict = profile_lock
        else:
            lock_dict = profile_lock.model_dump()

        # Serialize cells
        # cells_data = [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in profile_cells]

        cache = ProfileCache(
            cache_id=csv_hash,
            csv_path=csv_path,
            csv_hash=csv_hash,
            csv_size_bytes=csv_size,
            csv_row_count=profile_handoff.row_count,
            csv_column_count=profile_handoff.column_count,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.CACHE_TTL_DAYS),
            profile_lock=lock_dict,
            profile_cells=profile_cells,
            profile_handoff=profile_handoff,
            pipeline_mode=pipeline_mode,
            phase1_quality_score=phase1_quality_score,
            user_intent=user_intent,
            agent_version=self.VERSION,
        )

        # Save metadata.json atomically (write to temp then rename)
        try:
            metadata_path = cache_path / "metadata.json"
            temp_path = cache_path / "metadata.json.tmp"

            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(
                    cache.model_dump_json(indent=2)
                    if hasattr(cache, "model_dump_json")
                    else cache.json(indent=2)
                )

            # Atomic rename
            temp_path.replace(metadata_path)

            # Update index (optional, but good for listing)
            self._update_index(csv_path, csv_hash)

            # Log cache save
            logger.cache_saved(csv_hash, phase1_quality_score)
        except Exception as e:
            logger.error(f"Cache save failed: {e}")
            if "temp_path" in locals() and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        return cache

    def delete_cache(self, csv_hash: str, reason: str = "manual"):
        """Delete cache for a given CSV hash."""
        cache_path = self.get_cache_path(csv_hash)
        if cache_path.exists():
            shutil.rmtree(cache_path)
            logger.cache_deleted(csv_hash, reason)

    def clear_expired_caches(self):
        """Delete all expired caches."""
        from datetime import timezone

        if not self.CACHE_DIR.exists():
            return

        for cache_dir in self.CACHE_DIR.iterdir():
            if cache_dir.is_dir():
                metadata_file = cache_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        # Lightweight load check
                        data = json.loads(metadata_file.read_text())
                        expires_at = datetime.fromisoformat(data["expires_at"])
                        # Handle timezone awareness (cache might be unaware if old)
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)

                        if datetime.now(timezone.utc) > expires_at:
                            shutil.rmtree(cache_dir)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        # Corrupt cache found, log usage and maybe clean?
                        logger.warning(
                            f"Found corrupt cache at {cache_dir}, ignoring: {e}"
                        )
                        # Optional: shutil.rmtree(cache_dir) if strict
                        pass

    def clear_all_caches(self):
        """Delete ALL caches."""
        if self.CACHE_DIR.exists():
            shutil.rmtree(self.CACHE_DIR)
            self.CACHE_DIR.mkdir()

    def check_cache(self, csv_path: str) -> CacheCheckResult:
        """
        Check status of profile cache for a given CSV file.

        This method determines if a valid cache exists, if the file has changed
        since the last cache, or if no cache exists. It uses an index file to track
        path->hash mappings to detect content changes.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            CacheCheckResult containing status, cache object (if valid/changed), and message.
        """
        csv_hash = self.get_csv_hash(csv_path)
        if not csv_hash:
            return CacheCheckResult(
                status=CacheStatus.NOT_FOUND,
                cache=None,
                message="File not found or unreadable",
            )

        # Check index for previous hash FIRST to detect modifications
        last_hash = self._get_hash_from_index(csv_path)
        if last_hash and last_hash != csv_hash:
            # We have a record of this file, but hash is different.
            # Check if THAT old cache exists
            old_cache = self.load_cache(last_hash)
            if old_cache:
                return CacheCheckResult(
                    status=CacheStatus.CSV_CHANGED,
                    cache=old_cache,
                    message=f"CSV has changed since profile was cached on {old_cache.created_at}",
                )

        cache = self.load_cache(csv_hash)

        if cache is None:
            return CacheCheckResult(
                status=CacheStatus.NOT_FOUND,
                cache=None,
                message="No cached profile found",
            )

        return CacheCheckResult(
            status=CacheStatus.VALID,
            cache=cache,
            message=f"Valid cache found ({cache.days_until_expiry()} days until expiry)",
        )

    def check_multi_file_cache(self, file_paths: List[str]) -> CacheCheckResult:
        """Check cache for a set of files (combined hash)."""
        combined_hash = self.compute_combined_hash(file_paths)
        if not combined_hash:
            return CacheCheckResult(
                status=CacheStatus.NOT_FOUND,
                cache=None,
                message="Could not compute hash",
            )

        cache = self.load_cache(combined_hash)
        if not cache:
            return CacheCheckResult(
                status=CacheStatus.NOT_FOUND,
                cache=None,
                message="No cache for file set",
            )

        # For multi-file, we assume if input hash matches, it's valid.
        return CacheCheckResult(
            status=CacheStatus.VALID,
            cache=cache,
            message=f"Valid multi-file profile found ({cache.days_until_expiry()} days left)",
        )

    def _update_index(self, csv_path: str, csv_hash: str):
        """Update index file mapping path -> hash."""
        index_file = self.CACHE_DIR / "cache_index.json"

        try:
            # Atomic update with lock would be better but for now atomic write of file
            if index_file.exists():
                try:
                    index = json.loads(index_file.read_text())
                except json.JSONDecodeError:
                    index = {}  # Recover from corrupt index
            else:
                index = {}

            # Use absolute path as key
            abs_path = str(Path(csv_path).resolve())
            index[abs_path] = csv_hash

            user_data = json.dumps(index, indent=2)

            # Atomic write
            temp_file = self.CACHE_DIR / "cache_index.json.tmp"
            temp_file.write_text(user_data)
            temp_file.replace(index_file)

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to update cache index: {e}")
            if "temp_file" in locals() and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _get_hash_from_index(self, csv_path: str) -> Optional[str]:
        """Get last known hash for this path."""
        index_file = self.CACHE_DIR / "cache_index.json"
        if not index_file.exists():
            return None
        try:
            index = json.loads(index_file.read_text())
            abs_path = str(Path(csv_path).resolve())
            return index.get(abs_path)
        except (OSError, json.JSONDecodeError):
            logger.warning(f"Cache index corrupt or unreadable at {index_file}")
            return None

    def save_artifact(self, csv_hash: str, artifact_name: str, data: Dict[str, Any]):
        """Save a generic JSON artifact to the cache."""
        cache_path = self.get_cache_path(csv_hash)
        artifact_path = cache_path / f"{artifact_name}.json"
        
        try:
            ensure_dir(cache_path)
            ensure_dir(artifact_path.parent)
        except Exception as e:
            logger.error(f"Failed to create cache directories for '{artifact_name}': {e}")
            return

        temp_path = cache_path / f"{artifact_name}.json.tmp"

        try:
            temp_path.write_text(json.dumps(data, indent=2))
            temp_path.replace(artifact_path)
        except Exception as e:
            logger.error(f"Failed to save artifact '{artifact_name}': {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def load_artifact(
        self, csv_hash: str, artifact_name: str
    ) -> Optional[Dict[str, Any]]:
        """Load a generic JSON artifact from the cache."""
        cache_path = self.get_cache_path(csv_hash)
        artifact_path = cache_path / f"{artifact_name}.json"

        if artifact_path.exists():
            try:
                return json.loads(artifact_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load artifact '{artifact_name}': {e}")
                return None
        return None

    def save_extension(self, csv_hash: str, extension_name: str, data: Any):
        """Save extension data to cache."""
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump()
        else:
            data_dict = data

        self.save_artifact(csv_hash, f"extensions/{extension_name}", data_dict)

    def load_extension(
        self, csv_hash: str, extension_name: str, model_class: Any
    ) -> Optional[Any]:
        """Load extension data from cache."""
        data = self.load_artifact(csv_hash, f"extensions/{extension_name}")
        if data and model_class:
            try:
                if hasattr(model_class, "model_validate"):
                    return model_class.model_validate(data)
                else:
                    return model_class.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse extension '{extension_name}': {e}")
                return None
        return data
