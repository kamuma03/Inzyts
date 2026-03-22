from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from src.server.db.database import get_db
from src.server.db.models import Job
from src.server.middleware.auth import verify_token
from src.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/{job_id}")
async def get_job_metrics(
    job_id: str, db: AsyncSession = Depends(get_db), _token: str = Depends(verify_token)
):
    """
    Compute lightweight statistics for the job's dataset on-demand.
    Returns schema, missing values, and descriptive stats.
    """
    # 1. Get Job
    result = await db.execute(select(Job).filter(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.csv_path:
        raise HTTPException(
            status_code=404, detail="No CSV file associated with this job"
        )

    csv_path = Path(job.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV file not found at {csv_path}")

    try:
        from src.server.services.metrics_service import metrics_service

        return metrics_service.get_job_metrics(job_id, csv_path)

    except Exception as e:
        logger.error(f"Error computing metrics for job {job_id}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to compute metrics: {str(e)}"
        )
