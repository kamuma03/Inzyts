"""Audit logging service and middleware.

Provides:
- ``record_audit`` — low-level helper to persist an AuditLog row.
- ``AuditMiddleware`` — Starlette middleware that automatically records
  HTTP requests to security-relevant endpoints.
"""

import json
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.server.db.database import async_session_maker
from src.server.db.models import AuditLog, User
from src.utils.logger import get_logger

logger = get_logger()

# Paths that should be audit-logged automatically by the middleware.
# Covers login, analysis, file ops, user management, and admin actions.
_AUDITED_PREFIXES = (
    "/api/v2/auth/",
    "/api/v2/analyze",
    "/api/v2/files/",
    "/api/v2/jobs/",
    "/api/v2/admin/",
)

# Skip noisy read-only endpoints from auto-logging
_SKIP_METHODS_FOR_PATHS: dict[str, set[str]] = {
    "/api/v2/jobs": {"GET"},
}


def _client_ip(request: Request) -> str:
    """Extract client IP, preferring direct connection over forwarded headers.

    X-Forwarded-For is only trusted when the direct client is a known proxy
    (loopback or Docker-internal ranges). This prevents header spoofing from
    arbitrary clients.
    """
    direct_ip = request.client.host if request.client else None

    # Only trust X-Forwarded-For if the direct client is a known proxy.
    _TRUSTED_PROXIES = ("127.0.0.1", "::1", "172.17.0.1", "172.18.0.1")
    if direct_ip and direct_ip in _TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return direct_ip or "unknown"


def _classify_action(method: str, path: str) -> str:
    """Derive a human-readable action name from method + path."""
    if "/auth/login" in path:
        return "login"
    if "/files/upload" in path:
        return "upload_file"
    if "/analyze" in path:
        return "start_analysis"
    if "/cancel" in path:
        return "cancel_job"
    if "/admin/users" in path:
        if method == "POST":
            return "create_user"
        if method == "PUT" or method == "PATCH":
            return "update_user"
        if method == "DELETE":
            return "delete_user"
        return "list_users"
    if "/admin/audit" in path:
        return "view_audit_logs"
    return f"{method.lower()}_{path.rstrip('/').rsplit('/', 1)[-1]}"


async def record_audit(
    *,
    action: str,
    user: Optional[User] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    status_code: Optional[int] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
) -> None:
    """Persist a single audit log entry.

    Can be called directly from route handlers for fine-grained control,
    or automatically by ``AuditMiddleware``.
    """
    uid = user_id or (user.id if user else None)
    uname = username or (user.username if user else None)

    try:
        async with async_session_maker() as session:
            entry = AuditLog(
                user_id=uid,
                username=uname,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip_address,
                status_code=status_code,
                method=method,
                path=path,
            )
            session.add(entry)
            await session.commit()
    except Exception as exc:
        # Audit logging must never break the request flow
        logger.error(f"Failed to write audit log entry: {exc}")


class AuditMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records audit logs for mutating API calls."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        # Only audit relevant paths
        if not any(path.startswith(p) for p in _AUDITED_PREFIXES):
            return await call_next(request)

        # Skip noisy GETs on certain endpoints
        skip_methods = _SKIP_METHODS_FOR_PATHS.get(path.rstrip("/"), set())
        if method in skip_methods:
            return await call_next(request)

        response = await call_next(request)

        # Fire-and-forget audit write — don't slow down the response
        action = _classify_action(method, path)
        ip = _client_ip(request)

        # Try to extract username from the auth dependency if it was resolved
        username: Optional[str] = None
        user_id: Optional[str] = None
        if hasattr(request.state, "audit_user"):
            user: User = request.state.audit_user
            username = user.username
            user_id = user.id

        try:
            await record_audit(
                action=action,
                user_id=user_id,
                username=username,
                ip_address=ip,
                status_code=response.status_code,
                method=method,
                path=path,
            )
        except Exception as exc:
            logger.error(f"AuditMiddleware: failed to record audit log: {exc}")

        return response
