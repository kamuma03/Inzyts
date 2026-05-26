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
async def connect(sid, environ, auth=None):
    """Authenticate the WebSocket connection and store user identity on the session.

    Reads the bearer token from any of:
      1. The Socket.IO ``auth`` payload (preferred — works for both polling and
         WebSocket transports, including from browsers where custom headers
         on the WS handshake are blocked by the User-Agent).
      2. The ``Authorization: Bearer …`` header in the WSGI-style environ
         (works for polling, and for Node/test clients that bypass the
         browser's WS header restriction).
      3. The raw ASGI scope headers (defensive fallback for future
         python-socketio / engineio changes).
    """
    token = None

    # 1. Socket.IO auth payload — the recommended path for browser clients.
    if isinstance(auth, dict):
        candidate = auth.get("token")
        if isinstance(candidate, str) and candidate.strip():
            token = candidate.strip()

    # 2 + 3. Authorization header fallbacks.
    if not token:
        auth_header = environ.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            raw_headers = environ.get("asgi.scope", {}).get("headers", [])
            for k, v in raw_headers:
                key = k.decode("latin-1").lower() if isinstance(k, bytes) else k.lower()
                if key == "authorization":
                    auth_header = v.decode("latin-1") if isinstance(v, bytes) else v
                    break
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        logger.warning(f"Unauthorized WebSocket connection attempt: {sid} (No token)")
        return False

    from src.server.db.database import async_session_maker
    async with async_session_maker() as db:
        user = await verify_token_async(token, db)

    if not user:
        logger.warning(f"Unauthorized WebSocket connection attempt: {sid} (Invalid token)")
        return False

    # Persist the authenticated user identity so join_job can enforce ownership.
    # We need user_id (for ownership comparison) and role (admins bypass owner check).
    user_role_value = user.role.value if user.role else "viewer"
    await sio.save_session(sid, {
        "user_id": user.id,
        "username": user.username,
        "role": user_role_value,
    })
    logger.info(f"Client connected and authenticated: {sid} (user={user.username})")


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def join_job(sid, data):
    """Join a job's log-stream room after verifying the user owns the job.

    Admins bypass the ownership check and can subscribe to any job's log
    stream (mirrors REST RBAC). Non-admins can only join their own jobs.
    Legacy jobs with NULL user_id are admin-only (matches the REST behaviour
    in src.server.db.queries.resolve_owned_job).
    """
    job_id = data.get("job_id") if isinstance(data, dict) else data

    if not job_id:
        logger.warning(f"Client {sid} sent join_job without a job_id")
        return

    # Pull the authenticated identity stashed by ``connect``.
    session = await sio.get_session(sid)
    user_id = session.get("user_id") if isinstance(session, dict) else None
    role = session.get("role") if isinstance(session, dict) else None
    if not user_id:
        # Connect handler should have rejected this — defensive 401.
        logger.warning(f"Client {sid} sent join_job without an authenticated session")
        await sio.emit("error", {"message": "Unauthenticated"}, to=sid)
        return

    # Look up the job and check ownership (admin bypass).
    from src.server.db.database import async_session_maker
    from src.server.db.models import Job
    from sqlalchemy import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(Job.id, Job.user_id).where(Job.id == job_id)
        )
        row = result.first()
        if row is None:
            logger.warning(f"Client {sid} tried to join non-existent job room: {job_id}")
            await sio.emit("error", {"message": "Job not found"}, to=sid)
            return
        job_owner_id = row[1]

    if role != "admin":
        # Non-admins can only join their own jobs. Legacy NULL user_id is
        # treated as admin-only — surface as "Job not found" to avoid
        # enumeration of which job ids exist.
        if not job_owner_id or job_owner_id != user_id:
            logger.warning(
                f"Client {sid} (user={user_id}) tried to join job {job_id} "
                f"owned by {job_owner_id}"
            )
            await sio.emit("error", {"message": "Job not found"}, to=sid)
            return

    logger.info(f"Client {sid} joined job {job_id}")
    await sio.enter_room(sid, job_id)
    await sio.emit("log", f"Connected to log stream for {job_id}", room=job_id)

    # Replay any persisted run state to the joining client only, so a page
    # reload mid-run doesn't blank the PipelineRail / progress bar until
    # the next agent transition fires. Mirrors the historical log replay
    # already handled by GET /jobs/{id}.
    try:
        from src.server.services.phase_state import PhaseStateTracker
        phases_snapshot = PhaseStateTracker().snapshot(job_id)
        # snapshot() always returns the default skeleton (all phases queued)
        # even for fresh jobs — only replay when something has actually
        # progressed, otherwise the frontend already shows the same default.
        has_progress = any(
            (p.get("status") not in (None, "queued"))
            or any(s.get("status") not in (None, "queued") for s in p.get("steps", []))
            for p in phases_snapshot
        )
        if has_progress:
            await sio.emit(
                "phase_update",
                {"job_id": job_id, "phases": phases_snapshot},
                to=sid,
            )
    except Exception as e:
        logger.warning(f"phase_update replay failed for {job_id}: {e}")

    try:
        from src.server.services.progress_tracker import ProgressTracker
        progress = ProgressTracker().get_progress_with_timing(job_id)
        if progress and progress.get("progress"):
            await sio.emit("progress", progress, to=sid)
    except Exception as e:
        logger.warning(f"progress replay failed for {job_id}: {e}")


async def notify_job_update(job_id: str, data: dict):
    """Utility to emit updates to a job room."""
    await sio.emit("progress", data, room=job_id)


async def notify_log(job_id: str, message: str):
    """Utility to emit log lines."""
    await sio.emit("log", message, room=job_id)
