"""Compute a stable content hash for a CSV file.

Used by the previous-job lookup so that repeating a job with the same
(user, mode, csv_hash) tuple can surface KPI deltas vs. the prior run.

Hashing is performed over the raw file bytes in 64KiB chunks so that the
helper is safe for large files (no full read into memory).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


_CHUNK = 64 * 1024


def hash_csv_file(csv_path: str | Path) -> Optional[str]:
    """Return the sha256 hex digest of the CSV file at ``csv_path``.

    Returns ``None`` if the path is empty, missing, or unreadable — callers
    should treat absence as "no hash available" rather than an error, since
    the hash is only used for opportunistic previous-job matching.
    """
    if not csv_path:
        return None
    try:
        p = Path(csv_path)
        if not p.is_file():
            return None
        h = hashlib.sha256()
        with p.open("rb") as f:
            while True:
                chunk = f.read(_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None
