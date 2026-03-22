"""
Shared path validation utilities.

Consolidates the path traversal defence logic used across routes into a
single reusable module so the security-critical ``is_relative_to()`` check
is never re-implemented ad-hoc.
"""

from pathlib import Path
from typing import List, Optional, Union

from fastapi import HTTPException

from src.utils.logger import get_logger

logger = get_logger()


def validate_path_within(
    path: Union[str, Path],
    allowed_dirs: List[Path],
    *,
    resolve_relative_to: Optional[Path] = None,
    reject_symlinks: bool = False,
    must_exist: bool = False,
    error_label: str = "file",
) -> Path:
    """Validate that *path* resolves to a location inside one of *allowed_dirs*.

    Args:
        path: The user-supplied path (absolute or relative).
        allowed_dirs: Directories the resolved path must fall within.
        resolve_relative_to: If *path* is relative, resolve it against this
            directory instead of CWD.  When ``None``, relative paths are
            resolved against CWD (which is rarely desirable in a server).
        reject_symlinks: If ``True``, reject paths that are symlinks.
        must_exist: If ``True``, raise 404 when the resolved path does not
            exist on disk.
        error_label: Human-readable noun for error messages (e.g. "notebook",
            "log file").

    Returns:
        The resolved absolute ``Path``.

    Raises:
        HTTPException: 403 on traversal / symlink violations, 404 on missing
            files.
    """
    p = Path(path)

    if not p.is_absolute() and resolve_relative_to is not None:
        p = (resolve_relative_to / p)

    resolved = p.resolve()

    if reject_symlinks and (Path(path).is_symlink() or resolved.is_symlink()):
        raise HTTPException(status_code=403, detail="Symbolic links are not permitted")

    if not any(resolved.is_relative_to(d) for d in allowed_dirs):
        logger.warning(f"Path traversal blocked for {error_label}: {resolved}")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: invalid {error_label} path",
        )

    if must_exist and not resolved.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{error_label.capitalize()} not found",
        )

    return resolved


def ensure_dir(path: Union[str, Path]) -> Path:
    """Create *path* (and parents) if it does not exist, return the ``Path``.

    Replaces the ``Path(...).mkdir(parents=True, exist_ok=True)`` one-liner
    scattered across the codebase with a single call that also returns the
    path for chaining.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
