import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Use Redis as the storage backend so rate limits are shared across workers.
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Tests trip the per-route rate limit (e.g. 10/min for /analyze) because
# every test in a class shares the same TestClient IP. Set
# ``INZYTS_DISABLE_RATE_LIMIT=1`` to make the limiter a no-op for the
# duration of a test session.
_DISABLED = os.environ.get("INZYTS_DISABLE_RATE_LIMIT") == "1"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=_REDIS_URL,
    enabled=not _DISABLED,
)
