"""Regression tests for the security / robustness hardening added in the audit pass.

These are pure unit tests (no DB, no network) covering:
  * LLM retry predicate — retries transient errors, NOT permanent ones.
  * DB host SSRF block — checks all resolved addresses.
  * CORS startup validation — rejects wildcard.
  * JWT algorithm allowlist.
  * CSV-hash cache bounded eviction.
  * Celery reliability config.
"""

import os

import pytest


# --------------------------------------------------------------------------
# LLM retry predicate
# --------------------------------------------------------------------------

def test_llm_retry_predicate_classifies_errors():
    from src.llm.provider import _is_retryable_llm_error

    class RateLimit(Exception):
        status_code = 429

    class ServerErr(Exception):
        status_code = 503

    class AuthErr(Exception):
        status_code = 401

    class BadRequest(Exception):
        status_code = 400

    class OverloadedError(Exception):  # name-based match, no status
        pass

    class Weird(Exception):
        pass

    # Transient → retry
    assert _is_retryable_llm_error(RateLimit()) is True
    assert _is_retryable_llm_error(ServerErr()) is True
    assert _is_retryable_llm_error(ConnectionError()) is True
    assert _is_retryable_llm_error(TimeoutError()) is True
    assert _is_retryable_llm_error(OverloadedError()) is True

    # Permanent → fail fast (do NOT retry)
    assert _is_retryable_llm_error(AuthErr()) is False
    assert _is_retryable_llm_error(BadRequest()) is False
    assert _is_retryable_llm_error(Weird()) is False


def test_llm_retry_predicate_reads_nested_response_status():
    from src.llm.provider import _is_retryable_llm_error

    class Resp:
        status_code = 500

    class ErrWithResponse(Exception):
        response = Resp()

    assert _is_retryable_llm_error(ErrWithResponse()) is True


# --------------------------------------------------------------------------
# DB host SSRF block
# --------------------------------------------------------------------------

def test_db_host_block_localhost_and_metadata():
    from src.utils.db_utils import _is_db_host_blocked

    assert _is_db_host_blocked("postgresql://u:p@localhost:5432/db") is True
    assert _is_db_host_blocked("postgresql://u:p@127.0.0.1:5432/db") is True
    assert _is_db_host_blocked("postgresql://u:p@169.254.169.254:5432/db") is True  # cloud metadata
    assert _is_db_host_blocked("postgresql://u:p@0.0.0.0:5432/db") is True


def test_db_host_block_allows_private_and_public():
    from src.utils.db_utils import _is_db_host_blocked

    # RFC1918 private addresses are legitimate customer DBs — not blocked.
    assert _is_db_host_blocked("postgresql://u:p@10.0.0.5:5432/db") is False
    assert _is_db_host_blocked("postgresql://u:p@192.168.1.20:5432/db") is False


def test_db_host_block_respects_opt_out(monkeypatch):
    from src.utils import db_utils

    monkeypatch.setenv("INZYTS_DB_URI_ALLOW_LOOPBACK", "1")
    assert db_utils._is_db_host_blocked("postgresql://u:p@127.0.0.1:5432/db") is False


# --------------------------------------------------------------------------
# CORS startup validation
# --------------------------------------------------------------------------

def test_cors_validation_rejects_wildcard():
    from src.server.main import _validate_cors_origins

    with pytest.raises(RuntimeError):
        _validate_cors_origins(["http://localhost:5173", "*"])


def test_cors_validation_passes_explicit_origins():
    from src.server.main import _validate_cors_origins

    origins = ["http://localhost:5173", "https://app.example.com"]
    assert _validate_cors_origins(origins) == origins


# --------------------------------------------------------------------------
# JWT algorithm allowlist
# --------------------------------------------------------------------------

def test_jwt_algorithm_allowlist(monkeypatch):
    from src.config import Settings

    monkeypatch.setenv("JWT_SECRET_KEY", "x")
    monkeypatch.setenv("ADMIN_PASSWORD", "x")

    monkeypatch.setenv("JWT_ALGORITHM", "none")
    with pytest.raises(Exception):
        Settings()

    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    assert Settings().jwt_algorithm == "HS256"


# --------------------------------------------------------------------------
# CSV-hash cache bounded eviction
# --------------------------------------------------------------------------

def test_hash_cache_is_bounded(tmp_path):
    from src.utils.cache_manager import CacheManager

    cm = CacheManager()
    cm.MAX_HASH_CACHE_ENTRIES = 5  # shrink for the test
    # Create and hash more distinct files than the cap allows.
    for i in range(12):
        f = tmp_path / f"f{i}.csv"
        f.write_text(f"col\n{i}\n")
        cm.get_csv_hash(str(f))
    assert len(cm._hash_cache) <= 5


# --------------------------------------------------------------------------
# Celery reliability config
# --------------------------------------------------------------------------

def test_celery_reliability_config():
    from src.server.celery_app import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.worker_max_tasks_per_child == 200
