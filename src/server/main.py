"""
FastAPI Application Entry Point.

This module configures and initializes the main FastAPI application for the
backend service. It handles:
1. Application Lifecycle (startup/shutdown events).
2. Database Connection Checks (in lifespan).
3. Global Middleware (CORS, Rate Limiting).
4. Route Registration (API v2).
5. Socket.IO Integration.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.server.db.database import engine
from src.server.rate_limiter import limiter
from src.utils.logger import get_logger
from src.config import settings

from src.server.routes import (
    admin,
    analysis,
    jobs,
    websockets,
    files,
    notebooks,
    metrics,
    templates,
    auth,
    reports,
)
from src.server.middleware.audit import AuditMiddleware
import socketio  # type: ignore

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Inzyts v2...")

    # Wait for DB connection
    import asyncio
    from sqlalchemy import text
    from src.config import settings

    # Log connection details (mask password using URL parsing for safety)
    from urllib.parse import urlparse, urlunparse
    _parsed = urlparse(str(settings.db.url))
    _masked = _parsed._replace(netloc=f"{_parsed.username}:******@{_parsed.hostname}:{_parsed.port}")
    masked_url = urlunparse(_masked)
    logger.warning(f"Attempting to connect to database at: {masked_url}")

    try:
        loop = asyncio.get_running_loop()
        addr_info = await loop.getaddrinfo(settings.db.host, None)
        db_ip = addr_info[0][4][0]
        logger.warning(f"Resolved database host '{settings.db.host}' to IP: {db_ip}")
    except Exception as e:
        logger.error(f"Failed to resolve database host '{settings.db.host}': {e}")

    max_retries = settings.db.max_retries
    retry_interval = settings.db.retry_interval

    for i in range(max_retries):
        try:
            # Use engine.begin() for a direct connection check
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            
            # Make sure tables are created (dev step only usually handled by alembic)
            from src.server.db.database import Base
            # This handles first time runs quickly
            # Base.metadata.create_all(bind=engine.sync_engine) - skipped for async 
            
            break
        except Exception as e:
            if i == max_retries - 1:
                logger.error(
                    f"Failed to connect to database after {max_retries} attempts: {e}"
                )
                raise e
            logger.warning(
                f"Database connection failed, retrying in {retry_interval}s... ({i + 1}/{max_retries}) Error: {e}"
            )
            await asyncio.sleep(retry_interval)

    yield
    # Shutdown
    logger.info("Shutting down Inzyts...")
    await engine.dispose()


app = FastAPI(
    title="Inzyts API",
    version="2.0",
    description="Analyze. Predict. Discover. API",
    lifespan=lifespan,
)

# Register rate limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

ALLOWED_ORIGINS = settings.allowed_origins

# Add CORS middleware to support frontend in Docker and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS", "PUT"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

fastapi_app = app

# Audit logging middleware (runs inside CORS)
app.add_middleware(AuditMiddleware)

app.include_router(auth.router, prefix="/api/v2")
app.include_router(admin.router, prefix="/api/v2")
app.include_router(analysis.router, prefix="/api/v2")
app.include_router(jobs.router, prefix="/api/v2")
app.include_router(files.router, prefix="/api/v2")
app.include_router(notebooks.router, prefix="/api/v2")
app.include_router(metrics.router, prefix="/api/v2")
app.include_router(templates.router, prefix="/api/v2")
app.include_router(reports.router, prefix="/api/v2")

# Wrap FastAPI with Socket.IO
# This handles /socket.io requests and passes everything else to FastAPI
app = socketio.ASGIApp(websockets.sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    import os

    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("src.server.main:app", host=host, port=8000, reload=True)
