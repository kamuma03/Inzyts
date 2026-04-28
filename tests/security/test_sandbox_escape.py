"""Adversarial tests targeting the kernel sandbox.

These tests do NOT spawn real kernels — that's the ``slow``-marked
``test_sandbox_security.py`` job, which is high-risk on developer
machines (see SECURITY.md "Sandbox _killpg Safety Invariants").

Instead, they verify the *guardrails* using mocks:

* The policy is wired with the right ``setrlimit`` constants.
* Credential env vars are stripped from the kernel subprocess.
* The proxy-blackhole URLs are unreachable values.
* The ``preexec_fn`` setsid failure path calls ``os._exit(127)``
  (so a setsid failure can't leave the child in the parent's group).
* ``execute_cell`` truncates oversized output / images / tracebacks
  before they hit the LLM retry payload.

For a paranoid run that also exercises actual rlimits + signals on real
kernels, ``pytest -m slow tests/unit/services/test_sandbox_security.py``
is the gated suite — opt in only.
"""

from __future__ import annotations

import os
import resource
import signal
from unittest.mock import MagicMock, patch

import pytest

from src.services.sandbox_executor import (
    KernelSandbox,
    PRODUCTION_POLICY,
    SandboxPolicy,
    _build_preexec_fn,
    truncate_str,
    MAX_OUTPUT_LEN,
    MAX_TRACEBACK_LEN,
)


# ---------------------------------------------------------------------------
# Policy invariants
# ---------------------------------------------------------------------------


class TestProductionPolicy:

    def test_production_policy_blocks_egress_by_default(self):
        """``network_egress_blocked=True`` is the production default —
        if this regresses, kernels can hit the network without iptables."""
        assert PRODUCTION_POLICY.network_egress_blocked is True

    def test_production_policy_has_finite_resource_caps(self):
        """No "unlimited" caps in production — every dimension must have
        a finite limit."""
        p = PRODUCTION_POLICY
        assert 0 < p.memory_mb <= 8192
        assert 0 < p.cpu_seconds <= 600
        assert 0 < p.timeout_seconds <= 300
        assert 0 < p.max_processes <= 256
        assert 0 < p.max_open_files <= 1024
        assert 0 < p.max_file_size_mb <= 1024


# ---------------------------------------------------------------------------
# preexec_fn: setsid failure must terminate the child immediately
# ---------------------------------------------------------------------------


class TestPreexecFnSetsidGuard:

    def test_setsid_failure_terminates_child_with_127(self):
        """If ``os.setsid()`` fails in the child, the preexec_fn MUST
        call ``os._exit(127)`` instead of swallowing the OSError. A
        silently-failing setsid leaves the kernel in the parent's pgid —
        the bug that caused the original PC log-off.

        IMPORTANT: we mock ``resource`` too so that, when ``os._exit`` is
        mocked (and therefore returns instead of exiting), the function's
        fall-through into the ``setrlimit`` loop doesn't actually apply
        real RLIMIT_NPROC=64 to the test runner process. Without this
        guard the test runner becomes unable to spawn new threads, and
        every subsequent test that uses ``threading.Thread.start()``
        (notably the SSRF http.server fixture) crashes with
        ``RuntimeError: can't start new thread``.
        """
        preexec = _build_preexec_fn(PRODUCTION_POLICY)

        with patch(
            "src.services.sandbox_executor.os.setsid",
            side_effect=OSError("EPERM"),
        ), patch(
            "src.services.sandbox_executor.os._exit"
        ) as mock_exit, patch(
            "src.services.sandbox_executor.os.write"
        ), patch(
            "src.services.sandbox_executor.resource"
        ) as mock_resource:
            # Provide real rlimit constants so the closure's getattr() calls
            # resolve to truthy values; setrlimit itself is the mock attr,
            # so no real limit is applied.
            mock_resource.RLIMIT_AS = resource.RLIMIT_AS
            mock_resource.RLIMIT_CPU = resource.RLIMIT_CPU
            mock_resource.RLIMIT_NPROC = resource.RLIMIT_NPROC
            mock_resource.RLIMIT_NOFILE = resource.RLIMIT_NOFILE
            mock_resource.RLIMIT_FSIZE = resource.RLIMIT_FSIZE
            preexec()

        mock_exit.assert_called_once_with(127)

    def test_setsid_success_proceeds_to_setrlimit(self):
        """When setsid succeeds, the rlimit hardening applies normally.

        CRITICAL: this test calls ``preexec()`` directly in the test
        runner. We MUST mock both ``os.setsid`` (which would otherwise
        make the test runner a new session leader) and the entire
        ``resource`` module (which would otherwise apply real rlimits
        to the test runner — RLIMIT_NPROC=64 in particular would cause
        ``RuntimeError: can't start new thread`` in subsequent tests).
        """
        preexec = _build_preexec_fn(PRODUCTION_POLICY)

        with patch(
            "src.services.sandbox_executor.os.setsid"
        ) as mock_setsid, patch(
            "src.services.sandbox_executor.os._exit"
        ) as mock_exit, patch(
            "src.services.sandbox_executor.os.write"
        ), patch(
            "src.services.sandbox_executor.resource"
        ) as mock_resource:
            # Wire setrlimit so the loop actually runs without errors.
            # We provide real rlimit constants so the closure's
            # ``getattr(resource, "RLIMIT_X", None)`` resolves; setrlimit
            # itself stays mocked so no real limit applies to this process.
            mock_resource.RLIMIT_AS = resource.RLIMIT_AS
            mock_resource.RLIMIT_CPU = resource.RLIMIT_CPU
            mock_resource.RLIMIT_NPROC = resource.RLIMIT_NPROC
            mock_resource.RLIMIT_NOFILE = resource.RLIMIT_NOFILE
            mock_resource.RLIMIT_FSIZE = resource.RLIMIT_FSIZE
            preexec()

        mock_setsid.assert_called_once()
        mock_exit.assert_not_called()
        # All five rlimits applied.
        assert mock_resource.setrlimit.call_count >= 5


# ---------------------------------------------------------------------------
# Env stripping: credentials must not survive into the kernel
# ---------------------------------------------------------------------------


class TestKernelEnvStripping:

    @pytest.fixture
    def sandbox_no_kernel(self):
        """Build a KernelSandbox without starting a real kernel."""
        sb = KernelSandbox.__new__(KernelSandbox)
        sb.policy = PRODUCTION_POLICY
        sb._extra_env = {}
        return sb

    @pytest.mark.parametrize(
        "secret_var",
        [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "JUPYTER_TOKEN",
            "INZYTS_API_TOKEN",
            "JWT_SECRET_KEY",
            "POSTGRES_PASSWORD",
            "ADMIN_PASSWORD",
            "INZYTS__LLM__ANTHROPIC_API_KEY",
            "INZYTS__LLM__OPENAI_API_KEY",
            "INZYTS__LLM__GEMINI_API_KEY",
            "INZYTS__JUPYTER__TOKEN",
        ],
    )
    def test_each_secret_is_stripped(self, sandbox_no_kernel, monkeypatch, secret_var):
        """Every credential env var the worker has access to must be
        stripped before the kernel forks. A leak would let LLM-generated
        code echo our secrets back to us via cell output."""
        monkeypatch.setenv(secret_var, "leaked-value")
        env = sandbox_no_kernel._build_kernel_env()
        assert secret_var not in env, (
            f"{secret_var} survived into kernel env — credential leak"
        )

    def test_innocent_env_vars_preserved(self, sandbox_no_kernel, monkeypatch):
        """Non-secret env vars should pass through. The kernel needs
        ``PATH``, ``HOME``, etc. to function."""
        monkeypatch.setenv("MY_HARMLESS_VAR", "harmless")
        env = sandbox_no_kernel._build_kernel_env()
        assert env.get("MY_HARMLESS_VAR") == "harmless"


# ---------------------------------------------------------------------------
# Proxy blackhole: env vars point at unreachable address
# ---------------------------------------------------------------------------


class TestProxyBlackhole:

    @pytest.fixture
    def sandbox_egress_blocked(self):
        sb = KernelSandbox.__new__(KernelSandbox)
        sb.policy = PRODUCTION_POLICY  # network_egress_blocked=True
        sb._extra_env = {}
        return sb

    @pytest.fixture
    def sandbox_egress_allowed(self):
        sb = KernelSandbox.__new__(KernelSandbox)
        sb.policy = SandboxPolicy(
            timeout_seconds=15,
            network_egress_blocked=False,
            name="trusted",
        )
        sb._extra_env = {}
        return sb

    def test_proxy_env_points_at_blackhole(self, sandbox_egress_blocked):
        """All standard proxy env vars must point at the unreachable
        ``http://127.0.0.1:1`` address. ``no_proxy`` must be empty so
        nothing escapes."""
        env = sandbox_egress_blocked._build_kernel_env()
        for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
            assert env.get(var) == "http://127.0.0.1:1", (
                f"{var} not blackholed — egress block regression"
            )
        assert env.get("no_proxy") == ""
        assert env.get("NO_PROXY") == ""

    def test_proxy_env_not_set_when_egress_allowed(self, sandbox_egress_allowed):
        """A trusted policy must NOT inject the blackhole — it would
        prevent legitimate API calls from inside the trusted kernel."""
        env = sandbox_egress_allowed._build_kernel_env()
        # If the parent had a real proxy, that's preserved; we only
        # assert the blackhole isn't actively injected.
        assert env.get("http_proxy", "") != "http://127.0.0.1:1"


# ---------------------------------------------------------------------------
# Output truncation — bound the LLM retry payload size
# ---------------------------------------------------------------------------


class TestOutputTruncation:

    def test_short_text_is_returned_unchanged(self):
        text = "small output"
        assert truncate_str(text) == text

    def test_long_text_is_truncated_with_marker(self):
        """Outputs longer than ``MAX_OUTPUT_LEN`` must be truncated.
        Otherwise an infinite ``while True: print('x')`` cell would
        balloon the LLM retry prompt and burn token budget."""
        text = "x" * (MAX_OUTPUT_LEN * 3)
        result = truncate_str(text)
        assert len(result) < len(text)
        assert "TRUNCATED_FOR_SIZE" in result

    def test_traceback_truncation_is_independent_of_output(self):
        """Tracebacks have their own larger cap so error context isn't
        lost as aggressively as stdout."""
        tb = "Traceback line\n" * 1000
        result = truncate_str(tb, max_len=MAX_TRACEBACK_LEN)
        assert len(result) <= MAX_TRACEBACK_LEN + len(
            "\n\n...[TRUNCATED_FOR_SIZE]...\n\n"
        )

    def test_truncate_handles_non_string_input(self):
        """Defence-in-depth: ``truncate_str`` must coerce to string,
        not raise, when given a non-string. The kernel can return
        weird types from a buggy cell."""
        assert truncate_str(None) == ""
        # Numbers, bools, etc. are stringified.
        assert truncate_str(12345) == "12345"
