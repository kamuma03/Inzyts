from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class JoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    OUTER = "outer"


class JoinStrategy(str, Enum):
    AUTO = "auto"  # System detects and executes joins silently
    SUGGEST = "suggest"  # System suggests, user confirms (future)
    MANUAL = "manual"  # Only use explicit_joins
    NONE = "none"  # Analyze files independently


class FileType(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PARQUET = "parquet"
    LOG = "log"
    UNKNOWN = "unknown"


class JoinSpecification(BaseModel):
    """User-defined join specification."""

    left_file: str  # Alias or filename
    right_file: str
    left_key: str  # Column name
    right_key: str
    join_type: JoinType = JoinType.LEFT


class FileInput(BaseModel):
    """Single file input (generic)."""

    file_path: str
    file_hash: str
    file_type: FileType = FileType.UNKNOWN
    alias: Optional[str] = None  # User-friendly name (e.g., "customers", "orders")
    primary_key_hint: Optional[str] = None  # User hint for PK column


class MultiFileInput(BaseModel):
    """Input specification for multi-file analysis."""

    # File inputs (1-6 files)
    files: List[FileInput]  # min=1, max=6

    # Optional user-defined joins (overrides auto-detection)
    explicit_joins: Optional[List[JoinSpecification]] = None

    # Join behavior
    join_strategy: JoinStrategy = JoinStrategy.AUTO

    # Pydantic v2 config
    model_config = {"json_schema_extra": {"max_files": 6}}


class JoinCandidate(BaseModel):
    """A candidate join relationship."""

    left_file: str
    right_file: str
    left_column: str
    right_column: str

    # Scoring
    name_similarity: float
    type_compatibility: float
    value_overlap: float
    cardinality_ratio: str  # "1:1", "1:N", "N:1", "M:N"
    confidence_score: float

    # Recommendation
    recommended_join_type: JoinType

    def is_auto_executable(self) -> bool:
        return self.confidence_score >= 0.70


class MergedDataset(BaseModel):
    """Result of join execution."""

    merged_df_path: str  # Path to merged CSV/parquet
    merged_hash: str

    # Provenance
    source_files: List[str]
    join_plan_executed: List[JoinCandidate]

    # Statistics
    final_row_count: int
    final_column_count: int
    rows_dropped: int  # Due to inner joins
    rows_added: int  # Due to outer joins

    # Warnings
    warnings: List[str]  # e.g., "Row count increased 5x after join"


class JoinExecutionReport(BaseModel):
    """Detailed report of join detection and execution."""

    # Detection phase
    files_analyzed: int
    candidate_joins_found: int
    candidates: List[JoinCandidate]

    # Execution phase
    joins_executed: int
    joins_skipped: List[JoinCandidate]  # Below threshold or conflicting

    # Result
    merged_dataset: Optional[MergedDataset] = None
    fallback_mode: bool  # True if joins failed, analyzing largest file only
    fallback_reason: Optional[str] = None
