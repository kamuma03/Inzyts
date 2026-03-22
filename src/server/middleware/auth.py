import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR
from jose import JWTError, jwt
import bcrypt

from src.config import settings
from src.utils.logger import get_logger
from src.server.db.database import get_db
from src.server.db.models import User, UserRole

logger = get_logger()
security = HTTPBearer(auto_error=False)

# Role hierarchy: admin > analyst > viewer
ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.VIEWER: 0,
    UserRole.ANALYST: 1,
    UserRole.ADMIN: 2,
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.warning(f"Password verification error ({type(e).__name__}): {e}")
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def check_system_token(token: str) -> Optional[User]:
    expected_token = settings.api_token
    if expected_token and secrets.compare_digest(token, expected_token):
        logger.debug("System API Token authenticated.")
        return User(id="system", username="system", is_active=True, role=UserRole.ADMIN)
    return None

def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None

async def verify_token_async(token: str, db: AsyncSession) -> Optional[User]:
    sys_user = check_system_token(token)
    if sys_user:
        return sys_user

    username = decode_token(token)
    if not username:
        return None

    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    if user is None or not user.is_active:
        return None
    return user

def verify_token_sync(token: str, db: Optional[Session] = None) -> Optional[User]:
    """
    Synchronously verifies validity of the JWT token string.
    If valid, returns the User object, else None.

    When ``db`` is None the function can only authenticate system API tokens.
    It will NOT return a User from a JWT without a DB lookup — that would bypass
    deactivated-account and deletion checks.  Pass a Session for full JWT validation.
    """
    sys_user = check_system_token(token)
    if sys_user:
        return sys_user

    username = decode_token(token)
    if not username:
        return None

    if db:
        user = db.query(User).filter(User.username == username).first()
        if user is None or not user.is_active:
            return None
        return user

    # No DB session — cannot verify user existence/active status; reject.
    logger.warning(
        "verify_token_sync called without a DB session for a JWT token; "
        "cannot verify user status — rejecting."
    )
    return None

async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Auth failed: No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user = await verify_token_async(token, db)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Stash authenticated user on request.state for the audit middleware
    request.state.audit_user = user

    return user


def require_role(*allowed_roles: UserRole):
    """FastAPI dependency factory that enforces role-based access.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...

    The dependency first authenticates the user via ``verify_token``, then
    checks that the user's role is among *allowed_roles*.  Uses role hierarchy
    so that ``require_role(UserRole.ANALYST)`` also admits admins.
    """

    async def _check_role(
        user: User = Depends(verify_token),
    ) -> User:
        user_role = getattr(user, "role", None) or UserRole.VIEWER
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        min_level = min(ROLE_HIERARCHY.get(r, 0) for r in allowed_roles)
        if user_level < min_level:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(r.value for r in allowed_roles)}",
            )
        return user

    return _check_role
