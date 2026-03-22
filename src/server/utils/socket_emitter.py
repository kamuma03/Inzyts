import socketio  # type: ignore
import os

_socket_manager = None


def get_socket_manager():
    """
    Returns a synchronous RedisManager for emitting events from worker processes.
    Cached as a module-level singleton to avoid creating a new Redis connection
    pool on every call.
    """
    global _socket_manager
    if _socket_manager is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _socket_manager = socketio.RedisManager(redis_url, write_only=True)
    return _socket_manager
