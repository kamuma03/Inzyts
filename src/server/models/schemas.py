from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any
from datetime import datetime
from enum import Enum

from src.utils.db_utils import validate_db_uri as _validate_db_uri


class AnalysisMode(str, Enum):
    """Supported analysis modes."""

    EXPLORATORY = "exploratory"
    PREDICTIVE = "predictive"
    FORECASTING = "forecasting"
    COMPARATIVE = "comparative"
    SEGMENTATION = "segmentation"
    DIAGNOSTIC = "diagnostic"
    DIMENSIONALITY_REDUCTION = "dimensionality"


class AnalysisRequest(BaseModel):
    """Schema for analysis initiation request."""

    csv_path: str | None = Field(None, description="Absolute path to the CSV file")
    db_uri: str | None = Field(None, description="Database connection URI")
    db_query: str | None = Field(None, description="SQL query to execute for data extraction")
    cloud_uri: str | None = Field(None, description="Cloud storage URI (s3://, gs://, az://)")
    api_url: str | None = Field(None, description="REST API endpoint URL")
    api_headers: dict[str, str] | None = Field(None, description="Custom HTTP headers for API source")
    api_auth: dict[str, str] | None = Field(None, description="Auth config for API source")
    json_path: str | None = Field(None, description="JMESPath to extract data from API response")
    mode: AnalysisMode = Field(
        default=AnalysisMode.EXPLORATORY, description="Analysis pipeline mode"
    )
    target_column: str | None = Field(
        None, description="Target column for predictive analysis"
    )
    question: str | None = Field(
        None, description="Natural language question for exploratory analysis"
    )
    dict_path: str | None = Field(None, description="Path to data dictionary CSV")
    analysis_type: str | None = Field(
        None, description="Hint for analysis type (e.g., classification)"
    )
    project_id: str | None = None
    use_cache: bool = Field(
        True, description="Whether to use cached profile if available"
    )
    multi_file_input: dict[str, Any] | None = None
    exclude_columns: list[str] | None = Field(
        None, description="List of columns to exclude from analysis"
    )
    title: str | None = Field(None, description="Title of the analysis")

    @field_validator("db_uri")
    @classmethod
    def check_db_uri_scheme(cls, v: str | None) -> str | None:
        if v:
            _validate_db_uri(v)
        return v


class DBTestRequest(BaseModel):
    """Request schema for testing a database connection."""

    db_uri: str = Field(description="SQLAlchemy database connection URI")

    @field_validator("db_uri")
    @classmethod
    def check_db_uri_scheme(cls, v: str) -> str:
        _validate_db_uri(v)
        return v


class DBTestResponse(BaseModel):
    """Response schema for database connection test."""

    status: str
    dialect: str
    host: str | None = None
    tables: list[str] | None = None
    error: str | None = None


class SQLPreviewRequest(BaseModel):
    """Request schema for previewing SQL query results."""

    db_uri: str = Field(description="SQLAlchemy database connection URI")
    query: str = Field(description="SQL SELECT query to preview")

    @field_validator("db_uri")
    @classmethod
    def check_db_uri_scheme(cls, v: str) -> str:
        _validate_db_uri(v)
        return v


class APIPreviewRequest(BaseModel):
    """Request schema for previewing API endpoint data."""

    api_url: str = Field(description="REST API endpoint URL")
    api_headers: dict[str, str] | None = Field(None, description="Custom HTTP headers")
    api_auth: dict[str, str] | None = Field(None, description="Auth config")
    json_path: str | None = Field(None, description="JMESPath to extract data array")


class AnalysisResponse(BaseModel):
    """Response schema for analysis initiation."""

    job_id: str
    status: str
    created_at: datetime
    estimated_cost: float
    message: str


class LogEntry(BaseModel):
    """A single structured log line from a job's log file."""

    timestamp: str
    level: str
    message: str


class JobStatusResponse(BaseModel):
    """Detailed job status schema."""

    job_id: str
    status: str
    progress: int
    message: str
    result_path: str | None = None
    error: str | None = None
    logs: list[LogEntry] = []
    token_usage: dict | None = None
    cost_estimate: dict | None = None
    created_at: datetime


class JobSummary(BaseModel):
    """Summary schema for job listing."""

    id: str
    status: str
    mode: str
    created_at: datetime
    cost_estimate: dict | None = None
    token_usage: dict | None = None
    result_path: str | None = None
    # csv_path is intentionally excluded: exposing server-side filesystem paths to API
    # clients leaks internal layout and aids path enumeration attacks.
    has_data: bool = False
    error_message: str | None = None


class FilePreview(BaseModel):
    """CSV file preview schema."""

    filename: str
    columns: list[str]
    rows: list[dict]
    total_rows: int


class CellEditRequest(BaseModel):
    """Request schema for editing a notebook cell."""

    cell_index: int = Field(description="Index of the cell to edit (0-based)")
    current_code: str = Field(description="Current Python code of the cell")
    instruction: str = Field(description="Natural language edit instruction")


class CellEditResponse(BaseModel):
    """Response schema for cell edit results."""

    new_code: str = Field(description="Modified Python code")
    output: str = Field(default="", description="Execution output (text)")
    images: list[str] = Field(default_factory=list, description="Base64-encoded images from execution")
    success: bool = Field(description="Whether the edit + execution succeeded")
    error: str | None = Field(default=None, description="Error message if failed")


class FollowUpRequest(BaseModel):
    """Request schema for asking a follow-up question about an analysis."""

    question: str = Field(description="Follow-up question about the analysis")


class FollowUpCell(BaseModel):
    """A single cell generated by the follow-up agent."""

    cell_type: str = Field(description="'code' or 'markdown'")
    source: str = Field(description="Cell source content")
    output: str = Field(default="", description="Execution output (text)")
    images: list[str] = Field(default_factory=list, description="Base64-encoded images")


class ConversationMessageSchema(BaseModel):
    """Schema for a single conversation message."""

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="Question text or summary text")
    cells: list[FollowUpCell] | None = Field(
        default=None, description="Generated cells (assistant messages only)"
    )
    created_at: str | None = Field(
        default=None, description="ISO timestamp"
    )


class FollowUpResponse(BaseModel):
    """Response schema for follow-up question results."""

    summary: str = Field(description="Natural language answer to the question")
    cells: list[FollowUpCell] = Field(description="Generated and executed cells")
    success: bool = Field(description="Whether generation + execution succeeded")
    error: str | None = Field(default=None, description="Error message if failed")
    conversation_length: int = Field(
        description="Total number of Q&A exchanges for this job"
    )


class ConversationHistoryResponse(BaseModel):
    """Response schema for loading conversation history."""

    job_id: str
    messages: list[ConversationMessageSchema]


# ---------------------------------------------------------------------------
# Report Export Schemas
# ---------------------------------------------------------------------------


class ReportExportRequest(BaseModel):
    """Request schema for report export with options."""

    format: str = Field(
        default="html",
        description="Export format: html, pdf, pptx, markdown",
    )
    include_executive_summary: bool = Field(
        default=True,
        description="Whether to include LLM-generated executive summary",
    )
    include_pii_masking: bool = Field(
        default=False,
        description="Whether to mask detected PII in the report",
    )


class PIIFindingSchema(BaseModel):
    """A single PII detection finding."""

    pii_type: str
    value: str
    location: str
    severity: str


class PIIScanResponse(BaseModel):
    """Response schema for PII scan results."""

    job_id: str
    has_pii: bool
    findings: list[PIIFindingSchema]
    scanned_cells: int
    scan_duration_ms: float


class ExecutiveSummaryResponse(BaseModel):
    """Response schema for executive summary."""

    job_id: str
    key_findings: list[str]
    data_quality_highlights: list[str]
    recommendations: list[str]
    summary_text: str
    generated_by: str


class ModeSuggestionRequest(BaseModel):
    """Request schema for mode suggestion."""

    question: str | None = Field(None, description="Natural language analysis question")
    target_column: str | None = Field(None, description="Target column name")


class ModeSuggestionResponse(BaseModel):
    """Response schema for mode suggestion."""

    suggested_mode: AnalysisMode
    detection_method: str
    confidence: str  # "high", "medium", "low"
    explanation: str
