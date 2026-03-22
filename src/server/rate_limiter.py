import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Use Redis as the storage backend so rate limits are shared across workers.
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=_REDIS_URL,
)
