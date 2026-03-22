"""Admin-only API routes for user management and audit log queries.

All endpoints require ``UserRole.ADMIN``.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.db.database import get_db
from src.server.db.models import User, UserRole, AuditLog
from src.server.middleware.auth import require_role, get_password_hash, verify_password
from src.server.middleware.audit import record_audit
from src.utils.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/admin", tags=["Admin"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = None
    role: str = Field(default="viewer", pattern="^(admin|analyst|viewer)$")


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|analyst|viewer)$")
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: Optional[datetime] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    status_code: Optional[int] = None
    method: Optional[str] = None
    path: Optional[str] = None


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(
        select(User).order_by(User.created_at).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role.value if u.role else "viewer",
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    # Check uniqueness
    existing = await db.execute(select(User).filter(User.username == body.username))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Username already exists")

    new_user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role=UserRole(body.role),
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    await record_audit(
        action="create_user",
        user=admin,
        resource_type="user",
        resource_id=new_user.id,
        detail=f"Created user '{body.username}' with role '{body.role}'",
    )

    return UserOut(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role.value,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes: list[str] = []
    if body.role is not None:
        user.role = UserRole(body.role)
        changes.append(f"role→{body.role}")
    if body.email is not None:
        user.email = body.email
        changes.append("email updated")
    if body.is_active is not None:
        user.is_active = body.is_active
        changes.append(f"is_active→{body.is_active}")
    if body.password is not None:
        user.hashed_password = get_password_hash(body.password)
        changes.append("password changed")

    await db.commit()
    await db.refresh(user)

    await record_audit(
        action="update_user",
        user=admin,
        resource_type="user",
        resource_id=user_id,
        detail=f"Updated user '{user.username}': {', '.join(changes)}",
    )

    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting yourself
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    username = user.username
    await db.delete(user)
    await db.commit()

    await record_audit(
        action="delete_user",
        user=admin,
        resource_type="user",
        resource_id=user_id,
        detail=f"Deleted user '{username}'",
    )


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=list[AuditLogOut])
async def query_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    username: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    q = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if username:
        q = q.filter(AuditLog.username == username)
    if action:
        q = q.filter(AuditLog.action == action)
    if since:
        q = q.filter(AuditLog.timestamp >= since)
    if until:
        q = q.filter(AuditLog.timestamp <= until)

    q = q.offset(skip).limit(limit)

    result = await db.execute(q)
    logs = result.scalars().all()
    return [AuditLogOut.model_validate(log) for log in logs]


@router.get("/audit-logs/summary")
async def audit_logs_summary(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Return counts of audit log entries grouped by action."""
    result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(desc(func.count(AuditLog.id)))
    )
    rows = result.all()
    return {"actions": {action: count for action, count in rows}}
