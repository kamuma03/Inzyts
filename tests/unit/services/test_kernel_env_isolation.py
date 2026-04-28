"""Regression tests for the M-8 fix: ``KernelSession.start()`` must not
mutate the worker process's own ``os.environ``.

Previously, ``start()`` did:

    _os.environ["_INZYTS_KERNEL_CSV_PATH"] = self.csv_path

which permanently polluted the worker process's env. With multiple jobs
running on the same worker, Job B would observe Job A's most-recent dataset
path in ``os.environ`` — a quiet cross-job leakage bug and a hostile signal
in security audits.

The fix passes the path via the ``extra_env`` argument on
``SandboxExecutor`` / ``KernelSandbox`` so it reaches the kernel subprocess
only, never the parent's env.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.services.kernel_session_manager import KernelSession


# ---------------------------------------------------------------------------
# Fixture: a SandboxExecutor stub that captures kwargs but does no work.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_executor_class():
    """Patch SandboxExecutor at the import location used by the session.

    Returns the captured constructor calls so tests can inspect ``extra_env``.
    """
    with patch(
        "src.services.kernel_session_manager.SandboxExecutor"
    ) as cls:
        instance = MagicMock()
        # execute_cell during bootstrap returns a "successful" result.
        result = MagicMock()
        result.success = True
        result.output = "Loaded 100 rows x 5 columns\nint64\nobject"
        result.error_name = None
        result.error_value = None
        instance.execute_cell.return_value = result
        instance.kc = MagicMock()
        cls.return_value = instance
        yield cls


# ---------------------------------------------------------------------------
# Test: os.environ untouched after KernelSession.start()
# ---------------------------------------------------------------------------


def test_session_start_does_not_mutate_os_environ(mock_executor_class):
    """The worker's own ``os.environ`` must not gain any new keys after
    starting a kernel session. Cross-job leakage of dataset paths via the
    parent process env is a regression we explicitly fixed."""
    snapshot = dict(os.environ)
    snapshot_keys = set(snapshot.keys())

    session = KernelSession(job_id="test-job-1", csv_path="/data/test.csv")
    session.start()

    new_keys = set(os.environ.keys()) - snapshot_keys

    # No new keys may appear — especially not the legacy
    # ``_INZYTS_KERNEL_CSV_PATH`` from the pre-M-8 implementation.
    assert new_keys == set(), (
        f"KernelSession.start() leaked env keys into os.environ: {new_keys}"
    )
    assert "_INZYTS_KERNEL_CSV_PATH" not in os.environ, (
        "Legacy env-mutation bug regressed — _INZYTS_KERNEL_CSV_PATH "
        "should be passed only to the kernel subprocess via extra_env."
    )


def test_session_start_passes_csv_path_via_extra_env(mock_executor_class):
    """The dataset path must reach the kernel via the SandboxExecutor's
    ``extra_env`` argument (subprocess-only), not via os.environ."""
    csv_path = "/data/uploads/specific-dataset.csv"

    session = KernelSession(job_id="test-job-2", csv_path=csv_path)
    session.start()

    # SandboxExecutor was constructed once.
    assert mock_executor_class.call_count == 1
    _args, kwargs = mock_executor_class.call_args

    # The path was routed through extra_env so it lands in the kernel
    # subprocess env at fork time.
    extra = kwargs.get("extra_env")
    assert extra is not None, "extra_env kwarg missing — M-8 regression"
    assert extra.get("_INZYTS_KERNEL_CSV_PATH") == csv_path


def test_session_extra_env_is_isolated_per_session(mock_executor_class):
    """Two concurrent sessions must each get their own extra_env. A shared
    dict would mean mutations on one session bleed into the other."""
    s1 = KernelSession(job_id="job-a", csv_path="/data/a.csv")
    s1.start()
    s2 = KernelSession(job_id="job-b", csv_path="/data/b.csv")
    s2.start()

    calls = mock_executor_class.call_args_list
    assert len(calls) == 2

    e1 = calls[0].kwargs.get("extra_env") or {}
    e2 = calls[1].kwargs.get("extra_env") or {}

    assert e1["_INZYTS_KERNEL_CSV_PATH"] == "/data/a.csv"
    assert e2["_INZYTS_KERNEL_CSV_PATH"] == "/data/b.csv"
    # Distinct dict objects: mutating one must not affect the other.
    assert e1 is not e2
