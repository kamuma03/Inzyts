"""Reusable database query helpers that span more than one route."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.db.models import Job, JobStatus, User, UserRole


async def resolve_owned_job(
    job_id: str,
    db: AsyncSession,
    user: User,
) -> Job:
    """Fetch a Job by id, enforcing ownership.

    Admins can access any job. Non-admin users can only access jobs they
    created (``job.user_id == user.id``). Legacy jobs with ``user_id IS NULL``
    are admin-only — non-admins see them as 404 to avoid enumeration.

    Returns 404 (not 403) on access denied so an attacker cannot use
    response codes to enumerate which job ids exist.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_role = getattr(user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN:
        # Reject if the job has no owner (legacy) or belongs to someone else.
        if not job.user_id or job.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job not found")

    return job


async def find_previous_job(
    db: AsyncSession,
    *,
    user_id: str,
    mode: str,
    csv_hash: Optional[str],
    exclude_job_id: Optional[str] = None,
) -> Optional[Job]:
    """Return the most recent COMPLETED job for the same (user, mode, csv_hash).

    Returns None if any of the required fields is missing or no match exists.
    Used by the Command Center top strip to surface KPI deltas vs. the prior run.
    """
    if not user_id or not mode or not csv_hash:
        return None

    stmt = (
        select(Job)
        .where(Job.user_id == user_id)
        .where(Job.mode == mode)
        .where(Job.csv_hash == csv_hash)
        .where(Job.status == JobStatus.COMPLETED)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    if exclude_job_id:
        stmt = stmt.where(Job.id != exclude_job_id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()
