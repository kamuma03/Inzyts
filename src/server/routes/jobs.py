import datetime
import pathlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import Job, JobProgress, JobStatus, User, UserRole
from src.server.models.schemas import (
    ColumnProfileResponse,
    ColumnStats,
    CostBreakdownResponse,
    CostBreakdownRow,
    JobStatusResponse,
    JobSummary,
)
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


_DTYPE_LABEL = {
    "numeric_continuous": "float",
    "numeric_discrete": "int",
    "numeric_identifier": "int",
    "categorical": "category",
    "categorical_text": "category",
    "categorical_nominal": "category",
    "categorical_ordinal": "category",
    "categorical_binary": "bool",
    "binary": "bool",
    "datetime": "datetime",
    "text": "text",
    "identifier": "text",
    "unknown": "text",
}


def _format_cardinality(unique_count: int, dtype_label: str, stats) -> str:
    """Produce a compact 'cardinality_or_range' string for the inspector list."""
    if dtype_label in ("float", "int") and stats is not None:
        lo = getattr(stats, "min", None)
        hi = getattr(stats, "max", None)
        if lo is not None and hi is not None:
            return f"{lo:.0f}–{hi:.0f}"
    if unique_count > 1_000_000:
        return f"{unique_count / 1_000_000:.1f}M unique"
    if unique_count > 1_000:
        return f"{unique_count / 1_000:.1f}K unique"
    if dtype_label in ("category", "bool"):
        return f"{unique_count} levels"
    return f"{unique_count} unique"


def _resolve_role(
    name: str,
    feature_type: str | None,
    target_names: set[str],
    temporal_names: set[str],
) -> str:
    if name in target_names:
        return "target"
    if name in temporal_names:
        return "time"
    if feature_type in ("numeric_continuous", "numeric_discrete"):
        return "metric"
    if feature_type in (
        "categorical_low_cardinality",
        "categorical_high_cardinality",
        "binary",
    ):
        return "dim"
    if feature_type == "datetime":
        return "time"
    return "other"


async def _load_locked_handoff(job: Job):
    """Load the locked Phase-1 handoff for ``job`` from the on-disk profile cache."""
    if not job.csv_hash:
        return None
    try:
        from src.utils.cache_manager import CacheManager

        cache = CacheManager().load_cache(str(job.csv_hash))
        if not cache:
            return None
        return cache.profile_handoff
    except Exception as e:
        logger.warning(f"Failed to load profile cache for job {job.id}: {e}")
        return None


@router.get("/jobs/{job_id}/columns", response_model=list[ColumnProfileResponse])
async def get_job_columns(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Return per-column profile rows for the Command Center inspector."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_role = getattr(current_user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN and job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    handoff = await _load_locked_handoff(job)
    if handoff is None:
        return []

    target_names = {c.column_name for c in (handoff.recommended_target_candidates or ())}
    temporal_names = set(handoff.temporal_columns or ())
    feature_types = handoff.identified_feature_types or {}
    row_count = handoff.row_count or 0

    rows: list[ColumnProfileResponse] = []
    for col in handoff.column_profiles:
        dtype_value = col.detected_type.value if hasattr(col.detected_type, "value") else str(col.detected_type)
        dtype_label = _DTYPE_LABEL.get(dtype_value, "text")
        ft = feature_types.get(col.name)
        ft_value = ft.value if hasattr(ft, "value") else (ft if isinstance(ft, str) else None)
        role = _resolve_role(col.name, ft_value, target_names, temporal_names)
        null_count = int(round((col.null_percentage or 0.0) * row_count))
        stats_obj = col.statistics
        stats_payload = None
        if stats_obj is not None:
            stats_payload = ColumnStats(
                mean=getattr(stats_obj, "mean", None),
                median=getattr(stats_obj, "median", None),
                min=getattr(stats_obj, "min", None),
                max=getattr(stats_obj, "max", None),
                p99=getattr(stats_obj, "p99", None),
            )

        rows.append(
            ColumnProfileResponse(
                name=col.name,
                dtype=dtype_label,
                cardinality_or_range=_format_cardinality(
                    col.unique_count or 0, dtype_label, stats_obj
                ),
                role=role,
                null_count=null_count,
                histogram=[],  # populated by a follow-up; UI degrades gracefully
                stats=stats_payload,
            )
        )

    return rows


@router.get("/jobs/{job_id}/cost", response_model=CostBreakdownResponse)
async def get_job_cost(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Return per-phase cost breakdown for the Command Center cost panel."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_role = getattr(current_user, "role", None) or UserRole.VIEWER
    if user_role != UserRole.ADMIN and job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    breakdown = job.cost_breakdown or []
    rows = [CostBreakdownRow(**row) for row in breakdown if isinstance(row, dict)]

    total = 0.0
    estimate_flag = False
    cost_blob = job.cost_estimate or {}
    if isinstance(cost_blob, dict):
        total = float(cost_blob.get("total") or cost_blob.get("estimated_cost_usd") or 0.0)
        estimate_flag = bool(cost_blob.get("is_estimate") or "estimated" in (cost_blob.get("explanation") or "").lower())

    if not rows and total > 0:
        # Fallback for jobs that ran before per-phase attribution shipped.
        rows = [CostBreakdownRow(
            phase="all",
            label="All phases (legacy job, breakdown unavailable)",
            cost_usd=total,
            is_estimate=True,
        )]
        estimate_flag = True

    return CostBreakdownResponse(total_cost_usd=total, rows=rows, is_estimate=estimate_flag)


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
