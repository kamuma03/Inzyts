"""Encrypt request-supplied secrets before they cross the Celery broker.

API credentials (``api_headers``, ``api_auth``) and database URIs may contain
passwords/tokens. Celery serialises task kwargs as JSON into Redis, so anything
passed in the clear is readable by anyone with broker access or task
introspection. We wrap those values with Fernet (symmetric AEAD) using a key
derived from the app's JWT secret, so the broker only ever sees ciphertext.

Helpers are tolerant of legacy plaintext: ``decrypt_value`` returns non-wrapped
input unchanged, so in-flight tasks queued before this change still run.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings

# Marker prefix on the ciphertext so decrypt can distinguish wrapped values from
# legacy plaintext that predates encryption.
_PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """Derive a stable Fernet key from the JWT secret (32-byte urlsafe b64)."""
    digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(value: Any) -> Any:
    """Encrypt a JSON-serialisable value to a prefixed token string.

    ``None`` passes through unchanged (nothing to protect); everything else is
    JSON-encoded then Fernet-encrypted.
    """
    if value is None:
        return None
    import json

    raw = json.dumps(value).encode("utf-8")
    token = _fernet().encrypt(raw).decode("ascii")
    return _PREFIX + token


def decrypt_value(value: Any) -> Any:
    """Inverse of :func:`encrypt_value`. Non-wrapped input is returned as-is so
    plaintext (legacy / already-decrypted) values are handled gracefully."""
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    import json

    token = value[len(_PREFIX):].encode("ascii")
    try:
        raw = _fernet().decrypt(token)
    except InvalidToken:
        # Wrong key or tampered payload — fail closed to None rather than leak.
        return None
    return json.loads(raw.decode("utf-8"))
