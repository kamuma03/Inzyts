"""
Inter-agent handoff schemas for the Multi-Agent Data Analysis System.

Defines all Pydantic models for communication between agents.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict


from .cells import NotebookCell, CellManifest
from .multi_file import MultiFileInput, MergedDataset, JoinExecutionReport
from .tuning import TuningConfig
from .templates import DomainTemplate


# ============================================================================
# Enums and Base Types
# ============================================================================


class AnalysisType(str, Enum):
    """Types of analysis that can be performed."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    TIME_SERIES = "time_series"
    EXPLORATORY = "exploratory"
    ANOMALY_DETECTION = "anomaly_detection"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    DIMENSIONALITY = "dimensionality"


class PipelineMode(str, Enum):
    """Pipeline execution mode."""

    EXPLORATORY = "exploratory"  # Phase 1 + Exploratory Conclusions
    PREDICTIVE = "predictive"  # Phase 1 + Phase 2 (Modeling)
    DIAGNOSTIC = "diagnostic"  # Phase 1 + Extension + Diagnostic Phase 2
    COMPARATIVE = "comparative"  # Phase 1 + Extension + Comparative Phase 2
    FORECASTING = "forecasting"  # Phase 1 + Extension + Forecasting Phase 2
    SEGMENTATION = "segmentation"  # Phase 1 + Segmentation Phase 2
    DIMENSIONALITY = "dimensionality"  # Phase 1 + Phase 2 (PCA)


class CacheStatus(str, Enum):
    """Status of the profile cache."""

    NOT_FOUND = "not_found"
    VALID = "valid"
    EXPIRED = "expired"
    CSV_CHANGED = "csv_changed"


class DataType(str, Enum):
    """Detected data types for columns."""

    NUMERIC_CONTINUOUS = "numeric_continuous"
    NUMERIC_DISCRETE = "numeric_discrete"
    CATEGORICAL = "categorical"
    BINARY = "binary"
    DATETIME = "datetime"
    TEXT = "text"
    IDENTIFIER = "identifier"
    NUMERIC_IDENTIFIER = "numeric_identifier"
    CATEGORICAL_TEXT = "categorical_text"
    CATEGORICAL_NOMINAL = "categorical_nominal"
    CATEGORICAL_ORDINAL = "categorical_ordinal"
    CATEGORICAL_BINARY = "categorical_binary"
    UNKNOWN = "unknown"


class FeatureType(str, Enum):
    """Feature types for analysis."""

    NUMERIC_CONTINUOUS = "numeric_continuous"
    NUMERIC_DISCRETE = "numeric_discrete"
    CATEGORICAL_LOW_CARDINALITY = "categorical_low_cardinality"
    CATEGORICAL_HIGH_CARDINALITY = "categorical_high_cardinality"
    DATETIME = "datetime"
    TEXT = "text"
    BINARY = "binary"
    IDENTIFIER = "identifier"


# ============================================================================
# User Intent (Input to Orchestrator)
# ============================================================================

# Type Definitions
DataDictionaryType = Dict[str, str]


class UserIntent(BaseModel):
    """Captures what the user wants to learn from their data."""

    # Required
    csv_path: str

    # Optional - User-provided hints
    analysis_question: Optional[str] = None
    target_column: Optional[str] = None
    analysis_type_hint: Optional[AnalysisType] = None
    exclude_columns: List[str] = []
    title: Optional[str] = None

    # Metadata
    data_dictionary: Optional[DataDictionaryType] = None

    # Multi-file support (v1.8.0)
    multi_file_input: Optional[MultiFileInput] = None

    # System-inferred (populated by Orchestrator)
    inferred_objective: Optional[str] = None
    confidence_in_inference: float = 0.0

    # Hyperparameter tuning (v1.8.0)
    tuning_config: Optional[TuningConfig] = None
    enable_tuning: bool = True

    # Domain templates (v1.8.0)
    domain_template_id: Optional[str] = None
    auto_detect_domain: bool = True
    template_overrides: Optional[Dict[str, Any]] = None

    # Data dictionary (v1.8.0)
    data_dictionary_path: Optional[str] = None

    # SQL Integration
    db_uri: Optional[str] = None

    # REST API Integration
    api_url: Optional[str] = None
    api_headers: Optional[Dict[str, str]] = None
    api_auth: Optional[Dict[str, str]] = None
    json_path: Optional[str] = None


class ExtendedMetadata(BaseModel):
    """Pre-calculated metadata from Orchestrator."""

    row_count: int
    column_count: int
    column_names: List[str]
    nan_counts: Dict[str, int]
    initial_dtypes: Dict[str, str]
    duplicate_count: int
    unique_counts: Dict[str, int]
    sample_data: Dict[str, List[Any]]  # First 5 rows
    memory_usage_bytes: int


# ============================================================================
# Orchestrator → Data Profiler Handoff
# ============================================================================


class OrchestratorToProfilerHandoff(BaseModel):
    """
    Initial handoff from Orchestrator to start Phase 1.

    Contains the raw inputs needed for the Data Profiler to begin:
    - Path to the data
    - A small preview (head) of the data
    - Basic metadata (row count, columns)
    - The User's captured intent
    """

    csv_path: Optional[str] = None
    csv_preview: Dict[str, Any] = {}  # First 5 rows as dict
    row_count: int
    column_names: List[str]
    user_intent: UserIntent
    iteration: int = 1

    # Multi-file (v1.8.0)
    multi_file_input: Optional[MultiFileInput] = None
    merged_dataset: Optional[MergedDataset] = None  # If joins were executed
    join_report: Optional[JoinExecutionReport] = None

    # Pre-calculated Metadata
    extended_metadata: Optional[ExtendedMetadata] = None

    # Metadata for Profiler (Legacy - creating ExtendedMetadata preferred)
    column_missing_values: Dict[str, int] = {}
    column_initial_types: Dict[str, str] = {}

    # Extended Quality & Structure Metadata
    duplicate_row_count: int = 0
    column_unique_counts: Dict[str, int] = {}
    csv_sample: Dict[str, Any] = {}  # Random sample
    data_dictionary: Dict[str, str] = {}

    @property
    def is_multi_file(self) -> bool:
        return (
            self.multi_file_input is not None and len(self.multi_file_input.files) > 1
        )

    @property
    def effective_csv_path(self) -> str:
        """Returns path to analyze (merged or single)."""
        if self.merged_dataset:
            return self.merged_dataset.merged_df_path
        return self.csv_path or ""


# ============================================================================
# Data Profiler → Profile Code Generator Handoff
# ============================================================================


class ColumnSpec(BaseModel):
    """Specification for a single column."""

    name: str
    detected_type: DataType
    detection_confidence: float
    analysis_approach: str  # e.g., "numeric_continuous", "categorical"
    suggested_visualizations: List[str] = []
    preprocessing_requirement: Optional["ColumnPreprocessingRequirement"] = None


class ColumnPreprocessingRequirement(BaseModel):
    """Explicit data type conversion or cleaning requirement."""

    action: str  # "convert_type", "clean_string", etc.
    target_type: str
    strategy: Optional[str] = None


class PreprocessingRecommendation(BaseModel):
    """Recommendation for preprocessing step."""

    step_type: str  # "imputation", "encoding", "scaling", "conversion"
    columns: List[str]
    method: str
    rationale: Optional[str] = None


class StatisticsRequirement(BaseModel):
    """Requirement for statistics generation."""

    stat_type: str  # "descriptive", "correlation", "distribution"
    target_columns: List[str] = []
    parameters: Dict[str, Any] = {}


class VisualizationRequirement(BaseModel):
    """Requirement for visualization generation."""

    viz_type: str  # "histogram", "boxplot", "heatmap", "scatter"
    target_columns: List[str] = []
    title: str = "Untitled Visualization"
    parameters: Dict[str, Any] = {}


class QualityCheckRequirement(BaseModel):
    """Requirement for data quality checks."""

    check_type: str  # "missing_values", "outliers", "duplicates"
    target_columns: List[str] = []
    threshold: Optional[float] = None


class MarkdownSection(BaseModel):
    """Requirement for markdown section generation."""

    section_type: str  # "title", "data_overview", "quality_summary"
    content_guidance: str


# ============================================================================
# Data Quality Remediation (v1.9.0)
# ============================================================================


class QualityIssueType(str, Enum):
    """Types of data quality issues detected."""

    MISSING_VALUES = "missing_values"
    OUTLIERS_IQR = "outliers_iqr"
    OUTLIERS_ZSCORE = "outliers_zscore"
    DUPLICATE_ROWS = "duplicate_rows"
    DUPLICATE_KEYS = "duplicate_keys"
    TYPE_MISMATCH = "type_mismatch"
    MIXED_TYPES = "mixed_types"
    HIGH_CARDINALITY = "high_cardinality"
    INCONSISTENT_CATEGORIES = "inconsistent_categories"
    RARE_CATEGORIES = "rare_categories"
    INFINITE_VALUES = "infinite_values"
    NEGATIVE_WHERE_POSITIVE = "negative_where_positive"
    LEADING_TRAILING_WHITESPACE = "whitespace_issues"
    EMPTY_STRINGS = "empty_strings"
    ORPHAN_RECORDS = "orphan_records"


class RemediationType(str, Enum):
    """Available remediation strategies."""

    IMPUTE_MEAN = "impute_mean"
    IMPUTE_MEDIAN = "impute_median"
    IMPUTE_MODE = "impute_mode"
    IMPUTE_CONSTANT = "impute_constant"
    IMPUTE_KNN = "impute_knn"
    IMPUTE_FORWARD_FILL = "impute_ffill"
    IMPUTE_BACKWARD_FILL = "impute_bfill"
    DROP_ROWS = "drop_rows"
    DROP_COLUMN = "drop_column"
    CAP_FLOOR_IQR = "cap_floor_iqr"
    CAP_FLOOR_PERCENTILE = "cap_floor_percentile"
    CAP_FLOOR_ZSCORE = "cap_floor_zscore"
    WINSORIZE = "winsorize"
    LOG_TRANSFORM = "log_transform"
    DROP_OUTLIERS = "drop_outliers"
    FLAG_OUTLIERS = "flag_outliers"
    DROP_DUPLICATES_KEEP_FIRST = "drop_dup_first"
    DROP_DUPLICATES_KEEP_LAST = "drop_dup_last"
    DROP_DUPLICATES_KEEP_NONE = "drop_dup_none"
    FLAG_DUPLICATES = "flag_duplicates"
    COERCE_TO_NUMERIC = "coerce_numeric"
    COERCE_TO_DATETIME = "coerce_datetime"
    COERCE_TO_STRING = "coerce_string"
    NORMALIZE_CASE = "normalize_case"
    NORMALIZE_WHITESPACE = "normalize_whitespace"
    GROUP_RARE_CATEGORIES = "group_rare"
    TOP_N_ENCODING = "top_n_encoding"
    NO_REMEDIATION = "no_remediation"


class SafetyRating(str, Enum):
    """Safety ratings for remediation actions."""

    SAFE = "safe"
    REVIEW = "review"
    RISKY = "risky"
    DANGEROUS = "dangerous"


class QualityIssue(BaseModel):
    """A detected data quality issue."""

    issue_id: str
    issue_type: QualityIssueType
    column_name: Optional[str] = None
    severity: str  # "low", "medium", "high", "critical"
    affected_count: int
    affected_percentage: float
    description: str
    examples: List[Any] = []
    detection_method: str
    detection_params: Dict[str, Any] = {}


class RemediationPlan(BaseModel):
    """Plan for remediating a quality issue."""

    issue: QualityIssue
    remediation_type: RemediationType
    remediation_params: Dict[str, Any]
    safety_rating: SafetyRating
    safety_rationale: str
    auto_apply_recommended: bool
    user_approved: Optional[bool] = None
    user_override_type: Optional[RemediationType] = None
    code_snippet: str
    code_explanation: str
    estimated_rows_affected: int
    estimated_data_loss: float


# ============================================================================
# Dimensionality Reduction (v1.9.0)
# ============================================================================


class PCAConfig(BaseModel):
    """Configuration for PCA dimensionality reduction."""

    enabled: bool = True
    feature_count_threshold: int = 20
    correlation_threshold: float = 0.9
    variance_retention_target: float = 0.95
    min_components: int = 2
    max_components: Optional[int] = None
    generate_2d_plot: bool = True
    generate_3d_plot: bool = True
    generate_scree_plot: bool = True
    generate_loadings_heatmap: bool = True
    explain_top_n_components: int = 5
    show_feature_contributions: bool = True
    apply_to_training_only: bool = True
    use_llm_decision: bool = True


class ProfilerToCodeGenHandoff(BaseModel):
    """
    Specification from Data Profiler for Profile Code Generator.

    This is a LOGICAL specification, not code. It tells the Code Generator
    WHAT analysis is required (e.g., "Analyze the distribution of column 'Age'"),
    allowing the Code Generator to decide HOW to implement it (e.g., "Use sns.histplot").
    """

    # Data Overview
    csv_path: str
    row_count: int
    column_count: int

    # Column Specifications
    columns: List[ColumnSpec]

    # Required Analyses
    statistics_requirements: List[StatisticsRequirement] = []
    visualization_requirements: List[VisualizationRequirement] = []
    quality_check_requirements: List[QualityCheckRequirement] = []
    preprocessing_recommendations: List[PreprocessingRecommendation] = []

    # Markdown Sections to Generate
    markdown_sections: List[MarkdownSection] = []

    # Metadata passed through
    detected_domain: Optional[DomainTemplate] = None
    data_dictionary: Dict[str, str] = {}

    # v1.9.0
    remediation_plans: List[RemediationPlan] = []
    pca_config: Optional[PCAConfig] = None


# ============================================================================
# Profile Code Generator → Profile Validator Handoff
# ============================================================================


class ProfileCodeToValidatorHandoff(BaseModel):
    """Output from Profile Code Generator for validation."""

    # Generated Cells
    cells: List[NotebookCell]
    total_cells: int

    # Cell Manifest
    cell_purposes: Dict[int, str]  # index -> purpose

    # Dependencies
    required_imports: List[str]

    # Expected Outputs (for validation)
    expected_statistics: List[str]  # Variable names
    expected_visualizations: int
    expected_markdown_sections: List[str]

    # Profiler Specification (for reference)
    source_specification: ProfilerToCodeGenHandoff


# ============================================================================
# Profile Validator → ProfileToStrategyHandoff (LOCKED)
# ============================================================================


class NumericStats(BaseModel):
    """Statistical summary for numeric columns."""

    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None


class ColumnProfile(BaseModel):
    """Complete profile for a single column."""

    name: str
    detected_type: DataType
    detection_confidence: float
    unique_count: int
    null_percentage: float
    sample_values: List[Any] = []
    statistics: Optional[NumericStats] = None


class TargetCandidate(BaseModel):
    """Candidate column for being the analysis target."""

    column_name: str
    suggested_analysis_type: AnalysisType
    rationale: str
    confidence: float


class ProfileToStrategyHandoff(BaseModel):
    """
    LOCKED output from Phase 1 for Phase 2 consumption.

    This object becomes IMMUTABLE once Profile Lock is granted.
    It serves as the ground truth for the Strategy Agent, containing:
    - Definitive Column Profiles (types, stats)
    - Data Quality Summary
    - Validated Target Candidates
    """

    model_config = ConfigDict(frozen=True)

    # Lock Metadata
    lock_status: str = "locked"
    locked_at: datetime = Field(default_factory=datetime.now)
    phase1_quality_score: float

    # Data Structure (from profiling)
    row_count: int
    column_count: int
    column_profiles: Tuple[ColumnProfile, ...]  # Tuple for immutability

    # Data Quality Summary
    overall_quality_score: float
    missing_value_summary: Dict[str, float]
    data_quality_warnings: Tuple[Any, ...] = ()  # Tuple for immutability

    # Analysis Hints
    recommended_target_candidates: Tuple[
        TargetCandidate, ...
    ] = ()  # Tuple for immutability
    identified_feature_types: Dict[str, FeatureType] = {}
    temporal_columns: Tuple[str, ...] = ()
    high_cardinality_columns: Tuple[str, ...] = ()

    # Relationships
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    detected_patterns: Tuple[str, ...] = ()
    data_dictionary: Dict[str, str] = {}

    # Domain Context (v1.8.0)
    detected_domain: Optional[DomainTemplate] = None

    # Preprocessing Strategy (from Profiler)
    preprocessing_recommendations: Tuple[
        PreprocessingRecommendation, ...
    ] = ()  # Tuple of PreprocessingRecommendation

    # Profile Cells (for notebook assembly)
    profile_cells: Tuple[NotebookCell, ...] = ()  # Tuple of NotebookCell


# ============================================================================
# Strategy Agent → Analysis Code Generator Handoff
# ============================================================================


class PreprocessingStep(BaseModel):
    """Definition of a preprocessing step."""

    step_name: str
    step_type: str  # "imputation", "encoding", "scaling", "feature_eng"
    target_columns: List[str]
    method: str = "standard"
    parameters: Dict[str, Any] = {}
    rationale: str
    order: int


class ModelSpec(BaseModel):
    """Specification for a model to train."""

    model_name: str
    import_path: str
    hyperparameters: Dict[str, Any] = {}
    tuning_config: Optional[TuningConfig] = Field(
        None, description="Configuration for hyperparameter tuning"
    )
    rationale: str
    priority: int


class ValidationStrategy(BaseModel):
    """Strategy for model validation."""

    method: str  # "train_test_split", "cross_validation", "time_series_split"
    parameters: Dict[str, Any] = {}


class ResultVisualization(BaseModel):
    """Specification for a result visualization."""

    viz_type: str  # "confusion_matrix", "roc_curve", "feature_importance"
    title: str
    when_applicable: str = "always"  # Condition for generating this viz


class StrategyToCodeGenHandoff(BaseModel):
    """
    Analysis plan from Strategy Agent for Analysis Code Generator.

    Describes the Machine Learning pipeline to be implemented:
    - Preprocessing steps (imputation, encoding)
    - Models to be trained (algorithms, hyperparameters)
    - Evaluation metrics to use
    """

    # Source Profile (reference only, cannot modify)
    profile_reference: str  # ID of locked profile

    # Analysis Plan
    analysis_type: AnalysisType
    analysis_objective: str
    target_column: Optional[str] = None
    feature_columns: List[str] = []

    # Preprocessing Pipeline
    preprocessing_steps: List[PreprocessingStep] = []

    # Model Specifications
    models_to_train: List[ModelSpec] = []

    # Evaluation Strategy
    evaluation_metrics: List[str] = []
    validation_strategy: Optional[ValidationStrategy] = None

    # Visualization Requirements
    result_visualizations: List[ResultVisualization] = []

    # Conclusions Guidance
    conclusion_points: List[str] = []

    # Profile Limitations Acknowledged
    profile_limitations: List[str] = []


# ============================================================================
# Analysis Code Generator → Analysis Validator Handoff
# ============================================================================


class AnalysisCodeToValidatorHandoff(BaseModel):
    """Output from Analysis Code Generator for validation."""

    # Generated Cells
    cells: List[NotebookCell]
    total_cells: int

    # Cell Manifest
    cell_manifest: List[CellManifest]

    # Dependencies
    required_imports: List[str]
    pip_dependencies: List[str] = []

    # Expected Outputs
    expected_models: List[str]  # Model variable names
    expected_metrics: List[str]  # Metric variable names
    expected_visualizations: int

    # Source Strategy (for reference)
    source_strategy: StrategyToCodeGenHandoff


# ============================================================================
# Final Assembly Handoff (to Orchestrator)
# ============================================================================


class FinalAssemblyHandoff(BaseModel):
    """Combined outputs for Orchestrator to assemble final notebook."""

    # Phase 1 Outputs
    profile_cells: List[NotebookCell]
    phase1_quality_score: float

    # Phase 2 Outputs
    analysis_cells: List[NotebookCell]
    phase2_quality_score: float

    # Exploratory Outputs
    exploratory_cells: List[NotebookCell] = []

    # Assembly Instructions
    notebook_title: str
    introduction_content: str
    conclusion_content: str

    # Metadata
    total_execution_time: float
    total_iterations: int
    total_tokens_used: int


# ============================================================================
# Exploratory Conclusions Agent Handoffs
# ============================================================================


class ProfileToExploratoryConclusionsHandoff(BaseModel):
    """Handoff from Profile Validator to Exploratory Conclusions Agent."""

    # Locked profile
    profile_handoff: ProfileToStrategyHandoff
    profile_cells: List[NotebookCell]
    phase1_quality_score: float

    # User context
    user_question: str
    user_intent: UserIntent

    # Data context
    csv_path: str
    row_count: int
    column_count: int


class ExploratoryConclusionsOutput(BaseModel):
    """Output from Exploratory Conclusions Agent."""

    # User's question (echoed)
    original_question: str

    # LLM-generated content
    direct_answer: str
    key_findings: List[str]
    statistical_insights: List[str]
    data_quality_notes: List[str]
    recommendations: List[str]

    # Generated cells
    conclusions_cells: List[NotebookCell]

    # Optional additional visualizations
    visualization_cells: List[NotebookCell] = []

    # Confidence
    confidence_score: float
    limitations: List[str]


class ExploratoryConclusionsToAssemblyHandoff(BaseModel):
    """Handoff from Exploratory Conclusions to Orchestrator for assembly."""

    # Conclusions content
    conclusions_cells: List[NotebookCell]
    visualization_cells: List[NotebookCell]

    # Metadata
    direct_answer_summary: str
    key_findings_count: int
    confidence_score: float
    limitations: List[str]


# ============================================================================
# Profile Cache Model
# ============================================================================


class ProfileCache(BaseModel):
    """Cached Phase 1 outputs for upgrade path."""

    # Identity
    cache_id: str  # SHA256 of CSV content
    csv_path: str  # Original path (for display)
    csv_hash: str  # SHA256 for integrity check
    csv_size_bytes: int  # Quick integrity check
    csv_row_count: int  # For display
    csv_column_count: int  # For display

    # Timestamps
    created_at: datetime
    expires_at: datetime  # created_at + 7 days

    # Cached outputs
    # We use Any/Dict here to avoid circular imports with state.py if possible
    # But ideally validation.py uses ProfileLock.
    # For simplicity, we store the DICT representation or import dynamically if needed.
    # However, since handoffs.py does not strictly depend on state.py at module level
    # (except for what we intro now), we should be careful.
    # The Requirements asked for ProfileLock object.
    # We will use Dict/Any for the lock to store the serialized JSON content.
    profile_lock: Dict[str, Any]
    profile_cells: List[NotebookCell]
    profile_handoff: ProfileToStrategyHandoff

    # Metadata
    pipeline_mode: PipelineMode  # EXPLORATORY when cached
    phase1_quality_score: float
    user_intent: Optional[UserIntent]

    # Version info
    agent_version: str

    def is_expired(self) -> bool:
        """Check if cache has expired."""
        from datetime import timezone

        expires = self.expires_at
        # Handle both naive and aware datetimes
        if expires.tzinfo is None:
            return datetime.now() > expires
        return datetime.now(timezone.utc) > expires

    def is_valid_for_csv(self, current_csv_hash: str) -> bool:
        """Check if CSV matches cached version."""
        return self.csv_hash == current_csv_hash

    def days_until_expiry(self) -> int:
        """Days remaining until cache expires."""
        from datetime import timezone

        expires = self.expires_at
        if expires.tzinfo is None:
            delta = expires - datetime.now()
        else:
            delta = expires - datetime.now(timezone.utc)
        return max(0, delta.days)


# ============================================================================
# Extensions (v1.6.0)
# ============================================================================


class GapAnalysis(BaseModel):
    """Analysis of time series gaps."""

    has_gaps: bool
    gap_count: int
    largest_gap_periods: int
    gap_locations: List[str]


class ForecastingExtension(BaseModel):
    """Extension data for forecasting mode."""

    # Datetime analysis
    datetime_column: str
    datetime_format: str
    frequency: str  # "D", "W", "M", "Q", "Y"
    frequency_confidence: float

    # Time series characteristics
    date_range: Tuple[datetime, datetime]
    total_periods: int
    missing_periods: List[datetime]
    gap_analysis: GapAnalysis

    # Stationarity hints
    stationarity_hint: str  # "likely_stationary", "likely_non_stationary", "unknown"
    trend_detected: bool
    seasonality_detected: bool
    seasonality_period: Optional[int] = None

    # Recommendations
    recommended_models: List[str]  # ["prophet", "arima", "ets"]
    preprocessing_needed: List[str]

    # Cache metadata
    created_at: datetime
    csv_hash: str


class RecommendedTest(BaseModel):
    metric: str
    test_type: str  # "t_test", "chi_square", "mann_whitney"
    rationale: str


class ComparativeExtension(BaseModel):
    """Extension data for comparative mode."""

    # Group identification
    group_column: str
    group_values: List[str]
    baseline_group: str
    treatment_groups: List[str]

    # Sample analysis
    group_sizes: Dict[str, int]
    balance_ratio: float  # Smallest / Largest group
    is_balanced: bool

    # Metric candidates
    numeric_metrics: List[str]
    categorical_metrics: List[str]
    recommended_primary_metric: str

    # Test recommendations
    recommended_tests: List[RecommendedTest]
    multiple_comparison_correction: str  # "bonferroni", "holm", "fdr"

    # Cache metadata
    created_at: datetime
    csv_hash: str


class AnalysisPeriods(BaseModel):
    before_start: datetime
    before_end: datetime
    after_start: datetime
    after_end: datetime


class ChangePoint(BaseModel):
    timestamp: datetime
    metric: str
    magnitude: float
    direction: str  # "increase", "decrease"


class Anomaly(BaseModel):
    timestamp: datetime
    metric: str
    severity: float
    description: str


class DiagnosticExtension(BaseModel):
    """Extension data for diagnostic mode."""

    # Temporal analysis
    has_temporal_data: bool
    temporal_column: Optional[str] = None
    analysis_periods: Optional[AnalysisPeriods] = None

    # Metric identification
    metric_columns: List[str]
    primary_metric: str
    metric_direction: str  # "higher_is_better", "lower_is_better"

    # Dimension identification
    dimension_columns: List[str]

    # Change detection
    change_points_detected: List[ChangePoint]
    anomalies_detected: List[Anomaly]

    # Recommendations
    recommended_analysis: List[str]  # ["trend_decomposition", "segment_analysis", etc.]

    # Cache metadata
    created_at: datetime
    csv_hash: str


# ============================================================================
# Phase 2 Strategies (v1.6.0)
# ============================================================================


class Hypothesis(BaseModel):
    description: str
    dimension: Optional[str] = None
    expected_contribution: str  # "high", "medium", "low"
    test_approach: str


class AnalysisStep(BaseModel):
    step_name: str
    step_type: str  # "decomposition", "trend", "correlation", "anomaly"
    parameters: Dict[str, Any]
    output_variables: List[str]


class TimePeriodComparison(BaseModel):
    period1_label: str
    period2_label: str
    period1_range: Tuple[datetime, datetime]
    period2_range: Tuple[datetime, datetime]


class RootCauseStrategy(BaseModel):
    """Strategy for diagnostic analysis."""

    # Problem framing
    metric_of_interest: str
    direction_of_change: str  # "increase", "decrease"
    magnitude_estimate: Optional[float] = None

    # Analysis plan
    decomposition_dimensions: List[str]
    time_comparison: Optional[TimePeriodComparison] = None

    # Hypotheses
    hypotheses: List[Hypothesis]

    # Code generation instructions
    analysis_steps: List[AnalysisStep]
    visualization_requirements: List[str]


# ============================================================================
# Data Quality Remediation (v1.9.0)
# ============================================================================


class DimensionalityStrategyHandoff(BaseModel):
    """Strategy for dimensionality reduction (PCA)."""

    # Profile Reference
    profile_reference: str

    # PCA Configuration
    config: PCAConfig

    # Analysis Decisions
    target_variance: float
    n_components_estimate: Optional[int] = None
    features_to_reduce: List[str]
    target_column: Optional[str] = None

    # Interpretation
    interpretation_focus: str  # "visualization", "feature_reduction"

    # Visualization Requirements
    visualizations: List[str]
