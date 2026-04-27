import asyncio
import datetime
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import Job, JobStatus
from src.server.db.models import User
from src.server.middleware.auth import verify_token
from src.server.models.schemas import (
    AnalysisMode,
    AnalysisRequest,
    AnalysisResponse,
    ModeSuggestionRequest,
    ModeSuggestionResponse,
)
from src.server.rate_limiter import limiter
from src.server.services.cost_estimator import CostEstimator
from src.utils.errors import InzytsError, to_http_exception
from src.utils.logger import get_logger
from src.utils.path_validator import validate_path_within

cost_estimator = CostEstimator()
logger = get_logger()

router = APIRouter(tags=["analysis"])

# Resolve the upload directory once at module load time so it is stable
# regardless of the working directory at request time.
_UPLOAD_DIR = settings.upload_dir_resolved

# AnalysisMode and PipelineMode now share the same string values.
# No mapping layer needed.

_CONFIDENCE_MAP: dict[str, str] = {
    "explicit": "high",
    "target_column": "high",
    "inferred_keyword": "medium",
    "default": "low",
}

_EXPLANATION_MAP: dict[str, str] = {
    "explicit": "Mode was explicitly specified.",
    "target_column": "A target column was provided, suggesting predictive modeling.",
    "inferred_keyword": "Keywords in your question suggest {mode} analysis.",
    "default": "No strong signals detected — defaulting to exploratory analysis.",
}


@router.post("/suggest-mode", response_model=ModeSuggestionResponse)
@limiter.limit("30/minute")
async def suggest_mode(
    request: Request,
    body: ModeSuggestionRequest,
    _token: str = Depends(verify_token),
):
    """Suggest an analysis mode based on the user's question and/or target column."""
    from src.services.mode_detector import ModeDetector

    detector = ModeDetector()
    pipeline_mode, detection_method = detector.determine_mode(
        mode_arg=None,
        target_column=body.target_column,
        user_question=body.question,
    )

    # PipelineMode and AnalysisMode now share the same string values.
    suggested_mode = AnalysisMode(pipeline_mode.value)

    confidence = _CONFIDENCE_MAP.get(detection_method, "low")
    explanation_template = _EXPLANATION_MAP.get(detection_method, "")
    explanation = explanation_template.format(mode=suggested_mode.value)

    return ModeSuggestionResponse(
        suggested_mode=suggested_mode,
        detection_method=detection_method,
        confidence=confidence,
        explanation=explanation,
    )


@router.post("/analyze", response_model=AnalysisResponse)
@limiter.limit("10/minute")
async def analyze(
    request: Request,
    analysis_request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """
    Initiate a new data analysis job.

    This endpoint accepts a CSV file path (or database URI) and analysis
    parameters, estimates the cost, creates a job record in the database,
    and triggers an asynchronous Celery task to execute the analysis pipeline.

    Args:
        request: The raw HTTP request (required by rate limiter).
        analysis_request: The analysis request parameters.
        db: Database session.

    Returns:
        AnalysisResponse: Containing the new Job ID and status.
    """
    # Normalise empty strings to None so downstream checks behave consistently.
    csv_path: str | None = analysis_request.csv_path or None
    db_uri: str | None = analysis_request.db_uri or None
    cloud_uri: str | None = analysis_request.cloud_uri or None
    api_url: str | None = analysis_request.api_url or None

    # Validate that at least one data source is provided
    if not csv_path and not db_uri and not cloud_uri and not api_url:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one data source: csv_path, db_uri, cloud_uri, or api_url",
        )
    # Default cost is 0 for SQL-only jobs where no CSV is available for pre-estimation.
    cost_data = {"estimated_cost_usd": 0.0, "explanation": "Cost calculated after job completes"}

    # --- Path A: db_uri + db_query -> extract CSV immediately (Approach 1) ---
    if db_uri and analysis_request.db_query:
        from src.server.services.data_ingestion import ingest_from_sql
        try:
            csv_path = await asyncio.to_thread(
                ingest_from_sql,
                db_uri,
                analysis_request.db_query,
                str(_UPLOAD_DIR),
            )
        except Exception as e:
            logger.error(f"Database extraction failed: {e}")
            raise HTTPException(status_code=400, detail="Database extraction failed. Check your URI and query.")

    # --- Path A2: cloud_uri -> download and convert to CSV ---
    if cloud_uri and not csv_path:
        from src.server.services.cloud_ingestion import ingest_from_cloud
        try:
            csv_path = await asyncio.to_thread(
                ingest_from_cloud,
                cloud_uri,
                str(_UPLOAD_DIR),
            )
        except Exception as e:
            logger.error(f"Cloud ingestion failed: {e}")
            raise HTTPException(status_code=400, detail=f"Cloud ingestion failed: {type(e).__name__}")

    # --- Path B: db_uri only -> autonomous SQL agent handles extraction in the workflow ---
    # csv_path remains None; the sql_extraction_node in the graph will populate it.

    # --- Path D: api_url -> autonomous API agent handles extraction in the workflow ---
    # csv_path remains None; the api_extraction_node in the graph will populate it.

    # --- Path C: csv_path provided -> validate it ---
    if csv_path:
        allowed_dirs = [_UPLOAD_DIR]
        if settings.datasets_dir:
            allowed_dirs.append(Path(settings.datasets_dir).resolve())

        csv_abs = validate_path_within(
            csv_path,
            allowed_dirs,
            resolve_relative_to=_UPLOAD_DIR,
            reject_symlinks=True,
            must_exist=True,
            error_label="CSV file",
        )
        csv_path = str(csv_abs)

        cost_data = cost_estimator.estimate_job_cost(csv_path, analysis_request.mode)

    # Hash the resolved CSV bytes for opportunistic previous-job matching.
    # Path B (SQL deferred) and Path D (API deferred) leave csv_path = None;
    # the hash is back-filled by the workflow once those paths materialise the CSV.
    from src.server.services.csv_hashing import hash_csv_file
    csv_hash = await asyncio.to_thread(hash_csv_file, csv_path) if csv_path else None

    # 2. Create Job Record
    job_id = str(uuid.uuid4())
    new_job = Job(
        id=job_id,
        user_id=current_user.id,
        status=JobStatus.PENDING,
        mode=analysis_request.mode,
        title=analysis_request.title,
        csv_path=csv_path,
        csv_hash=csv_hash,
        dict_path=analysis_request.dict_path,
        target_column=analysis_request.target_column,
        analysis_type=analysis_request.analysis_type,
        question=analysis_request.question,
        cost_estimate=cost_data,
        token_usage={"input": 0, "output": 0},
    )

    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 3. Trigger Celery Task
    from src.server.services.engine import execution_task

    try:
        execution_task.apply_async(
            kwargs={
                "job_id": job_id,
                "csv_path": csv_path,
                "mode": analysis_request.mode.value,
                "db_uri": db_uri,
                "target": analysis_request.target_column,
                "question": analysis_request.question,
                "title": analysis_request.title,
                "dict_path": analysis_request.dict_path,
                "analysis_type": analysis_request.analysis_type,
                "multi_file_input": analysis_request.multi_file_input,
                "exclude_columns": analysis_request.exclude_columns,
                "use_cache": analysis_request.use_cache,
                "api_url": api_url,
                "api_headers": analysis_request.api_headers,
                "api_auth": analysis_request.api_auth,
                "json_path": analysis_request.json_path,
            },
            task_id=job_id,
        )
    except Exception as e:
        logger.error(f"Failed to queue analysis task: {e}")
        new_job.status = JobStatus.FAILED  # type: ignore
        new_job.error_message = f"Queue error: {str(e)}"  # type: ignore
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to queue analysis task")

    return AnalysisResponse(
        job_id=job_id,
        status="pending",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        estimated_cost=cost_data["estimated_cost_usd"],
        message="Analysis job queued successfully",
    )
