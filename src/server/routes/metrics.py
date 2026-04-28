from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import User
from src.server.db.queries import resolve_owned_job
from src.server.middleware.auth import verify_token
from src.utils.logger import get_logger
from src.utils.path_validator import validate_path_within

logger = get_logger()

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Bind allowed dirs at module load so tests can patch them as plain
# attributes (the Pydantic Settings object is immutable, so direct
# attribute patching on `settings.upload_dir_resolved` is rejected).
_UPLOAD_DIR = settings.upload_dir_resolved
_DATASETS_DIR = (
    Path(settings.datasets_dir).resolve() if settings.datasets_dir else None
)


@router.get("/{job_id}")
async def get_job_metrics(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """
    Compute lightweight statistics for the job's dataset on-demand.
    Returns schema, missing values, and descriptive stats.

    Owner-or-admin only. Validates that ``job.csv_path`` resolves inside the
    configured upload / datasets directory so a tampered DB row cannot make
    the metrics service read arbitrary host files.
    """
    job = await resolve_owned_job(job_id, db, current_user)

    if not job.csv_path:
        raise HTTPException(
            status_code=404, detail="No CSV file associated with this job"
        )

    allowed_dirs = [_UPLOAD_DIR]
    if _DATASETS_DIR is not None:
        allowed_dirs.append(_DATASETS_DIR)

    try:
        csv_path = validate_path_within(
            job.csv_path,
            allowed_dirs,
            must_exist=True,
            error_label="CSV file",
        )
    except HTTPException:
        # Surface a generic 404 instead of leaking which directory was rejected.
        raise HTTPException(status_code=404, detail="CSV file not found")

    try:
        from src.server.services.metrics_service import metrics_service

        return metrics_service.get_job_metrics(job_id, csv_path)

    except Exception as e:
        logger.error(f"Error computing metrics for job {job_id}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to compute metrics"
        )
