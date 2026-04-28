"""
Report export API routes.

Provides endpoints for generating analysis reports in multiple formats
(HTML, PDF, PPTX, Markdown), running PII scans, and generating
executive summaries from completed analysis notebooks.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.server.db.database import get_db
from src.server.db.models import Job, User
from src.server.db.queries import resolve_owned_job
from src.server.middleware.auth import verify_token
from src.server.models.schemas import (
    ExecutiveSummaryResponse,
    PIIFindingSchema,
    PIIScanResponse,
    ReportExportRequest,
)
from src.services.executive_summary import ExecutiveSummaryGenerator
from src.services.pii_detector import PIIDetector
from src.services.report_exporter import ReportExporter, ReportFormat
from src.utils.logger import get_logger
from src.utils.path_validator import validate_path_within

logger = get_logger()

router = APIRouter(prefix="/reports", tags=["reports"])

# Allowed base directory for notebook output files.
# Resolve once at module load so the path is stable regardless of CWD at request time.
_OUTPUT_DIR = settings.output_dir_resolved

# Lazy-initialized singletons
_exporter: ReportExporter | None = None
_summary_gen: ExecutiveSummaryGenerator | None = None


def _get_exporter() -> ReportExporter:
    global _exporter
    if _exporter is None:
        _exporter = ReportExporter()
    return _exporter


def _get_summary_gen() -> ExecutiveSummaryGenerator:
    global _summary_gen
    if _summary_gen is None:
        _summary_gen = ExecutiveSummaryGenerator()
    return _summary_gen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FORMAT_CONTENT_TYPES = {
    ReportFormat.HTML: "text/html",
    ReportFormat.PDF: "application/pdf",
    ReportFormat.PPTX: (
        "application/vnd.openxmlformats-officedocument"
        ".presentationml.presentation"
    ),
    ReportFormat.MARKDOWN: "text/markdown",
}

_FORMAT_EXTENSIONS = {
    ReportFormat.HTML: "html",
    ReportFormat.PDF: "pdf",
    ReportFormat.PPTX: "pptx",
    ReportFormat.MARKDOWN: "md",
}


async def _get_job_notebook(
    job_id: str, db: AsyncSession, user: User
) -> tuple[Job, Path]:
    """Load a job (with ownership check) and validate its notebook exists.

    Validates that the on-disk path lives inside the allowed output directory
    so a tampered DB row cannot make the report exporter read arbitrary files.
    """
    job = await resolve_owned_job(job_id, db, user)
    if not job.result_path:
        raise HTTPException(
            status_code=404, detail="No notebook generated for this job yet"
        )
    # Validate the on-disk path is inside the configured output directory.
    notebook_path = validate_path_within(
        job.result_path,
        [_OUTPUT_DIR],
        must_exist=True,
        error_label="notebook",
    )
    return job, notebook_path


def _build_job_metadata(job: Job) -> dict:
    """Extract job metadata for report generation."""
    from src.config import settings

    model_name = getattr(
        settings.llm, f"{settings.llm.default_provider}_model", "unknown"
    )
    mode = job.mode or "exploratory"
    return {
        "job_id": job.id,
        "mode": mode.replace("_", " ").title(),
        "title": job.title or f"{mode.replace('_', ' ').title()} Analysis",
        "question": job.question,
        "model": model_name,
        "version": settings.app_version,
    }


def _parse_format(fmt: str) -> ReportFormat:
    """Parse and validate the export format string."""
    fmt_lower = fmt.lower().strip()
    try:
        return ReportFormat(fmt_lower)
    except ValueError:
        valid = ", ".join(f.value for f in ReportFormat)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format '{fmt}'. Valid formats: {valid}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{job_id}/export")
async def export_report_get(
    job_id: str,
    format: str = Query(default="html", description="Export format: html, pdf, pptx, markdown"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Generate and download a report in the specified format."""
    report_format = _parse_format(format)
    job, notebook_path = await _get_job_notebook(job_id, db, current_user)
    metadata = _build_job_metadata(job)

    stored_summary = job.executive_summary
    try:
        exporter = _get_exporter()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: exporter.export(
                notebook_path=str(notebook_path),
                job_metadata=metadata,
                format=report_format,
                stored_summary=stored_summary,
            ),
        )
    except RuntimeError as e:
        # WeasyPrint or python-pptx not installed
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Report export failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")

    ext = _FORMAT_EXTENSIONS[report_format]
    content_type = _FORMAT_CONTENT_TYPES[report_format]
    filename = f"inzyts_report_{job_id}.{ext}"

    return FileResponse(
        path=result.file_path,
        media_type=content_type,
        filename=filename,
        headers={
            "X-Report-Has-Summary": str(result.has_executive_summary).lower(),
            "X-Report-Has-PII": str(result.has_pii_warnings).lower(),
        },
    )


@router.post("/{job_id}/export")
async def export_report_post(
    job_id: str,
    request: ReportExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Generate and download a report with custom options."""
    report_format = _parse_format(request.format)
    job, notebook_path = await _get_job_notebook(job_id, db, current_user)
    metadata = _build_job_metadata(job)

    stored_summary = job.executive_summary if request.include_executive_summary else None
    try:
        exporter = _get_exporter()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: exporter.export(
                notebook_path=str(notebook_path),
                job_metadata=metadata,
                format=report_format,
                include_executive_summary=request.include_executive_summary,
                include_pii_masking=request.include_pii_masking,
                stored_summary=stored_summary,
            ),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Report export failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")

    ext = _FORMAT_EXTENSIONS[report_format]
    content_type = _FORMAT_CONTENT_TYPES[report_format]
    filename = f"inzyts_report_{job_id}.{ext}"

    return FileResponse(
        path=result.file_path,
        media_type=content_type,
        filename=filename,
        headers={
            "X-Report-Has-Summary": str(result.has_executive_summary).lower(),
            "X-Report-Has-PII": str(result.has_pii_warnings).lower(),
        },
    )


@router.get("/{job_id}/executive-summary")
async def get_executive_summary(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Return the executive summary for a completed analysis.

    Returns the pre-generated summary stored in the database.
    For jobs created before this feature, generates on-demand and persists
    the result so subsequent requests are free.
    """
    job, notebook_path = await _get_job_notebook(job_id, db, current_user)

    # Return stored summary if available
    if job.executive_summary:
        s = job.executive_summary
        return ExecutiveSummaryResponse(
            job_id=job_id,
            key_findings=s.get("key_findings", []),
            data_quality_highlights=s.get("data_quality_highlights", []),
            recommendations=s.get("recommendations", []),
            summary_text=s.get("summary_text", ""),
            generated_by=s.get("generated_by", "unknown"),
        )

    # Backfill: generate once for old jobs, then persist
    try:
        gen = _get_summary_gen()
        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(
            None, lambda: gen.generate(str(notebook_path))
        )
    except Exception as e:
        logger.error(f"Executive summary failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Executive summary generation failed"
        )

    # Persist so future requests don't regenerate
    job.executive_summary = summary.model_dump()  # type: ignore
    await db.commit()

    return ExecutiveSummaryResponse(
        job_id=job_id,
        key_findings=summary.key_findings,
        data_quality_highlights=summary.data_quality_highlights,
        recommendations=summary.recommendations,
        summary_text=summary.summary_text,
        generated_by=summary.generated_by,
    )


@router.get("/{job_id}/pii-scan")
async def get_pii_scan(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_token),
):
    """Run a PII scan on a completed analysis notebook."""
    job, notebook_path = await _get_job_notebook(job_id, db, current_user)

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: PIIDetector.scan_notebook(str(notebook_path))
        )
    except Exception as e:
        logger.error(f"PII scan failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="PII scan failed")

    return PIIScanResponse(
        job_id=job_id,
        has_pii=result.has_pii,
        findings=[
            PIIFindingSchema(
                pii_type=f.pii_type,
                value=f.value,
                location=f.location,
                severity=f.severity,
            )
            for f in result.findings
        ],
        scanned_cells=result.scanned_cells,
        scan_duration_ms=result.scan_duration_ms,
    )
