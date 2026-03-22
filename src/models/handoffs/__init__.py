"""
Handoffs Package - Inter-agent communication schemas.

All models can still be imported from `src.models.handoffs` as before.
"""

# Re-export everything from the original handoffs module
from src.models._handoffs import (
    # Enums
    AnalysisType,
    PipelineMode,
    CacheStatus,
    DataType,
    FeatureType,
    QualityIssueType,
    RemediationType,
    SafetyRating,
    # User Intent
    UserIntent,
    ExtendedMetadata,
    # Orchestrator handoffs
    OrchestratorToProfilerHandoff,
    # Profiler handoffs
    ColumnSpec,
    ColumnPreprocessingRequirement,
    PreprocessingRecommendation,
    StatisticsRequirement,
    VisualizationRequirement,
    QualityCheckRequirement,
    MarkdownSection,
    ProfilerToCodeGenHandoff,
    # Quality handoffs
    QualityIssue,
    RemediationPlan,
    PCAConfig,
    # Code Gen handoffs
    ProfileCodeToValidatorHandoff,
    # Column profiles
    NumericStats,
    ColumnProfile,
    TargetCandidate,
    # Strategy handoffs
    ProfileToStrategyHandoff,
    PreprocessingStep,
    ModelSpec,
    ValidationStrategy,
    ResultVisualization,
    StrategyToCodeGenHandoff,
    # Analysis handoffs
    AnalysisCodeToValidatorHandoff,
    FinalAssemblyHandoff,
    # Conclusions
    ProfileToExploratoryConclusionsHandoff,
    ExploratoryConclusionsOutput,
    ExploratoryConclusionsToAssemblyHandoff,
    # Cache
    ProfileCache,
    # Extensions - Forecasting
    GapAnalysis,
    ForecastingExtension,
    # Extensions - Comparative
    RecommendedTest,
    ComparativeExtension,
    # Extensions - Diagnostic
    AnalysisPeriods,
    ChangePoint,
    Anomaly,
    DiagnosticExtension,
    Hypothesis,
    AnalysisStep,
    TimePeriodComparison,
    RootCauseStrategy,
    # Dimensionality
    DimensionalityStrategyHandoff,
)

# Re-export from cells module for convenience
from src.models.cells import NotebookCell, CellManifest

# Backward compatibility aliases
FeatureSpec = ModelSpec  # Some code may use FeatureSpec

__all__ = [
    "AnalysisType",
    "PipelineMode",
    "CacheStatus",
    "DataType",
    "FeatureType",
    "QualityIssueType",
    "RemediationType",
    "SafetyRating",
    "UserIntent",
    "ExtendedMetadata",
    "OrchestratorToProfilerHandoff",
    "ColumnSpec",
    "ColumnPreprocessingRequirement",
    "PreprocessingRecommendation",
    "StatisticsRequirement",
    "VisualizationRequirement",
    "QualityCheckRequirement",
    "MarkdownSection",
    "ProfilerToCodeGenHandoff",
    "QualityIssue",
    "RemediationPlan",
    "PCAConfig",
    "ProfileCodeToValidatorHandoff",
    "NumericStats",
    "ColumnProfile",
    "TargetCandidate",
    "ProfileToStrategyHandoff",
    "PreprocessingStep",
    "ModelSpec",
    "FeatureSpec",
    "ValidationStrategy",
    "ResultVisualization",
    "StrategyToCodeGenHandoff",
    "AnalysisCodeToValidatorHandoff",
    "FinalAssemblyHandoff",
    "ProfileToExploratoryConclusionsHandoff",
    "ExploratoryConclusionsOutput",
    "ExploratoryConclusionsToAssemblyHandoff",
    "ProfileCache",
    "GapAnalysis",
    "ForecastingExtension",
    "RecommendedTest",
    "ComparativeExtension",
    "AnalysisPeriods",
    "ChangePoint",
    "Anomaly",
    "DiagnosticExtension",
    "Hypothesis",
    "AnalysisStep",
    "TimePeriodComparison",
    "RootCauseStrategy",
    "DimensionalityStrategyHandoff",
    "NotebookCell",
    "CellManifest",
]
