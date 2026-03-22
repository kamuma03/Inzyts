"""
Configuration settings for the Multi-Agent Data Analysis System.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices
from src.models.handoffs import PipelineMode


class SingleModeSettings(BaseModel):
    """Configuration for a specific pipeline mode."""

    phases: List[str]
    requires_extension: bool
    extension_type: Optional[str] = None
    quality_thresholds: Dict[str, float]


class DatabaseConfig(BaseModel):
    """Database configuration."""

    user: str = Field("postgres", validation_alias="POSTGRES_USER")
    password: str = Field("postgres", validation_alias="POSTGRES_PASSWORD")
    db: str = Field("inzyts", validation_alias="POSTGRES_DB")
    host: str = Field("localhost", validation_alias="POSTGRES_HOST")
    port: str = Field("5432", validation_alias="POSTGRES_PORT")
    max_retries: int = Field(15, validation_alias="DB_MAX_RETRIES")
    retry_interval: int = Field(2, validation_alias="DB_RETRY_INTERVAL")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class JupyterConfig(BaseModel):
    """Jupyter service configuration."""

    model_config = ConfigDict(populate_by_name=True)

    base_url: str = Field("http://jupyter:8888", validation_alias=AliasChoices("base_url", "JUPYTER_BASE_URL"))
    token: Optional[str] = Field(None, validation_alias=AliasChoices("token", "JUPYTER_TOKEN"))


class ModeConfig(BaseModel):
    """Configuration for all pipeline modes."""

    exploratory: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "exploratory_conclusions"],
        requires_extension=False,
        quality_thresholds={"phase1": 0.80, "conclusions": 0.70},
    )
    predictive: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "predictive_phase2"],
        requires_extension=False,
        quality_thresholds={"phase1": 0.80, "phase2": 0.75},
    )
    diagnostic: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "diagnostic_extension", "diagnostic_phase2"],
        requires_extension=True,
        extension_type="diagnostic",
        quality_thresholds={"phase1": 0.80, "phase2": 0.80},
    )
    comparative: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "comparative_extension", "comparative_phase2"],
        requires_extension=True,
        extension_type="comparative",
        quality_thresholds={"phase1": 0.80, "phase2": 0.80},
    )
    forecasting: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "forecasting_extension", "forecasting_phase2"],
        requires_extension=True,
        extension_type="forecasting",
        quality_thresholds={"phase1": 0.80, "phase2": 0.80},
    )
    segmentation: SingleModeSettings = SingleModeSettings(
        phases=["phase1", "segmentation_phase2"],
        requires_extension=False,
        quality_thresholds={"phase1": 0.80, "phase2": 0.80},
    )

    def get(self, mode: PipelineMode) -> SingleModeSettings:
        if not hasattr(self, mode.value):
            raise ValueError(f"Unknown pipeline mode: {mode.value}")
        return getattr(self, mode.value)


class Phase1Config(BaseModel):
    """
    Phase 1 (Data Understanding) configuration.

    Attributes:
        name: Display name for the phase.
        max_iterations: Maximum recursion loops allowed in Phase 1 (Data Profiling).
        quality_threshold: Minimum quality score (0.0-1.0) required to lock the profile.
        timeout_seconds: Hard timeout for the entire Phase 1 execution.
        agents: List of active agents in this phase.
    """

    name: str = "Data Understanding"
    max_iterations: int = 3
    quality_threshold: float = 0.70
    timeout_seconds: int = 300
    agents: List[str] = ["data_profiler", "profile_code_generator", "profile_validator"]


class Phase2Config(BaseModel):
    """
    Phase 2 (Analysis & Modeling) configuration.

    Attributes:
        name: Display name for the phase.
        max_iterations: Maximum recursion loops allowed in Phase 2.
        quality_threshold: Minimum quality score required to complete the analysis.
        timeout_seconds: Hard timeout for Phase 2 execution.
        agents: List of active agents in this phase.
    """

    name: str = "Analysis & Modeling"
    max_iterations: int = 4
    quality_threshold: float = 0.70
    timeout_seconds: int = 600
    agents: List[str] = [
        "strategy_agent",
        "analysis_code_generator",
        "analysis_validator",
    ]


class ExploratoryConclusionsConfig(BaseModel):
    """
    Exploratory Conclusions Agent configuration.
    """

    name: str = "Exploratory Conclusions"
    llm_model: Optional[str] = None  # Inherit from global settings
    max_tokens: int = 8192
    min_confidence: float = 0.5
    min_findings: int = 3
    min_recommendations: int = 2
    quality_threshold: float = 0.70


class CloudConfig(BaseModel):
    """Cloud storage connector configuration."""

    max_download_size_mb: int = 500
    allowed_schemes: List[str] = ["s3", "gs", "az", "abfs", "abfss"]
    download_timeout_seconds: int = 300


class APISourceConfig(BaseModel):
    """REST API data source configuration."""

    max_pages: int = 10
    request_timeout_seconds: int = 30
    max_response_size_mb: int = 100
    require_https: bool = True


class CacheConfig(BaseModel):
    """
    Profile Cache Configuration.
    """

    enabled: bool = True
    cache_dir: str = str(Path.home() / ".inzyts_cache")
    ttl_days: int = 7
    auto_save: bool = True
    auto_cleanup: bool = True


class AgentConfig(BaseModel):
    """
    Agent-specific configuration parameters.

    This class centralizes tunable parameters for each agent to allow easy
    experimentation and optimization without changing code.
    """

    # Orchestrator
    assembly_timeout: int = 60  # Time limit for assembling the final notebook
    max_total_iterations: int = 10  # Safety limit for total graph steps
    escalation_threshold: int = 2  # Number of repeated failures before escalating

    # Data Profiler
    max_rows_to_sample: int = (
        10000  # Sample size for initial profiling to save tokens/time
    )
    outlier_threshold: float = 3.0  # Z-score threshold for outlier detection
    correlation_threshold: float = 0.7  # Threshold for high correlation flagging
    type_detection_confidence_threshold: float = (
        0.7  # Min confidence to accept heuristic type
    )

    # Profile Code Generator
    style_guide: str = "PEP8"
    max_code_length_per_cell: int = 50  # Soft limit for lines of code per cell
    include_type_hints: bool = True
    visualization_types: List[str] = ["hist", "box", "scatter", "heatmap"]

    # Profile Validator
    timeout_per_cell: int = 30  # Execution timeout for a single cell in sandbox
    memory_limit_mb: int = 1024  # RAM limit for sandbox
    min_visualizations: int = 3  # Min required plots for valid profile
    required_report_sections: List[str] = [
        "data_overview",
        "statistics_summary",
        "missing_values",
        "quality_assessment",
    ]

    # Strategy Agent
    default_test_size: float = 0.2
    cv_folds: int = 5
    algorithm_families: List[str] = ["linear", "tree", "ensemble"]
    must_acknowledge_limitations: bool = True

    # Analysis Code Generator
    analysis_max_code_length_per_cell: int = 75
    add_error_handling: bool = True

    # Analysis Validator
    analysis_memory_limit_mb: int = 2048
    min_models: int = 1
    min_result_visualizations: int = 2
    min_conclusion_insights: int = 3

    # Forecasting Agents
    forecasting_min_history_periods: int = 12
    forecasting_default_horizon: int = 6
    forecasting_models: List[str] = ["prophet", "arima", "ets"]

    # Comparative Agents
    comparative_min_group_size: int = 30
    comparative_significance_level: float = 0.05
    comparative_correction_method: str = "bonferroni"

    # Diagnostic Agents
    diagnostic_min_change_magnitude: float = 0.10  # 10% change
    diagnostic_decomposition_model: str = "additive"

    # Segmentation Agents
    segmentation_min_clusters: int = 2
    segmentation_max_clusters: int = 8
    segmentation_algorithm: str = "kmeans"


class RecursionConfig(BaseModel):
    """
    Recursion and rollback configuration.

    Controls the self-correction loops.
    """

    # Phase 1 Recursion
    phase1_max_iterations: int = 3
    phase1_quality_threshold: float = 0.70
    phase1_min_improvement_delta: float = (
        0.05  # Min score increase to justify continuing
    )

    # Phase 2 Recursion
    phase2_max_iterations: int = 4
    phase2_quality_threshold: float = 0.70
    phase2_min_improvement_delta: float = 0.03

    # Global Limits
    max_tokens_per_run: int = 100000  # Cost safety limit
    max_execution_time_seconds: int = 900

    # Escalation
    escalation_threshold_same_issue: int = 2
    escalation_threshold_oscillation: float = 0.02

    # Rollback
    enable_rollback: bool = True  # Allow reverting to previous best state
    rollback_on_degradation: bool = True  # Rollback if quality score drops


class LLMConfig(BaseSettings):
    """
    LLM provider configuration.

    Manages API keys and model selections for different providers.
    Supports environment variable injection via Pydantic using validation_alias.
    """

    # Global Defaults
    default_provider: str = "anthropic"  # Options: ollama, anthropic, openai, gemini
    temperature: float = 0.1  # Low temperature for deterministic code generation
    max_tokens: int = 8192

    # Gemini Configuration
    google_api_key: Optional[str] = Field(None, validation_alias="GOOGLE_API_KEY")
    gemini_model: str = "gemini-1.5-pro"  # Updated to latest stable model

    # Ollama Configuration (Local/Docker)
    # Default to host.docker.internal for Docker, but can be overridden via env var
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:32b"

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(None, validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o"

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("sk-"):
            import logging

            logging.getLogger(__name__).warning(
                "OpenAI API key does not start with 'sk-'."
            )
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("sk-ant-"):
            import logging

            logging.getLogger(__name__).warning(
                "Anthropic API key does not start with 'sk-ant-'."
            )
        return v


class Settings(BaseSettings):
    """Global application settings."""

    # LLM Configuration
    llm: LLMConfig = Field(default_factory=lambda: LLMConfig())  # type: ignore

    # Phase Configurations
    phase1: Phase1Config = Field(default_factory=Phase1Config)
    phase2: Phase2Config = Field(default_factory=Phase2Config)
    exploratory: ExploratoryConclusionsConfig = Field(
        default_factory=ExploratoryConclusionsConfig
    )
    cache: CacheConfig = Field(default_factory=CacheConfig)

    # Agent Configuration
    agent: AgentConfig = Field(default_factory=AgentConfig)

    # Recursion Configuration
    recursion: RecursionConfig = Field(default_factory=RecursionConfig)

    # Cloud & API Source Configuration
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    api_source: APISourceConfig = Field(default_factory=APISourceConfig)

    # Mode Configuration (v1.6.0)
    modes: ModeConfig = Field(default_factory=ModeConfig)

    # Database Configuration
    db: DatabaseConfig = Field(default_factory=lambda: DatabaseConfig())  # type: ignore

    # Jupyter Configuration
    jupyter: JupyterConfig = Field(default_factory=lambda: JupyterConfig())  # type: ignore

    # Output settings
    output_dir: str = "output"
    upload_dir: str = Field("data/uploads", validation_alias="UPLOAD_DIR")
    log_dir: str = Field("logs", validation_alias="LOG_DIR")
    datasets_dir: Optional[str] = Field(None, validation_alias="DATASETS_DIR")

    @property
    def upload_dir_resolved(self) -> Path:
        """Canonical resolved upload directory. Use this instead of re-resolving upload_dir."""
        return Path(self.upload_dir).resolve()

    @property
    def output_dir_resolved(self) -> Path:
        """Canonical resolved output directory."""
        return Path(self.output_dir).resolve()

    @property
    def log_dir_resolved(self) -> Path:
        """Canonical resolved log directory."""
        return Path(self.log_dir).resolve()
    log_level: str = "INFO"

    # Redis
    redis_url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")

    # SQL ingestion
    sql_max_rows: int = Field(200_000, validation_alias="SQL_MAX_ROWS")
    sql_max_cols: int = Field(500, validation_alias="SQL_MAX_COLS")

    # Cloud ingestion
    cloud_max_download_mb: int = Field(500, validation_alias="CLOUD_MAX_DOWNLOAD_MB")

    # Application Metadata
    app_version: str = "v0.10.0"

    @field_validator("app_version", mode="before")
    @classmethod
    def load_version_from_file(cls, v: str) -> str:
        """Load version from VERSION file if it exists."""
        try:
            # Try to find VERSION file in root config directory
            # src/config/__init__.py -> ../../config/VERSION
            current_file = Path(__file__).resolve()
            # Go up two levels to root (src/config/ -> src/ -> root) then into config/
            root_dir = current_file.parent.parent.parent
            version_file = root_dir / "config" / "VERSION"

            if version_file.exists():
                version = version_file.read_text().strip()
                # Ensure it starts with v
                return f"v{version}" if not version.startswith("v") else version
        except Exception:
            pass  # Fallback to default
        return v

    # Security & JWT
    api_token: Optional[str] = Field(None, validation_alias="INZYTS_API_TOKEN") # Fallback for worker/server tasks
    jwt_secret_key: str = Field(..., validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(60 * 4, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")  # 4 hours default
    
    # Admin Defaults (for initialization).
    # ADMIN_PASSWORD is REQUIRED in docker-compose — the "admin" fallback here
    # exists only for local dev outside Docker. Change it before any shared use.
    admin_username: str = Field("admin", validation_alias=AliasChoices("ADMIN_USERNAME", "INZYTS__ADMIN_USERNAME"))
    admin_password: str = Field(..., validation_alias=AliasChoices("ADMIN_PASSWORD", "INZYTS__ADMIN_PASSWORD"))
    # File Search Configuration
    file_search_paths: List[str] = ["~/Documents/Datasets", "./data", "."]

    # CORS Configuration
    allowed_origins: List[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
        ],
        validation_alias="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(
        env_prefix="INZYTS__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()
