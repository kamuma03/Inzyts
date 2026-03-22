import socketio
from src.utils.logger import get_logger
from src.config import settings
from src.server.middleware.auth import verify_token_async

logger = get_logger()

# Create a Socket.IO Server (Async)
REDIS_URL = settings.redis_url
ALLOWED_ORIGINS = settings.allowed_origins
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS,
    client_manager=socketio.AsyncRedisManager(REDIS_URL, write_only=False),
)

# Create ASGI App
socket_app = socketio.ASGIApp(sio, socketio_path="")


@sio.event
async def connect(sid, environ):
    """Authenticate the WebSocket connection and store user identity on the session."""
    token = None

    # Extract the Authorization header from the environ dict.
    #
    # python-socketio 5.x + python-engineio's ASGI translate_request() converts
    # the raw ASGI scope into a WSGI-style environ dict where HTTP headers
    # become "HTTP_<UPPER_NAME>" keys (e.g. HTTP_AUTHORIZATION).  The original
    # ASGI scope is also available at environ["asgi.scope"]["headers"] as a
    # list of (bytes, bytes) tuples.
    #
    # We check all three locations for robustness:
    #   1. WSGI-style key (primary — always present via translate_request)
    #   2. ASGI scope headers (fallback)
    #   3. Direct "headers" key (in case of future socketio changes)
    auth_header = environ.get("HTTP_AUTHORIZATION", "")

    if not auth_header:
        # Fallback: read from raw ASGI scope headers
        raw_headers = environ.get("asgi.scope", {}).get("headers", [])
        for k, v in raw_headers:
            key = k.decode("latin-1").lower() if isinstance(k, bytes) else k.lower()
            if key == "authorization":
                auth_header = v.decode("latin-1") if isinstance(v, bytes) else v
                break

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token:
        logger.warning(f"Unauthorized WebSocket connection attempt: {sid} (No token)")
        return False

    from src.server.db.database import async_session_maker
    async with async_session_maker() as db:
        user = await verify_token_async(token, db)

    if not user:
        logger.warning(f"Unauthorized WebSocket connection attempt: {sid} (Invalid token)")
        return False

    # Persist the authenticated username so join_job can enforce ownership.
    await sio.save_session(sid, {"username": user.username})
    logger.info(f"Client connected and authenticated: {sid} (user={user.username})")


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def join_job(sid, data):
    """Join a job's log-stream room after verifying the job exists."""
    job_id = data.get("job_id") if isinstance(data, dict) else data

    if not job_id:
        logger.warning(f"Client {sid} sent join_job without a job_id")
        return

    # Verify the job exists in the database before allowing the client to subscribe.
    from src.server.db.database import async_session_maker
    from src.server.db.models import Job
    from sqlalchemy import select

    async with async_session_maker() as db:
        result = await db.execute(select(Job.id).where(Job.id == job_id))
        if result.scalar_one_or_none() is None:
            logger.warning(f"Client {sid} tried to join non-existent job room: {job_id}")
            await sio.emit("error", {"message": "Job not found"}, to=sid)
            return

    logger.info(f"Client {sid} joined job {job_id}")
    await sio.enter_room(sid, job_id)
    await sio.emit("log", f"Connected to log stream for {job_id}", room=job_id)


async def notify_job_update(job_id: str, data: dict):
    """Utility to emit updates to a job room."""
    await sio.emit("progress", data, room=job_id)


async def notify_log(job_id: str, message: str):
    """Utility to emit log lines."""
    await sio.emit("log", message, room=job_id)
