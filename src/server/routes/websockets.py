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

    # Prefer the Authorization header over the query string to avoid token leaking
    # into server access logs. Query string is kept as a fallback for clients that
    # cannot set custom headers (e.g. browser-native WebSocket).
    headers: dict[str, str] = {}
    for k, v in environ.get("headers_raw", environ.get("asgi.scope", {}).get("headers", [])):
        key = k.decode("latin-1").lower() if isinstance(k, bytes) else k.lower()
        val = v.decode("latin-1") if isinstance(v, bytes) else v
        headers[key] = val
    auth_header = headers.get("authorization")
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
