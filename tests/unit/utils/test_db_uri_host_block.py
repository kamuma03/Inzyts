"""Regression tests for the M-7 fix: ``validate_db_uri`` rejects hosts
that point at the platform's own internal services or at loopback /
link-local ranges.

Without this guard, an authenticated analyst could submit a ``db_uri``
of ``postgresql://postgres:<known_password>@db:5432/inzyts`` and have
Inzyts connect to its OWN metadata database. The iptables egress
allowlist permits ``db`` → analyst can read audit logs, user table, etc.

The fix blocks:
* loopback (``127.0.0.0/8``, ``::1``, ``localhost``, ``0.0.0.0``)
* link-local (``169.254.0.0/16`` — covers AWS metadata at 169.254.169.254)
* docker-internal hostnames (``db``, ``redis``, plus ``INZYTS_INTERNAL_HOSTS``)

Operators who legitimately run an analytics DB on the same host can opt
out via ``INZYTS_DB_URI_ALLOW_LOOPBACK=1``.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.utils.db_utils import _is_db_host_blocked, validate_db_uri
from src.utils.errors import DataValidationError


# ---------------------------------------------------------------------------
# Hosts that MUST be blocked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        # Loopback — would hit the worker's own listening services.
        "postgresql://u:p@localhost:5432/db",
        "postgresql://u:p@127.0.0.1:5432/db",
        "mysql://u:p@127.0.0.1:3306/db",
        "postgresql://u:p@0.0.0.0:5432/db",
        # Docker-internal hostnames — defined by docker-compose.yml.
        "postgresql://u:p@db:5432/inzyts",
        "postgresql://u:p@redis:6379/0",
        # Link-local — covers AWS instance metadata.
        "postgresql://u:p@169.254.169.254:80/db",
        # Mixed-case loopback resolves identically — make sure we don't
        # only check lowercase.
        "postgresql://u:p@LocalHost:5432/db",
    ],
)
def test_validate_db_uri_blocks_internal_hosts(uri):
    """Each of these hosts is platform-internal or a metadata pivot
    point. ``validate_db_uri`` must raise ``DataValidationError``."""
    # Make sure the loopback opt-out is OFF for this test.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("INZYTS_DB_URI_ALLOW_LOOPBACK", None)
        with pytest.raises(DataValidationError):
            validate_db_uri(uri)


# ---------------------------------------------------------------------------
# Hosts that MUST be allowed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://u:p@warehouse.example.com:5432/analytics",
        "mysql://u:p@db.acme.io:3306/sales",
        "snowflake://u:p@my-org.snowflakecomputing.com/db",
        "bigquery://my-gcp-project/dataset",
        "postgresql://u:p@8.8.8.8:5432/test",   # public IP literal
    ],
)
def test_validate_db_uri_allows_legitimate_hosts(uri):
    """Public hosts (RFC1918 not blocked here intentionally — many real
    customer DBs sit on private networks) must pass validation."""
    # Should not raise.
    validate_db_uri(uri)


# ---------------------------------------------------------------------------
# Opt-out: INZYTS_DB_URI_ALLOW_LOOPBACK=1 lets dev environments connect to
# localhost.
# ---------------------------------------------------------------------------


def test_loopback_opt_out_allows_localhost():
    """Setting ``INZYTS_DB_URI_ALLOW_LOOPBACK=1`` must lift the loopback /
    link-local block for local dev. Internal docker hosts (``db``,
    ``redis``) are still blocked even with the opt-out."""
    uri_local = "postgresql://u:p@localhost:5432/db"

    # Without the opt-out, blocked.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("INZYTS_DB_URI_ALLOW_LOOPBACK", None)
        assert _is_db_host_blocked(uri_local) is True

    # With the opt-out, allowed.
    with patch.dict(os.environ, {"INZYTS_DB_URI_ALLOW_LOOPBACK": "1"}):
        assert _is_db_host_blocked(uri_local) is False


# ---------------------------------------------------------------------------
# Operator-supplied internal-hosts blocklist.
# ---------------------------------------------------------------------------


def test_internal_hosts_env_var_extends_blocklist():
    """``INZYTS_INTERNAL_HOSTS`` lets operators add more docker-network
    service names (e.g. ``flower``, ``ollama``) to the blocklist without
    code changes."""
    with patch.dict(os.environ, {"INZYTS_INTERNAL_HOSTS": "ollama flower"}):
        os.environ.pop("INZYTS_DB_URI_ALLOW_LOOPBACK", None)
        # Default-blocked still works.
        assert _is_db_host_blocked("postgresql://u:p@db:5432/x") is True
        # Extra hosts now also blocked.
        assert _is_db_host_blocked("postgresql://u:p@ollama:11434/x") is True
        assert _is_db_host_blocked("postgresql://u:p@flower:5555/x") is True
        # Unrelated public host still allowed.
        assert _is_db_host_blocked("postgresql://u:p@warehouse.example.com/x") is False


# ---------------------------------------------------------------------------
# Scheme guard still applies independently of host.
# ---------------------------------------------------------------------------


def test_scheme_check_runs_before_host_check():
    """The scheme allowlist (no ``sqlite://`` etc.) must reject early —
    even if the host is fine, an invalid scheme is fatal."""
    with pytest.raises(DataValidationError):
        validate_db_uri("sqlite:///etc/shadow")


def test_dns_resolution_failure_does_not_block():
    """If a hostname doesn't resolve, treat it as a real DB outage signal
    rather than blocking — the scheme guard is the primary protection."""
    # Using a guaranteed-nonexistent TLD — RFC 6761 reserves ``.invalid``.
    # No exception expected; the call surfaces the connection failure
    # later, when create_engine actually tries to dial.
    validate_db_uri("postgresql://u:p@no-such-host.invalid/db")
