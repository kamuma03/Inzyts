"""Regression tests for the C-2 ``_killpg`` safety invariants.

The original ``_killpg`` had two latent bugs that could SIGKILL the parent
process group (worker, test runner, shell, *desktop session*):

1. **PID-reuse race**: between ``has_kernel`` check and ``getpgid(pid)``
   the kernel could exit and Linux could reuse its PID for an unrelated
   process. ``killpg(reused_pgid, SIGKILL)`` would then nuke the wrong group.
2. **`setsid()` failure**: the preexec_fn caught ``OSError`` from
   ``setsid()`` and returned silently, leaving the child in the parent's
   process group. ``_killpg`` would then resolve to the parent's pgid and
   SIGKILL the entire test runner / shell / desktop session.

The fix layers three guards in ``_killpg``:

* refuse to kill if ``pgid == own_pgid`` (would nuke the parent),
* require ``pgid == kernel_pid`` (a successful ``setsid()`` makes the
  child the leader of a new session, so this MUST hold),
* fall back to ``os.kill(pid, SIGKILL)`` on the original pid only when
  either guard trips.

These tests drive ``_killpg`` through each branch with mocked km/pid/getpgid
combinations and verify ``os.killpg`` is NEVER called when the invariants
fail.
"""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

import pytest

from src.services.sandbox_executor import KernelSandbox


# ---------------------------------------------------------------------------
# Helpers — build a KernelSandbox without actually starting a kernel.
# ---------------------------------------------------------------------------


def _make_sandbox_with_pid(pid: int) -> KernelSandbox:
    """Return a KernelSandbox whose km.kernel.pid resolves to ``pid``.

    Bypasses ``_start_kernel`` (which would spawn a real subprocess) by
    constructing the object via ``__new__`` and wiring the minimum state
    ``_killpg`` reads.
    """
    sb = KernelSandbox.__new__(KernelSandbox)
    sb.policy = MagicMock(name="policy")
    sb.km = MagicMock()
    sb.km.has_kernel = True
    sb.km.kernel = MagicMock()
    sb.km.kernel.pid = pid
    sb.kc = None
    sb._working_dir = None
    sb._working_dir_owned = False
    return sb


# ---------------------------------------------------------------------------
# Invariant 1: pgid != own_pgid
# ---------------------------------------------------------------------------


def test_killpg_refuses_when_pgid_matches_parent():
    """If setsid() failed in the child, the kernel inherits the parent's
    pgid. ``_killpg`` must detect this and NEVER killpg the parent group —
    instead, fall back to ``os.kill`` on the kernel pid only.
    """
    sb = _make_sandbox_with_pid(pid=12345)
    parent_pgid = 9999

    with patch("src.services.sandbox_executor.os") as mock_os:
        mock_os.getpgid.return_value = parent_pgid  # mirrors a setsid failure
        mock_os.getpgrp.return_value = parent_pgid  # parent's own pgid
        mock_os.killpg = MagicMock()
        mock_os.kill = MagicMock()
        # Patch out the constants the function reads from the real os module.
        mock_os.SIGKILL = signal.SIGKILL
        # ProcessLookupError + friends still need to be the real types.
        import builtins
        mock_os.ProcessLookupError = builtins.ProcessLookupError = ProcessLookupError

        sb._killpg()

    # The killpg path must NEVER be taken when the resolved pgid matches
    # our own — otherwise we'd SIGKILL the parent process group.
    mock_os.killpg.assert_not_called()
    # The fallback path SIGKILLs the kernel pid only, which is safe.
    mock_os.kill.assert_called_once_with(12345, signal.SIGKILL)


# ---------------------------------------------------------------------------
# Invariant 2: pgid == kernel_pid (a successful setsid makes the child a
#              session leader, so its pgid equals its pid).
# ---------------------------------------------------------------------------


def test_killpg_refuses_when_pgid_does_not_match_kernel_pid():
    """PID-reuse race: kernel exits, Linux reassigns its PID to an unrelated
    process before ``getpgid()``. The resolved pgid then belongs to that
    other process — ``_killpg`` must refuse to killpg it and fall back
    to ``os.kill(original_pid)`` only.
    """
    sb = _make_sandbox_with_pid(pid=12345)

    with patch("src.services.sandbox_executor.os") as mock_os:
        # The kernel pid still resolves to *some* pgid, but it is not the
        # kernel's own pgid (because the PID was reused).
        mock_os.getpgid.return_value = 7777
        mock_os.getpgrp.return_value = 1  # parent pgid (different from 7777)
        mock_os.killpg = MagicMock()
        mock_os.kill = MagicMock()
        mock_os.SIGKILL = signal.SIGKILL
        mock_os.ProcessLookupError = ProcessLookupError

        sb._killpg()

    # Refused — pgid (7777) != kernel pid (12345)
    mock_os.killpg.assert_not_called()
    # Safer fallback used: SIGKILL only the original pid we recorded.
    mock_os.kill.assert_called_once_with(12345, signal.SIGKILL)


# ---------------------------------------------------------------------------
# Happy path: pgid == pid != own_pgid → killpg fires.
# ---------------------------------------------------------------------------


def test_killpg_succeeds_when_invariants_hold():
    """A successful setsid() in the child means pgid == pid, and pgid !=
    own_pgid (the child is in its own session). In that case ``_killpg``
    must call ``os.killpg`` so the entire kernel process tree dies.
    """
    sb = _make_sandbox_with_pid(pid=12345)

    with patch("src.services.sandbox_executor.os") as mock_os:
        mock_os.getpgid.return_value = 12345  # equals kernel pid → setsid OK
        mock_os.getpgrp.return_value = 999    # parent pgid is different
        mock_os.killpg = MagicMock()
        mock_os.kill = MagicMock()
        mock_os.SIGKILL = signal.SIGKILL

        sb._killpg()

    # Happy path: killpg the kernel's own group.
    mock_os.killpg.assert_called_once_with(12345, signal.SIGKILL)
    # The single-pid fallback should NOT also run — that would be
    # redundant since killpg already covers the leader.
    mock_os.kill.assert_not_called()


# ---------------------------------------------------------------------------
# Liveness short-circuits — kernel already gone, no signal of any kind.
# ---------------------------------------------------------------------------


def test_killpg_noop_when_no_kernel():
    """If the KernelManager has no live kernel, ``_killpg`` must not even
    look up a pgid. Otherwise we'd risk killing on a stale pid."""
    sb = KernelSandbox.__new__(KernelSandbox)
    sb.policy = MagicMock()
    sb.km = MagicMock()
    sb.km.has_kernel = False
    sb.kc = None

    with patch("src.services.sandbox_executor.os") as mock_os:
        sb._killpg()

    mock_os.getpgid.assert_not_called()
    mock_os.killpg.assert_not_called()
    mock_os.kill.assert_not_called()


def test_killpg_noop_when_pid_missing():
    """km.kernel exists but its pid attribute is None (kernel still
    bootstrapping). Don't kill — wait for the next timeout cycle."""
    sb = _make_sandbox_with_pid(pid=None)

    with patch("src.services.sandbox_executor.os") as mock_os:
        sb._killpg()

    mock_os.getpgid.assert_not_called()
    mock_os.killpg.assert_not_called()
    mock_os.kill.assert_not_called()


def test_killpg_swallows_lookup_error_during_pgid_resolve():
    """``os.getpgid`` can raise ProcessLookupError if the kernel exits between
    our liveness check and the call. We must NOT propagate the exception —
    return cleanly so the parent execute-loop can still mark the result."""
    sb = _make_sandbox_with_pid(pid=12345)

    with patch("src.services.sandbox_executor.os") as mock_os:
        mock_os.getpgid.side_effect = ProcessLookupError("kernel gone")
        mock_os.killpg = MagicMock()
        mock_os.kill = MagicMock()

        # Must not raise.
        sb._killpg()

    mock_os.killpg.assert_not_called()
    mock_os.kill.assert_not_called()
