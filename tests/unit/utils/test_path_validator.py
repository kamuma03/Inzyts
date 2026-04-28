"""Targeted tests for ``src.utils.path_validator``.

These tests close coverage gaps that mutation testing surfaced — each
test was added to kill a specific surviving mutant from
``mutmut run --paths-to-mutate=src/utils/path_validator.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from src.utils.path_validator import ensure_dir, validate_path_within


# ---------------------------------------------------------------------------
# Mutant #2: reject_symlinks default flipped from False to True
# ---------------------------------------------------------------------------


def test_symlinks_are_allowed_by_default(tmp_path):
    """``reject_symlinks`` defaults to False — symlinks pointing INSIDE
    the allowed dir must be accepted unless the caller opts into rejection.

    Kills mutmut mutant #2 (default flipped to True).
    """
    target = tmp_path / "real.txt"
    target.write_text("ok")
    link = tmp_path / "link_to_real.txt"
    link.symlink_to(target)

    # Default behaviour (reject_symlinks=False): symlink is accepted.
    resolved = validate_path_within(link, [tmp_path])
    assert resolved.exists()


# ---------------------------------------------------------------------------
# Mutant #8: ``and`` → ``or`` in the absolute-path branch
# ---------------------------------------------------------------------------


def test_absolute_path_ignores_resolve_relative_to(tmp_path):
    """An absolute path MUST NOT be re-anchored under ``resolve_relative_to``.

    The source's ``if not p.is_absolute() and resolve_relative_to is not None:``
    is the guard — flipping ``and`` to ``or`` would prepend ``resolve_relative_to``
    to absolute paths too, producing nonsense like ``/tmp/foo//etc/passwd``
    (which on Linux still resolves to /etc/passwd, but the type-coercion is wrong).

    We assert that an absolute path inside ``allowed_dirs`` resolves correctly
    even when ``resolve_relative_to`` is also set — exercising the AND
    short-circuit.

    Kills mutmut mutant #8.
    """
    abs_path = tmp_path / "absolute.txt"
    abs_path.write_text("absolute content")

    # Pass the absolute path AND a resolve_relative_to. The function must
    # ignore resolve_relative_to (because the path is absolute) and resolve
    # the file directly.
    other_dir = tmp_path.parent / "other"
    other_dir.mkdir(exist_ok=True)
    resolved = validate_path_within(
        abs_path,
        [tmp_path],
        resolve_relative_to=other_dir,  # MUST be ignored for absolute paths
        must_exist=True,
    )
    assert resolved == abs_path.resolve()


# ---------------------------------------------------------------------------
# Mutant #12: ``or`` → ``and`` in the symlink check
# ---------------------------------------------------------------------------


def test_symlink_rejection_triggers_when_only_resolved_is_symlink(tmp_path, monkeypatch):
    """The source's symlink check is::

        if reject_symlinks and (Path(path).is_symlink() or resolved.is_symlink()):

    Mutant #12 flips ``or`` to ``and`` — meaning rejection would only fire
    when BOTH the source and the resolved are symlinks. Cover the ``only
    one is a symlink`` case so the mutant is killed.

    We construct a chain: tmp_path/link → tmp_path/real (a regular file).
    ``Path(link).is_symlink()`` is True; ``link.resolve().is_symlink()``
    is False. With the original ``or``, rejection fires; with the mutant
    ``and``, rejection silently doesn't fire.
    """
    real = tmp_path / "real.txt"
    real.write_text("ok")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    # link.is_symlink() == True, link.resolve().is_symlink() == False.
    # With reject_symlinks=True, we MUST reject.
    with pytest.raises(HTTPException) as exc:
        validate_path_within(
            link,
            [tmp_path],
            reject_symlinks=True,
            error_label="testfile",
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# must_exist=True returns 404 (vs 403 for traversal)
# ---------------------------------------------------------------------------


def test_must_exist_returns_404_for_missing_file(tmp_path):
    """A path that's INSIDE the allowed dir but doesn't exist must produce
    404 (not 403). This distinguishes "denied access" (403) from "the file
    you have access to is gone" (404)."""
    missing = tmp_path / "not_there.csv"

    with pytest.raises(HTTPException) as exc:
        validate_path_within(
            missing,
            [tmp_path],
            must_exist=True,
            error_label="csv",
        )
    assert exc.value.status_code == 404
    assert "Csv" in exc.value.detail or "not found" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# Mutant #25: ensure_dir parents=True → False
# ---------------------------------------------------------------------------


def test_ensure_dir_creates_intermediate_parents(tmp_path):
    """``ensure_dir`` must create intermediate parent directories — the
    most common usage (``ensure_dir(/data/uploads/job-123/output)``)
    requires ``parents=True``.

    Kills mutmut mutant #25 (``parents=True`` → ``parents=False``):
    flipping it would raise ``FileNotFoundError`` when any intermediate
    parent didn't exist.
    """
    deep = tmp_path / "a" / "b" / "c" / "d"
    assert not deep.exists()

    result = ensure_dir(deep)
    assert result.exists()
    assert result.is_dir()
    assert result == deep
    # Intermediate parents were also created.
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_ensure_dir_is_idempotent(tmp_path):
    """Calling ``ensure_dir`` twice must succeed (``exist_ok=True``)."""
    target = tmp_path / "double" / "create"
    ensure_dir(target)
    # Must not raise the second time.
    ensure_dir(target)
    assert target.is_dir()
