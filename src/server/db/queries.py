"""Reusable database query helpers that span more than one route."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.db.models import Job, JobStatus


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
