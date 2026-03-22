"""
Unit tests for handoff models.

Tests all inter-agent communication handoff models including validations,
serialization, field constraints, and enum values.

Coverage includes:
- All handoff model validations
- Serialization roundtrips
- Field constraints
- Enum values
- Pydantic model behavior
"""

import pytest
from datetime import datetime, timedelta

from src.models.handoffs import (
    # Enums
    AnalysisType,
    PipelineMode,
    CacheStatus,
    DataType,
    FeatureType,
    # User Intent
    UserIntent,
    # Phase 1 Handoffs
    OrchestratorToProfilerHandoff,
    ColumnSpec,
    ColumnPreprocessingRequirement,
    PreprocessingRecommendation,
    StatisticsRequirement,
    VisualizationRequirement,
    QualityCheckRequirement,
    ProfilerToCodeGenHandoff,
    ProfileCodeToValidatorHandoff,
    NumericStats,
    ColumnProfile,
    TargetCandidate,
    ProfileToStrategyHandoff,
    # Phase 2 Handoffs
    PreprocessingStep,
    ModelSpec,
    ValidationStrategy,
    StrategyToCodeGenHandoff,
    AnalysisCodeToValidatorHandoff,
    # Assembly
    FinalAssemblyHandoff,
    # Exploratory
    ProfileToExploratoryConclusionsHandoff,
    ExploratoryConclusionsOutput,
    ProfileCache,
    # Extensions
    GapAnalysis,
    ForecastingExtension,
    RecommendedTest,
    ComparativeExtension,
    AnalysisPeriods,
    ChangePoint,
    DiagnosticExtension,
    Hypothesis,
    AnalysisStep,
    TimePeriodComparison,
    RootCauseStrategy,
)
from src.models.cells import NotebookCell, CellManifest


class TestEnums:
    """Test all enumeration types."""

    def test_analysis_type_enum(self):
        """Test AnalysisType enum values."""
        assert AnalysisType.CLASSIFICATION == "classification"
        assert AnalysisType.REGRESSION == "regression"
        assert AnalysisType.CLUSTERING == "clustering"
        assert AnalysisType.TIME_SERIES == "time_series"
        assert AnalysisType.EXPLORATORY == "exploratory"
        assert AnalysisType.ANOMALY_DETECTION == "anomaly_detection"
        assert AnalysisType.CAUSAL == "causal"
        assert AnalysisType.COMPARATIVE == "comparative"

    def test_pipeline_mode_enum(self):
        """Test PipelineMode enum values."""
        assert PipelineMode.EXPLORATORY == "exploratory"
        assert PipelineMode.PREDICTIVE == "predictive"
        assert PipelineMode.DIAGNOSTIC == "diagnostic"
        assert PipelineMode.COMPARATIVE == "comparative"
        assert PipelineMode.FORECASTING == "forecasting"
        assert PipelineMode.SEGMENTATION == "segmentation"

    def test_cache_status_enum(self):
        """Test CacheStatus enum values."""
        assert CacheStatus.NOT_FOUND == "not_found"
        assert CacheStatus.VALID == "valid"
        assert CacheStatus.EXPIRED == "expired"
        assert CacheStatus.CSV_CHANGED == "csv_changed"

    def test_data_type_enum(self):
        """Test DataType enum values."""
        assert DataType.NUMERIC_CONTINUOUS == "numeric_continuous"
        assert DataType.NUMERIC_DISCRETE == "numeric_discrete"
        assert DataType.CATEGORICAL == "categorical"
        assert DataType.BINARY == "binary"
        assert DataType.DATETIME == "datetime"
        assert DataType.TEXT == "text"
        assert DataType.IDENTIFIER == "identifier"
        assert DataType.UNKNOWN == "unknown"

    def test_feature_type_enum(self):
        """Test FeatureType enum values."""
        assert FeatureType.NUMERIC_CONTINUOUS == "numeric_continuous"
        assert FeatureType.CATEGORICAL_LOW_CARDINALITY == "categorical_low_cardinality"
        assert FeatureType.CATEGORICAL_HIGH_CARDINALITY == "categorical_high_cardinality"
        assert FeatureType.DATETIME == "datetime"
        assert FeatureType.BINARY == "binary"


class TestUserIntent:
    """Test UserIntent model."""

    def test_user_intent_minimal(self):
        """Test UserIntent with minimal fields."""
        intent = UserIntent(csv_path="/data/test.csv")

        assert intent.csv_path == "/data/test.csv"
        assert intent.analysis_question is None
        assert intent.target_column is None
        assert intent.analysis_type_hint is None
        assert intent.exclude_columns == []
        assert intent.confidence_in_inference == 0.0

    def test_user_intent_full(self):
        """Test UserIntent with all fields."""
        intent = UserIntent(
            csv_path="/data/test.csv",
            analysis_question="What factors affect sales?",
            target_column="sales",
            analysis_type_hint=AnalysisType.REGRESSION,
            exclude_columns=["id", "timestamp"],
            data_dictionary={"sales": "Monthly sales in USD"},
            inferred_objective="Predict sales based on features",
            confidence_in_inference=0.85
        )

        assert intent.csv_path == "/data/test.csv"
        assert intent.analysis_question == "What factors affect sales?"
        assert intent.target_column == "sales"
        assert intent.analysis_type_hint == AnalysisType.REGRESSION
        assert len(intent.exclude_columns) == 2
        assert intent.confidence_in_inference == 0.85

    def test_user_intent_serialization(self):
        """Test UserIntent JSON serialization."""
        intent = UserIntent(
            csv_path="/data/test.csv",
            target_column="target"
        )

        if hasattr(intent, 'model_dump_json'):
            json_str = intent.model_dump_json()
        else:
            json_str = intent.json()

        assert "/data/test.csv" in json_str
        assert "target" in json_str


class TestOrchestratorToProfilerHandoff:
    """Test OrchestratorToProfilerHandoff model."""

    def test_orchestrator_to_profiler_basic(self):
        """Test basic handoff creation."""
        user_intent = UserIntent(csv_path="/data/test.csv")

        handoff = OrchestratorToProfilerHandoff(
            csv_path="/data/test.csv",
            csv_preview={"col1": [1, 2, 3], "col2": ["a", "b", "c"]},
            row_count=1000,
            column_names=["col1", "col2"],
            user_intent=user_intent
        )

        assert handoff.csv_path == "/data/test.csv"
        assert handoff.row_count == 1000
        assert len(handoff.column_names) == 2
        assert handoff.iteration == 1

    def test_orchestrator_to_profiler_with_metadata(self):
        """Test handoff with extended metadata."""
        user_intent = UserIntent(csv_path="/data/test.csv")

        handoff = OrchestratorToProfilerHandoff(
            csv_path="/data/test.csv",
            csv_preview={},
            row_count=5000,
            column_names=["age", "income", "category"],
            user_intent=user_intent,
            column_missing_values={"age": 10, "income": 5},
            column_initial_types={"age": "int64", "income": "float64"},
            duplicate_row_count=15,
            column_unique_counts={"age": 50, "category": 5}
        )

        assert handoff.duplicate_row_count == 15
        assert handoff.column_missing_values["age"] == 10
        assert handoff.column_unique_counts["category"] == 5


class TestColumnSpec:
    """Test ColumnSpec model."""

    def test_column_spec_basic(self):
        """Test basic column specification."""
        spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical analysis"
        )

        assert spec.name == "age"
        assert spec.detected_type == DataType.NUMERIC_CONTINUOUS
        assert spec.detection_confidence == 0.95
        assert spec.suggested_visualizations == []

    def test_column_spec_with_visualizations(self):
        """Test column spec with suggested visualizations."""
        spec = ColumnSpec(
            name="category",
            detected_type=DataType.CATEGORICAL,
            detection_confidence=0.90,
            analysis_approach="Frequency analysis",
            suggested_visualizations=["bar_chart", "pie_chart"]
        )

        assert len(spec.suggested_visualizations) == 2
        assert "bar_chart" in spec.suggested_visualizations

    def test_column_spec_with_preprocessing(self):
        """Test column spec with preprocessing requirement."""
        preproc = ColumnPreprocessingRequirement(
            action="convert_type",
            target_type="float",
            strategy="remove_currency_symbol"
        )

        spec = ColumnSpec(
            name="price",
            detected_type=DataType.TEXT,
            detection_confidence=0.85,
            analysis_approach="Convert to numeric",
            preprocessing_requirement=preproc
        )

        assert spec.preprocessing_requirement is not None
        assert spec.preprocessing_requirement.action == "convert_type"


class TestProfilerToCodeGenHandoff:
    """Test ProfilerToCodeGenHandoff model."""

    def test_profiler_to_codegen_basic(self):
        """Test basic profiler to codegen handoff."""
        col_spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        handoff = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=3,
            columns=[col_spec]
        )

        assert handoff.csv_path == "/data/test.csv"
        assert handoff.row_count == 1000
        assert len(handoff.columns) == 1
        assert handoff.statistics_requirements == []

    def test_profiler_to_codegen_with_requirements(self):
        """Test handoff with all requirement types."""
        col_spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        stat_req = StatisticsRequirement(
            stat_type="descriptive",
            target_columns=["age"]
        )

        viz_req = VisualizationRequirement(
            viz_type="histogram",
            target_columns=["age"],
            title="Age Distribution"
        )

        quality_req = QualityCheckRequirement(
            check_type="missing_values",
            target_columns=["age"]
        )

        handoff = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=1,
            columns=[col_spec],
            statistics_requirements=[stat_req],
            visualization_requirements=[viz_req],
            quality_check_requirements=[quality_req]
        )

        assert len(handoff.statistics_requirements) == 1
        assert len(handoff.visualization_requirements) == 1
        assert len(handoff.quality_check_requirements) == 1


class TestProfileCodeToValidatorHandoff:
    """Test ProfileCodeToValidatorHandoff model."""

    def test_profile_code_to_validator_basic(self):
        """Test basic profile code to validator handoff."""
        cells = [
            NotebookCell(cell_type="markdown", source="# Report"),
            NotebookCell(cell_type="code", source="import pandas as pd")
        ]

        col_spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        source_spec = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=1,
            columns=[col_spec]
        )

        handoff = ProfileCodeToValidatorHandoff(
            cells=cells,
            total_cells=2,
            cell_purposes={0: "Title", 1: "Imports"},
            required_imports=["pandas"],
            expected_statistics=[],
            expected_visualizations=0,
            expected_markdown_sections=["Report"],
            source_specification=source_spec
        )

        assert handoff.total_cells == 2
        assert len(handoff.cells) == 2
        assert "pandas" in handoff.required_imports


class TestNumericStatsAndColumnProfile:
    """Test NumericStats and ColumnProfile models."""

    def test_numeric_stats_complete(self):
        """Test NumericStats with all fields."""
        stats = NumericStats(
            mean=50.0,
            median=48.0,
            std=15.0,
            min=10.0,
            max=100.0,
            q25=35.0,
            q75=65.0
        )

        assert stats.mean == 50.0
        assert stats.median == 48.0
        assert stats.std == 15.0
        assert stats.q25 == 35.0

    def test_numeric_stats_partial(self):
        """Test NumericStats with partial fields."""
        stats = NumericStats(
            mean=50.0,
            median=48.0
        )

        assert stats.mean == 50.0
        assert stats.std is None
        assert stats.min is None

    def test_column_profile_with_stats(self):
        """Test ColumnProfile with numeric statistics."""
        stats = NumericStats(mean=50.0, median=48.0, std=15.0)

        profile = ColumnProfile(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=50,
            null_percentage=0.05,
            sample_values=[25, 30, 35, 40, 45],
            statistics=stats
        )

        assert profile.name == "age"
        assert profile.statistics.mean == 50.0
        assert len(profile.sample_values) == 5

    def test_column_profile_without_stats(self):
        """Test ColumnProfile for categorical column."""
        profile = ColumnProfile(
            name="category",
            detected_type=DataType.CATEGORICAL,
            detection_confidence=0.90,
            unique_count=5,
            null_percentage=0.0,
            sample_values=["A", "B", "C"]
        )

        assert profile.statistics is None
        assert profile.detected_type == DataType.CATEGORICAL


class TestProfileToStrategyHandoff:
    """Test ProfileToStrategyHandoff (locked handoff)."""

    def test_profile_to_strategy_basic(self):
        """Test basic locked handoff creation."""
        col_profile = ColumnProfile(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=50,
            null_percentage=0.0
        )

        handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.85,
            row_count=1000,
            column_count=1,
            column_profiles=(col_profile,),  # Tuple for immutability
            overall_quality_score=0.85,
            missing_value_summary={"age": 0.0}
        )

        assert handoff.phase1_quality_score == 0.85
        assert handoff.row_count == 1000
        assert isinstance(handoff.column_profiles, tuple)
        assert handoff.lock_status == "locked"

    def test_profile_to_strategy_immutability(self):
        """Test that ProfileToStrategyHandoff is frozen."""
        col_profile = ColumnProfile(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=50,
            null_percentage=0.0
        )

        handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.85,
            row_count=1000,
            column_count=1,
            column_profiles=(col_profile,),
            overall_quality_score=0.85,
            missing_value_summary={}
        )

        # Should not be able to modify frozen model
        with pytest.raises((ValueError, AttributeError)):
            handoff.row_count = 2000

    def test_profile_to_strategy_with_recommendations(self):
        """Test handoff with target candidates and recommendations."""
        col_profile = ColumnProfile(
            name="target",
            detected_type=DataType.CATEGORICAL,
            detection_confidence=0.90,
            unique_count=2,
            null_percentage=0.0
        )

        target_candidate = TargetCandidate(
            column_name="target",
            suggested_analysis_type=AnalysisType.CLASSIFICATION,
            rationale="Binary target with balanced classes",
            confidence=0.85
        )

        preproc = PreprocessingRecommendation(
            step_type="encoding",
            columns=["category"],
            method="onehot",
            rationale="Low cardinality categorical"
        )

        handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.90,
            row_count=1000,
            column_count=2,
            column_profiles=(col_profile,),
            overall_quality_score=0.90,
            missing_value_summary={},
            recommended_target_candidates=(target_candidate,),
            preprocessing_recommendations=(preproc,)
        )

        assert len(handoff.recommended_target_candidates) == 1
        assert len(handoff.preprocessing_recommendations) == 1


class TestStrategyToCodeGenHandoff:
    """Test StrategyToCodeGenHandoff model."""

    def test_strategy_to_codegen_basic(self):
        """Test basic strategy handoff."""
        handoff = StrategyToCodeGenHandoff(
            profile_reference="profile_123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Predict customer churn",
            target_column="churn",
            feature_columns=["age", "income", "tenure"]
        )

        assert handoff.analysis_type == AnalysisType.CLASSIFICATION
        assert handoff.target_column == "churn"
        assert len(handoff.feature_columns) == 3

    def test_strategy_to_codegen_with_pipeline(self):
        """Test handoff with preprocessing and models."""
        preproc_step = PreprocessingStep(
            step_name="Impute Missing Values",
            step_type="imputation",
            target_columns=["age", "income"],
            method="median",
            parameters={"strategy": "median"},
            rationale="Handle missing numeric values",
            order=1
        )

        model_spec = ModelSpec(
            model_name="RandomForest",
            import_path="sklearn.ensemble.RandomForestClassifier",
            hyperparameters={"n_estimators": 100, "max_depth": 10},
            rationale="Good for tabular data",
            priority=1
        )

        validation = ValidationStrategy(
            method="cross_validation",
            parameters={"cv": 5}
        )

        handoff = StrategyToCodeGenHandoff(
            profile_reference="profile_123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Predict churn",
            target_column="churn",
            feature_columns=["age", "income"],
            preprocessing_steps=[preproc_step],
            models_to_train=[model_spec],
            evaluation_metrics=["accuracy", "f1_score"],
            validation_strategy=validation
        )

        assert len(handoff.preprocessing_steps) == 1
        assert len(handoff.models_to_train) == 1
        assert "accuracy" in handoff.evaluation_metrics


class TestAnalysisCodeToValidatorHandoff:
    """Test AnalysisCodeToValidatorHandoff model."""

    def test_analysis_code_to_validator(self):
        """Test analysis code to validator handoff."""
        cells = [
            NotebookCell(cell_type="code", source="# Preprocessing"),
            NotebookCell(cell_type="code", source="# Model training")
        ]

        manifest = [
            CellManifest(
                index=0,
                cell_type="code",
                purpose="Preprocessing",
                outputs_variables=["X_train", "X_test"]
            ),
            CellManifest(
                index=1,
                cell_type="code",
                purpose="Model training",
                outputs_variables=["model"]
            )
        ]

        strategy = StrategyToCodeGenHandoff(
            profile_reference="profile_123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test",
            feature_columns=[]
        )

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=2,
            cell_manifest=manifest,
            required_imports=["sklearn", "pandas"],
            expected_models=["model"],
            expected_metrics=["accuracy"],
            expected_visualizations=1,
            source_strategy=strategy
        )

        assert handoff.total_cells == 2
        assert len(handoff.cell_manifest) == 2
        assert "sklearn" in handoff.required_imports


class TestFinalAssemblyHandoff:
    """Test FinalAssemblyHandoff model."""

    def test_final_assembly_handoff(self):
        """Test final assembly handoff."""
        profile_cells = [NotebookCell(cell_type="markdown", source="# Profile")]
        analysis_cells = [NotebookCell(cell_type="code", source="# Analysis")]

        handoff = FinalAssemblyHandoff(
            profile_cells=profile_cells,
            phase1_quality_score=0.90,
            analysis_cells=analysis_cells,
            phase2_quality_score=0.85,
            notebook_title="Analysis Report",
            introduction_content="This is the introduction",
            conclusion_content="These are the conclusions",
            total_execution_time=120.5,
            total_iterations=5,
            total_tokens_used=10000
        )

        assert len(handoff.profile_cells) == 1
        assert len(handoff.analysis_cells) == 1
        assert handoff.total_execution_time == 120.5
        assert handoff.total_tokens_used == 10000


class TestExploratoryConclusionsHandoffs:
    """Test exploratory conclusions handoff models."""

    def test_profile_to_exploratory_conclusions(self):
        """Test ProfileToExploratoryConclusionsHandoff."""
        col_profile = ColumnProfile(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=50,
            null_percentage=0.0
        )

        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.85,
            row_count=1000,
            column_count=1,
            column_profiles=(col_profile,),
            overall_quality_score=0.85,
            missing_value_summary={}
        )

        user_intent = UserIntent(
            csv_path="/data/test.csv",
            analysis_question="What are the key patterns?"
        )

        handoff = ProfileToExploratoryConclusionsHandoff(
            profile_handoff=profile_handoff,
            profile_cells=[],
            phase1_quality_score=0.85,
            user_question="What are the key patterns?",
            user_intent=user_intent,
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=1
        )

        assert handoff.phase1_quality_score == 0.85
        assert handoff.user_question == "What are the key patterns?"

    def test_exploratory_conclusions_output(self):
        """Test ExploratoryConclusionsOutput."""
        output = ExploratoryConclusionsOutput(
            original_question="What patterns exist?",
            direct_answer="The data shows three main patterns...",
            key_findings=["Pattern 1", "Pattern 2"],
            statistical_insights=["Mean is 50", "Std is 15"],
            data_quality_notes=["No missing values"],
            recommendations=["Consider normalization"],
            conclusions_cells=[],
            confidence_score=0.85,
            limitations=["Limited sample size"]
        )

        assert output.original_question == "What patterns exist?"
        assert len(output.key_findings) == 2
        assert output.confidence_score == 0.85


class TestProfileCache:
    """Test ProfileCache model."""

    def test_profile_cache_creation(self):
        """Test creating a profile cache."""
        col_profile = ColumnProfile(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=50,
            null_percentage=0.0
        )

        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.85,
            row_count=1000,
            column_count=1,
            column_profiles=(col_profile,),
            overall_quality_score=0.85,
            missing_value_summary={}
        )

        now = datetime.now()
        cache = ProfileCache(
            cache_id="cache_123",
            csv_path="/data/test.csv",
            csv_hash="abc123",
            csv_size_bytes=1024000,
            csv_row_count=1000,
            csv_column_count=5,
            created_at=now,
            expires_at=now + timedelta(days=7),
            profile_lock={},
            profile_cells=[],
            profile_handoff=profile_handoff,
            pipeline_mode=PipelineMode.EXPLORATORY,
            phase1_quality_score=0.85,
            user_intent=None,
            agent_version="1.5.0"
        )

        assert cache.cache_id == "cache_123"
        assert cache.csv_row_count == 1000
        assert cache.agent_version == "1.5.0"

    def test_profile_cache_is_expired(self):
        """Test cache expiration check."""
        now = datetime.now()

        # Expired cache
        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.8,
            row_count=100,
            column_count=5,
            column_profiles=(),
            overall_quality_score=0.8,
            missing_value_summary={}
        )

        expired_cache = ProfileCache(
            cache_id="cache_1",
            csv_path="/data/test.csv",
            csv_hash="abc",
            csv_size_bytes=1000,
            csv_row_count=100,
            csv_column_count=5,
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
            profile_lock={},
            profile_cells=[],
            profile_handoff=profile_handoff,
            pipeline_mode=PipelineMode.EXPLORATORY,
            phase1_quality_score=0.8,
            user_intent=None,
            agent_version="1.5.0"
        )

        assert expired_cache.is_expired() is True

    def test_profile_cache_not_expired(self):
        """Test cache not expired."""
        now = datetime.now()

        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.8,
            row_count=100,
            column_count=5,
            column_profiles=(),
            overall_quality_score=0.8,
            missing_value_summary={}
        )

        valid_cache = ProfileCache(
            cache_id="cache_2",
            csv_path="/data/test.csv",
            csv_hash="abc",
            csv_size_bytes=1000,
            csv_row_count=100,
            csv_column_count=5,
            created_at=now,
            expires_at=now + timedelta(days=5),
            profile_lock={},
            profile_cells=[],
            profile_handoff=profile_handoff,
            pipeline_mode=PipelineMode.EXPLORATORY,
            phase1_quality_score=0.8,
            user_intent=None,
            agent_version="1.5.0"
        )

        assert valid_cache.is_expired() is False

    def test_profile_cache_is_valid_for_csv(self):
        """Test CSV hash validation."""
        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.8,
            row_count=100,
            column_count=5,
            column_profiles=(),
            overall_quality_score=0.8,
            missing_value_summary={}
        )

        cache = ProfileCache(
            cache_id="cache_3",
            csv_path="/data/test.csv",
            csv_hash="abc123",
            csv_size_bytes=1000,
            csv_row_count=100,
            csv_column_count=5,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            profile_lock={},
            profile_cells=[],
            profile_handoff=profile_handoff,
            pipeline_mode=PipelineMode.EXPLORATORY,
            phase1_quality_score=0.8,
            user_intent=None,
            agent_version="1.5.0"
        )

        assert cache.is_valid_for_csv("abc123") is True
        assert cache.is_valid_for_csv("different_hash") is False


class TestExtensions:
    """Test v1.6.0 extension models."""

    def test_forecasting_extension(self):
        """Test ForecastingExtension model."""
        gap_analysis = GapAnalysis(
            has_gaps=True,
            gap_count=5,
            largest_gap_periods=3,
            gap_locations=["2023-01-15", "2023-02-20"]
        )

        extension = ForecastingExtension(
            datetime_column="date",
            datetime_format="%Y-%m-%d",
            frequency="D",
            frequency_confidence=0.95,
            date_range=(datetime(2023, 1, 1), datetime(2023, 12, 31)),
            total_periods=365,
            missing_periods=[],
            gap_analysis=gap_analysis,
            stationarity_hint="likely_non_stationary",
            trend_detected=True,
            seasonality_detected=True,
            seasonality_period=7,
            recommended_models=["prophet", "arima"],
            preprocessing_needed=["detrend"],
            created_at=datetime.now(),
            csv_hash="abc123"
        )

        assert extension.datetime_column == "date"
        assert extension.seasonality_period == 7
        assert "prophet" in extension.recommended_models

    def test_comparative_extension(self):
        """Test ComparativeExtension model."""
        test = RecommendedTest(
            metric="conversion_rate",
            test_type="chi_square",
            rationale="Categorical outcome"
        )

        extension = ComparativeExtension(
            group_column="treatment",
            group_values=["control", "variant_a", "variant_b"],
            baseline_group="control",
            treatment_groups=["variant_a", "variant_b"],
            group_sizes={"control": 1000, "variant_a": 1000, "variant_b": 1000},
            balance_ratio=1.0,
            is_balanced=True,
            numeric_metrics=["conversion_rate", "revenue"],
            categorical_metrics=["outcome"],
            recommended_primary_metric="conversion_rate",
            recommended_tests=[test],
            multiple_comparison_correction="bonferroni",
            created_at=datetime.now(),
            csv_hash="abc123"
        )

        assert extension.group_column == "treatment"
        assert extension.is_balanced is True
        assert len(extension.recommended_tests) == 1

    def test_diagnostic_extension(self):
        """Test DiagnosticExtension model."""
        periods = AnalysisPeriods(
            before_start=datetime(2023, 1, 1),
            before_end=datetime(2023, 6, 30),
            after_start=datetime(2023, 7, 1),
            after_end=datetime(2023, 12, 31)
        )

        change_point = ChangePoint(
            timestamp=datetime(2023, 7, 1),
            metric="sales",
            magnitude=0.15,
            direction="decrease"
        )

        extension = DiagnosticExtension(
            has_temporal_data=True,
            temporal_column="date",
            analysis_periods=periods,
            metric_columns=["sales", "profit"],
            primary_metric="sales",
            metric_direction="higher_is_better",
            dimension_columns=["region", "product"],
            change_points_detected=[change_point],
            anomalies_detected=[],
            recommended_analysis=["trend_decomposition", "segment_analysis"],
            created_at=datetime.now(),
            csv_hash="abc123"
        )

        assert extension.primary_metric == "sales"
        assert len(extension.change_points_detected) == 1

    def test_root_cause_strategy(self):
        """Test RootCauseStrategy model."""
        hypothesis = Hypothesis(
            description="Regional differences causing decline",
            dimension="region",
            expected_contribution="high",
            test_approach="segment_analysis"
        )

        analysis_step = AnalysisStep(
            step_name="Decompose by Region",
            step_type="decomposition",
            parameters={"dimension": "region"},
            output_variables=["region_metrics"]
        )

        comparison = TimePeriodComparison(
            period1_label="Before",
            period2_label="After",
            period1_range=(datetime(2023, 1, 1), datetime(2023, 6, 30)),
            period2_range=(datetime(2023, 7, 1), datetime(2023, 12, 31))
        )

        strategy = RootCauseStrategy(
            metric_of_interest="sales",
            direction_of_change="decrease",
            magnitude_estimate=0.15,
            decomposition_dimensions=["region", "product"],
            time_comparison=comparison,
            hypotheses=[hypothesis],
            analysis_steps=[analysis_step],
            visualization_requirements=["trend_chart", "waterfall"]
        )

        assert strategy.metric_of_interest == "sales"
        assert len(strategy.hypotheses) == 1
        assert len(strategy.analysis_steps) == 1


class TestHandoffSerialization:
    """Test serialization and deserialization of handoffs."""

    def test_user_intent_roundtrip(self):
        """Test UserIntent serialization roundtrip."""
        intent = UserIntent(
            csv_path="/data/test.csv",
            target_column="target"
        )

        if hasattr(intent, 'model_dump_json'):
            json_str = intent.model_dump_json()
            restored = UserIntent.model_validate_json(json_str)
        else:
            json_str = intent.json()
            restored = UserIntent.parse_raw(json_str)

        assert restored.csv_path == intent.csv_path
        assert restored.target_column == intent.target_column

    def test_column_spec_roundtrip(self):
        """Test ColumnSpec serialization roundtrip."""
        spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        if hasattr(spec, 'model_dump_json'):
            json_str = spec.model_dump_json()
            restored = ColumnSpec.model_validate_json(json_str)
        else:
            json_str = spec.json()
            restored = ColumnSpec.parse_raw(json_str)

        assert restored.name == spec.name
        assert restored.detected_type == spec.detected_type
