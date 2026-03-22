import datetime
import pathlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import Job, JobProgress, JobStatus, User, UserRole
from src.server.models.schemas import JobStatusResponse, JobSummary
from src.server.middleware.auth import verify_token
from src.server.rate_limiter import limiter
from src.utils.logger import get_logger
from src.utils.path_validator import validate_path_within

logger = get_logger()
router = APIRouter(tags=["jobs"])

# Resolve once at module load so it is consistent with the engine.py log path.
_LOG_BASE = settings.log_dir_resolved

# Maximum log lines returned per request — prevents loading multi-MB files.
_MAX_LOG_LINES = 500


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """
    Retrieve a paginated list of recent analysis jobs.

    Admins see all jobs. Non-admin users see only their own jobs.
    """
    query = select(Job).order_by(Job.created_at.desc())

    # Non-admin users can only see their own jobs
    user_role = getattr(current_user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN:
        query = query.filter(Job.user_id == current_user.id)

    result = await db.execute(query.offset(skip).limit(limit))
    jobs = result.scalars().all()
    return [
        JobSummary(
            id=job.id,  # type: ignore
            status=job.status.value if hasattr(job.status, "value") else job.status,  # type: ignore
            mode=job.mode.value if hasattr(job.mode, "value") else job.mode,  # type: ignore
            created_at=job.created_at,  # type: ignore
            cost_estimate=job.cost_estimate,  # type: ignore
            token_usage=job.token_usage,  # type: ignore
            result_path=job.result_path,  # type: ignore
            error_message=job.error_message,  # type: ignore
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_job_status(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """
    Get the detailed status of a specific job.

    Admins can view any job. Non-admin users can only view their own jobs.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Ownership check: non-admins can only see their own jobs
    user_role = getattr(current_user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN and job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    logs = []
    if job.logs_location:
        try:
            try:
                log_path = validate_path_within(
                    job.logs_location,
                    [_LOG_BASE],
                    must_exist=False,
                    error_label="log file",
                )
            except HTTPException:
                logger.warning(
                    f"Security: Job {job_id} attempted to access log outside allowed directory"
                )
                logs.append(
                    {
                        "timestamp": "",
                        "level": "WARN",
                        "message": "Security: Access denied to log file.",
                    }
                )
                log_path = None

            if log_path and log_path.exists() and log_path.is_file():
                last_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                with open(log_path, "r", encoding="utf-8") as f:
                    # Cap at _MAX_LOG_LINES to prevent loading multi-MB files into memory.
                    lines = f.readlines()[-_MAX_LOG_LINES:]
                    for line in lines:
                        parts = line.strip().split(" | ", 2)
                        if len(parts) == 3:
                            ts_raw = parts[0].strip()
                            # Normalise python timestamp (e.g. 2026-02-24 13:51:36,123) for JS date parsing
                            ts_iso = ts_raw.replace(",", ".").replace(" ", "T")
                            if "T" in ts_iso and "Z" not in ts_iso and "+" not in ts_iso:
                                ts_iso += "Z"  # Assuming UTC per Celery settings
                            last_timestamp = ts_iso
                            logs.append(
                                {
                                    "timestamp": ts_iso,
                                    "level": parts[1].strip(),
                                    "message": parts[2],
                                }
                            )
                        else:
                            logs.append(
                                {
                                    "timestamp": last_timestamp,
                                    "level": "INFO",
                                    "message": line.strip(),
                                }
                            )
        except Exception as e:
            logger.error(f"Error reading logs for {job_id}: {e}")

    # Dynamic progress: query JobProgress table for the latest entry
    progress = 0
    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        progress = 100
    elif job.status == JobStatus.RUNNING:
        progress_result = await db.execute(
            select(JobProgress.progress)
            .where(JobProgress.job_id == job_id)
            .order_by(JobProgress.timestamp.desc())
            .limit(1)
        )
        latest_progress = progress_result.scalar_one_or_none()
        progress = latest_progress if latest_progress is not None else 10

    return JobStatusResponse(
        job_id=job.id,  # type: ignore
        status=job.status.value if hasattr(job.status, "value") else job.status,  # type: ignore
        progress=progress,
        message=f"Job is {job.status.value if hasattr(job.status, 'value') else job.status}",
        result_path=job.result_path,  # type: ignore
        error=job.error_message,  # type: ignore
        logs=logs,
        token_usage=job.token_usage,  # type: ignore
        cost_estimate=job.cost_estimate,  # type: ignore
        created_at=job.created_at,  # type: ignore
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(verify_token)
):
    """
    Cancel a running analysis job.

    Admins can cancel any job. Non-admin users can only cancel their own jobs.
    """
    # 1. Verify job exists and user has access
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Ownership check
    user_role = getattr(current_user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN and job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    # 2. Revoke in Celery
    # On Windows, terminate=True (which sends SIGTERM) is not supported.
    # Fall back to revoke without termination — the task will stop at the
    # next Celery heartbeat check rather than being killed immediately.
    import sys
    from src.server.celery_app import celery_app

    celery_app.control.revoke(job_id, terminate=(sys.platform != "win32"))

    # 3. Update DB
    if job:
        job.status = JobStatus.CANCELLED  # type: ignore
        await db.commit()

    return {"status": "cancelled"}
