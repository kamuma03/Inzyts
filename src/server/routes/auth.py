from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import uuid

from src.server.db.database import get_db
from src.server.db.models import User, UserRole
from src.server.middleware.auth import verify_password, create_access_token, get_password_hash, verify_token
from src.server.middleware.audit import record_audit
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger()
router = APIRouter(tags=["Authentication"])

@router.post("/auth/login")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()

    # On first boot with no users, auto-create the default admin account.
    # Race condition safety: if two requests race here, the UNIQUE constraint on
    # username ensures only one INSERT succeeds. The loser catches IntegrityError,
    # rolls back, and re-fetches the winner's row.
    if not user and form_data.username == settings.admin_username:
        count_result = await db.execute(select(func.count(User.id)))
        user_count = count_result.scalar()
        if user_count == 0:
            logger.info("No users exist. Creating default admin user.")
            new_user = User(
                id=str(uuid.uuid4()),
                username=settings.admin_username,
                hashed_password=get_password_hash(settings.admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(new_user)
            try:
                await db.commit()
                await db.refresh(new_user)
                user = new_user
            except IntegrityError:
                await db.rollback()
                result = await db.execute(
                    select(User).filter(User.username == settings.admin_username)
                )
                user = result.scalars().first()

    # Always run a password comparison to prevent timing-based user enumeration.
    # When the user doesn't exist we compare against a dummy hash so the response
    # time is indistinguishable from a wrong-password attempt.
    _DUMMY_HASH = "$2b$12$LJ3m4ys3Lg2Uu.qYtMS6fOKeAVgNjuEFgB3M2HqLhBNyB0noxyUi"
    password_ok = verify_password(
        form_data.password,
        user.hashed_password if user else _DUMMY_HASH,
    )
    if not user or not password_ok:
        # Audit failed login attempt
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        await record_audit(
            action="login_failed",
            username=form_data.username,
            ip_address=ip,
            detail=f"Failed login attempt for '{form_data.username}'",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_role = user.role.value if user.role else "viewer"

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "role": user_role},
        expires_delta=access_token_expires,
    )

    # Audit successful login
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    await record_audit(
        action="login",
        user=user,
        ip_address=ip,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user_role,
        "username": user.username,
    }


@router.get("/auth/me")
async def get_current_user(user: User = Depends(verify_token)):
    """Return the current authenticated user's profile."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if user.role else "viewer",
        "is_active": user.is_active,
    }
