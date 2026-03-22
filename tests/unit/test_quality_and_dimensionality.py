"""
Unit tests for v1.9.0 features.

Tests cover:
- Dimensionality Reduction Mode (7th pipeline mode)
- Data Quality Remediation (issue detection and remediation plans)
- PCA Assessment and Configuration
- New handoff models (QualityIssue, RemediationPlan, PCAConfig, DimensionalityStrategyHandoff)

Coverage includes:
- Quality issue detection
- Remediation plan generation
- PCA applicability assessment
- DimensionalityStrategyAgent
- Mode detection for dimensionality
- New enum values
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from src.models.handoffs import (
    # New v1.9.0 Enums
    QualityIssueType,
    RemediationType,
    SafetyRating,
    AnalysisType,
    PipelineMode,
    # New v1.9.0 Models
    QualityIssue,
    RemediationPlan,
    PCAConfig,
    DimensionalityStrategyHandoff,
    # Existing models
    ProfilerToCodeGenHandoff,
    ColumnSpec,
    DataType,
    StrategyToCodeGenHandoff,
    ColumnProfile,
)
from src.models.state import AnalysisState, ProfileLock
from src.services.mode_detector import ModeDetector


# ============================================================================
# Test New Enum Values
# ============================================================================

class TestV190Enums:
    """Test new v1.9.0 enum values."""

    def test_analysis_type_dimensionality(self):
        """Test AnalysisType.DIMENSIONALITY enum value."""
        assert AnalysisType.DIMENSIONALITY == "dimensionality"
        assert AnalysisType.DIMENSIONALITY.value == "dimensionality"

    def test_pipeline_mode_dimensionality(self):
        """Test PipelineMode.DIMENSIONALITY enum value."""
        assert PipelineMode.DIMENSIONALITY == "dimensionality"
        assert PipelineMode.DIMENSIONALITY.value == "dimensionality"

    def test_quality_issue_type_enum(self):
        """Test QualityIssueType enum values."""
        assert QualityIssueType.MISSING_VALUES == "missing_values"
        assert QualityIssueType.OUTLIERS_IQR == "outliers_iqr"
        assert QualityIssueType.OUTLIERS_ZSCORE == "outliers_zscore"
        assert QualityIssueType.DUPLICATE_ROWS == "duplicate_rows"
        assert QualityIssueType.DUPLICATE_KEYS == "duplicate_keys"
        assert QualityIssueType.TYPE_MISMATCH == "type_mismatch"
        assert QualityIssueType.MIXED_TYPES == "mixed_types"
        assert QualityIssueType.HIGH_CARDINALITY == "high_cardinality"
        assert QualityIssueType.INCONSISTENT_CATEGORIES == "inconsistent_categories"
        assert QualityIssueType.RARE_CATEGORIES == "rare_categories"
        assert QualityIssueType.INFINITE_VALUES == "infinite_values"
        assert QualityIssueType.NEGATIVE_WHERE_POSITIVE == "negative_where_positive"
        assert QualityIssueType.LEADING_TRAILING_WHITESPACE == "whitespace_issues"
        assert QualityIssueType.EMPTY_STRINGS == "empty_strings"
        assert QualityIssueType.ORPHAN_RECORDS == "orphan_records"

    def test_remediation_type_enum(self):
        """Test RemediationType enum values."""
        # Imputation methods
        assert RemediationType.IMPUTE_MEAN == "impute_mean"
        assert RemediationType.IMPUTE_MEDIAN == "impute_median"
        assert RemediationType.IMPUTE_MODE == "impute_mode"
        assert RemediationType.IMPUTE_CONSTANT == "impute_constant"
        assert RemediationType.IMPUTE_KNN == "impute_knn"
        assert RemediationType.IMPUTE_FORWARD_FILL == "impute_ffill"
        assert RemediationType.IMPUTE_BACKWARD_FILL == "impute_bfill"
        # Drop methods
        assert RemediationType.DROP_ROWS == "drop_rows"
        assert RemediationType.DROP_COLUMN == "drop_column"
        # Outlier handling
        assert RemediationType.CAP_FLOOR_IQR == "cap_floor_iqr"
        assert RemediationType.CAP_FLOOR_PERCENTILE == "cap_floor_percentile"
        assert RemediationType.CAP_FLOOR_ZSCORE == "cap_floor_zscore"
        assert RemediationType.WINSORIZE == "winsorize"
        assert RemediationType.LOG_TRANSFORM == "log_transform"
        assert RemediationType.DROP_OUTLIERS == "drop_outliers"
        assert RemediationType.FLAG_OUTLIERS == "flag_outliers"
        # Duplicate handling
        assert RemediationType.DROP_DUPLICATES_KEEP_FIRST == "drop_dup_first"
        assert RemediationType.DROP_DUPLICATES_KEEP_LAST == "drop_dup_last"
        assert RemediationType.DROP_DUPLICATES_KEEP_NONE == "drop_dup_none"
        assert RemediationType.FLAG_DUPLICATES == "flag_duplicates"
        # Type coercion
        assert RemediationType.COERCE_TO_NUMERIC == "coerce_numeric"
        assert RemediationType.COERCE_TO_DATETIME == "coerce_datetime"
        assert RemediationType.COERCE_TO_STRING == "coerce_string"
        # Normalization
        assert RemediationType.NORMALIZE_CASE == "normalize_case"
        assert RemediationType.NORMALIZE_WHITESPACE == "normalize_whitespace"
        # Category handling
        assert RemediationType.GROUP_RARE_CATEGORIES == "group_rare"
        assert RemediationType.TOP_N_ENCODING == "top_n_encoding"
        # No action
        assert RemediationType.NO_REMEDIATION == "no_remediation"

    def test_safety_rating_enum(self):
        """Test SafetyRating enum values."""
        assert SafetyRating.SAFE == "safe"
        assert SafetyRating.REVIEW == "review"
        assert SafetyRating.RISKY == "risky"
        assert SafetyRating.DANGEROUS == "dangerous"


# ============================================================================
# Test Quality Issue Model
# ============================================================================

class TestQualityIssue:
    """Test QualityIssue model."""

    def test_quality_issue_basic(self):
        """Test basic QualityIssue creation."""
        issue = QualityIssue(
            issue_id="missing_age",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="age",
            severity="medium",
            affected_count=50,
            affected_percentage=5.0,
            description="Column 'age' has 50 (5.0%) missing values.",
            detection_method="isnull().sum()"
        )

        assert issue.issue_id == "missing_age"
        assert issue.issue_type == QualityIssueType.MISSING_VALUES
        assert issue.column_name == "age"
        assert issue.severity == "medium"
        assert issue.affected_count == 50
        assert issue.affected_percentage == 5.0
        assert issue.examples == []
        assert issue.detection_params == {}

    def test_quality_issue_with_examples(self):
        """Test QualityIssue with examples."""
        issue = QualityIssue(
            issue_id="outliers_income",
            issue_type=QualityIssueType.OUTLIERS_IQR,
            column_name="income",
            severity="high",
            affected_count=25,
            affected_percentage=2.5,
            description="Income has 25 outliers detected via IQR.",
            examples=[1000000, 2000000, 5000000],
            detection_method="IQR method",
            detection_params={"iqr_multiplier": 1.5}
        )

        assert len(issue.examples) == 3
        assert issue.detection_params["iqr_multiplier"] == 1.5

    def test_quality_issue_duplicate_rows(self):
        """Test QualityIssue for duplicate rows (no column)."""
        issue = QualityIssue(
            issue_id="duplicate_rows",
            issue_type=QualityIssueType.DUPLICATE_ROWS,
            severity="critical",
            affected_count=100,
            affected_percentage=10.0,
            description="Dataset contains 100 (10.0%) duplicate rows.",
            detection_method="duplicated().sum()"
        )

        assert issue.column_name is None
        assert issue.issue_type == QualityIssueType.DUPLICATE_ROWS


# ============================================================================
# Test Remediation Plan Model
# ============================================================================

class TestRemediationPlan:
    """Test RemediationPlan model."""

    def test_remediation_plan_basic(self):
        """Test basic RemediationPlan creation."""
        issue = QualityIssue(
            issue_id="missing_age",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="age",
            severity="medium",
            affected_count=50,
            affected_percentage=5.0,
            description="Missing values in age",
            detection_method="isnull()"
        )

        plan = RemediationPlan(
            issue=issue,
            remediation_type=RemediationType.IMPUTE_MEDIAN,
            remediation_params={},
            safety_rating=SafetyRating.SAFE,
            safety_rationale="Median imputation is safe for numeric columns with low missingness.",
            auto_apply_recommended=True,
            code_snippet="df['age'] = df['age'].fillna(df['age'].median())",
            code_explanation="Impute missing values in 'age' with median.",
            estimated_rows_affected=50,
            estimated_data_loss=0.0
        )

        assert plan.remediation_type == RemediationType.IMPUTE_MEDIAN
        assert plan.safety_rating == SafetyRating.SAFE
        assert plan.auto_apply_recommended is True
        assert plan.user_approved is None
        assert plan.user_override_type is None
        assert "fillna" in plan.code_snippet

    def test_remediation_plan_with_user_override(self):
        """Test RemediationPlan with user override."""
        issue = QualityIssue(
            issue_id="missing_salary",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="salary",
            severity="high",
            affected_count=200,
            affected_percentage=20.0,
            description="High missingness in salary",
            detection_method="isnull()"
        )

        plan = RemediationPlan(
            issue=issue,
            remediation_type=RemediationType.IMPUTE_MEDIAN,
            remediation_params={},
            safety_rating=SafetyRating.REVIEW,
            safety_rationale="High missingness requires review.",
            auto_apply_recommended=False,
            user_approved=True,
            user_override_type=RemediationType.DROP_ROWS,
            code_snippet="df = df.dropna(subset=['salary'])",
            code_explanation="Drop rows with missing salary.",
            estimated_rows_affected=200,
            estimated_data_loss=0.2
        )

        assert plan.user_approved is True
        assert plan.user_override_type == RemediationType.DROP_ROWS
        assert plan.safety_rating == SafetyRating.REVIEW

    def test_remediation_plan_for_duplicates(self):
        """Test RemediationPlan for duplicate rows."""
        issue = QualityIssue(
            issue_id="duplicate_rows",
            issue_type=QualityIssueType.DUPLICATE_ROWS,
            severity="medium",
            affected_count=50,
            affected_percentage=5.0,
            description="Duplicate rows detected",
            detection_method="duplicated()"
        )

        plan = RemediationPlan(
            issue=issue,
            remediation_type=RemediationType.DROP_DUPLICATES_KEEP_FIRST,
            remediation_params={"keep": "first"},
            safety_rating=SafetyRating.SAFE,
            safety_rationale="Dropping duplicates keeping first is standard practice.",
            auto_apply_recommended=True,
            code_snippet="df = df.drop_duplicates(keep='first')",
            code_explanation="Remove duplicate rows, keeping the first occurrence.",
            estimated_rows_affected=50,
            estimated_data_loss=0.0
        )

        assert plan.remediation_type == RemediationType.DROP_DUPLICATES_KEEP_FIRST
        assert plan.remediation_params["keep"] == "first"


# ============================================================================
# Test PCA Config Model
# ============================================================================

class TestPCAConfig:
    """Test PCAConfig model."""

    def test_pca_config_defaults(self):
        """Test PCAConfig with default values."""
        config = PCAConfig()

        assert config.enabled is True
        assert config.feature_count_threshold == 20
        assert config.correlation_threshold == 0.9
        assert config.variance_retention_target == 0.95
        assert config.min_components == 2
        assert config.max_components is None
        assert config.generate_2d_plot is True
        assert config.generate_3d_plot is True
        assert config.generate_scree_plot is True
        assert config.generate_loadings_heatmap is True
        assert config.explain_top_n_components == 5
        assert config.show_feature_contributions is True
        assert config.apply_to_training_only is True
        assert config.use_llm_decision is True

    def test_pca_config_custom(self):
        """Test PCAConfig with custom values."""
        config = PCAConfig(
            enabled=True,
            feature_count_threshold=10,
            correlation_threshold=0.8,
            variance_retention_target=0.90,
            min_components=3,
            max_components=15,
            generate_3d_plot=False,
            explain_top_n_components=3,
            use_llm_decision=False
        )

        assert config.feature_count_threshold == 10
        assert config.correlation_threshold == 0.8
        assert config.variance_retention_target == 0.90
        assert config.max_components == 15
        assert config.generate_3d_plot is False
        assert config.use_llm_decision is False

    def test_pca_config_disabled(self):
        """Test PCAConfig when disabled."""
        config = PCAConfig(enabled=False)

        assert config.enabled is False


# ============================================================================
# Test DimensionalityStrategyHandoff Model
# ============================================================================

class TestDimensionalityStrategyHandoff:
    """Test DimensionalityStrategyHandoff model."""

    def test_dimensionality_strategy_handoff_basic(self):
        """Test basic DimensionalityStrategyHandoff creation."""
        config = PCAConfig(
            enabled=True,
            feature_count_threshold=20,
            variance_retention_target=0.95
        )

        handoff = DimensionalityStrategyHandoff(
            profile_reference="profile_abc123",
            config=config,
            target_variance=0.95,
            features_to_reduce=["col1", "col2", "col3", "col4", "col5"],
            interpretation_focus="visualization",
            visualizations=["scree_plot", "2d_scatter", "loadings_heatmap"]
        )

        assert handoff.profile_reference == "profile_abc123"
        assert handoff.config.enabled is True
        assert handoff.target_variance == 0.95
        assert len(handoff.features_to_reduce) == 5
        assert handoff.interpretation_focus == "visualization"
        assert "scree_plot" in handoff.visualizations

    def test_dimensionality_strategy_handoff_with_target(self):
        """Test DimensionalityStrategyHandoff with target column."""
        config = PCAConfig()

        handoff = DimensionalityStrategyHandoff(
            profile_reference="profile_xyz",
            config=config,
            target_variance=0.90,
            n_components_estimate=5,
            features_to_reduce=["f1", "f2", "f3"],
            target_column="label",
            interpretation_focus="feature_reduction",
            visualizations=["scree_plot"]
        )

        assert handoff.n_components_estimate == 5
        assert handoff.target_column == "label"
        assert handoff.interpretation_focus == "feature_reduction"


# ============================================================================
# Test ProfilerToCodeGenHandoff with v1.9.0 fields
# ============================================================================

class TestProfilerToCodeGenHandoffV190:
    """Test ProfilerToCodeGenHandoff with new v1.9.0 fields."""

    def test_profiler_to_codegen_with_remediation(self):
        """Test ProfilerToCodeGenHandoff with remediation plans."""
        col_spec = ColumnSpec(
            name="age",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        issue = QualityIssue(
            issue_id="missing_age",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="age",
            severity="medium",
            affected_count=50,
            affected_percentage=5.0,
            description="Missing values",
            detection_method="isnull()"
        )

        plan = RemediationPlan(
            issue=issue,
            remediation_type=RemediationType.IMPUTE_MEDIAN,
            remediation_params={},
            safety_rating=SafetyRating.SAFE,
            safety_rationale="Safe imputation",
            auto_apply_recommended=True,
            code_snippet="df['age'] = df['age'].fillna(df['age'].median())",
            code_explanation="Impute with median",
            estimated_rows_affected=50,
            estimated_data_loss=0.0
        )

        handoff = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=1,
            columns=[col_spec],
            remediation_plans=[plan]
        )

        assert len(handoff.remediation_plans) == 1
        assert handoff.remediation_plans[0].remediation_type == RemediationType.IMPUTE_MEDIAN

    def test_profiler_to_codegen_with_pca_config(self):
        """Test ProfilerToCodeGenHandoff with PCA config."""
        col_spec = ColumnSpec(
            name="feature1",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        pca_config = PCAConfig(
            enabled=True,
            feature_count_threshold=20,
            use_llm_decision=True
        )

        handoff = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=25,
            columns=[col_spec],
            pca_config=pca_config
        )

        assert handoff.pca_config is not None
        assert handoff.pca_config.enabled is True
        assert handoff.pca_config.feature_count_threshold == 20

    def test_profiler_to_codegen_with_both(self):
        """Test ProfilerToCodeGenHandoff with both remediation and PCA."""
        col_spec = ColumnSpec(
            name="feature1",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            analysis_approach="Statistical"
        )

        issue = QualityIssue(
            issue_id="missing_feature1",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="feature1",
            severity="low",
            affected_count=10,
            affected_percentage=1.0,
            description="Minor missing values",
            detection_method="isnull()"
        )

        plan = RemediationPlan(
            issue=issue,
            remediation_type=RemediationType.IMPUTE_MEAN,
            remediation_params={},
            safety_rating=SafetyRating.SAFE,
            safety_rationale="Low missingness",
            auto_apply_recommended=True,
            code_snippet="df['feature1'] = df['feature1'].fillna(df['feature1'].mean())",
            code_explanation="Impute with mean",
            estimated_rows_affected=10,
            estimated_data_loss=0.0
        )

        pca_config = PCAConfig(enabled=True)

        handoff = ProfilerToCodeGenHandoff(
            csv_path="/data/test.csv",
            row_count=1000,
            column_count=30,
            columns=[col_spec],
            remediation_plans=[plan],
            pca_config=pca_config
        )

        assert len(handoff.remediation_plans) == 1
        assert handoff.pca_config.enabled is True


# ============================================================================
# Test Data Profiler Quality Detection
# ============================================================================

class TestDataProfilerQualityDetection:
    """Test DataProfilerAgent quality issue detection."""

    @pytest.fixture
    def profiler_agent(self):
        """Create a DataProfilerAgent instance."""
        with patch('src.agents.base.LLMAgent'):
            from src.agents.phase1.data_profiler import DataProfilerAgent
            return DataProfilerAgent()

    def test_detect_missing_values(self, profiler_agent):
        """Test detection of missing values."""
        df = pd.DataFrame({
            'A': [1, 2, np.nan, 4, 5, np.nan, 7, 8, np.nan, 10],
            'B': ['x', 'y', 'z', 'x', 'y', 'z', 'x', 'y', 'z', 'x']
        })

        issues = profiler_agent.detect_quality_issues(df)

        # Should detect missing values in column A
        missing_issues = [i for i in issues if i.issue_type == QualityIssueType.MISSING_VALUES]
        assert len(missing_issues) == 1
        assert missing_issues[0].column_name == 'A'
        assert missing_issues[0].affected_count == 3
        assert missing_issues[0].affected_percentage == 30.0

    def test_detect_duplicates(self, profiler_agent):
        """Test detection of duplicate rows."""
        df = pd.DataFrame({
            'A': [1, 2, 3, 1, 2],
            'B': ['x', 'y', 'z', 'x', 'y']
        })

        issues = profiler_agent.detect_quality_issues(df)

        # Should detect duplicate rows
        dup_issues = [i for i in issues if "duplicate" in str(i.issue_type).lower()]
        assert len(dup_issues) == 1
        assert dup_issues[0].affected_count == 2
        assert dup_issues[0].affected_percentage == 40.0

    def test_no_issues_clean_data(self, profiler_agent):
        """Test no issues detected for clean data."""
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': ['a', 'b', 'c', 'd', 'e']
        })

        issues = profiler_agent.detect_quality_issues(df)

        # No missing values or duplicates
        assert len(issues) == 0


# ============================================================================
# Test Data Profiler Remediation Plan Generation
# ============================================================================

class TestDataProfilerRemediationPlan:
    """Test DataProfilerAgent remediation plan generation."""

    @pytest.fixture
    def profiler_agent(self):
        """Create a DataProfilerAgent instance."""
        with patch('src.agents.base.LLMAgent'):
            from src.agents.phase1.data_profiler import DataProfilerAgent
            return DataProfilerAgent()

    def test_generate_numeric_imputation_plan(self, profiler_agent):
        """Test remediation plan for numeric missing values."""
        df = pd.DataFrame({
            'age': [25, 30, np.nan, 40, 45],
            'name': ['A', 'B', 'C', 'D', 'E']
        })

        issues = profiler_agent.detect_quality_issues(df)
        plans = profiler_agent.generate_remediation_plan(issues, df)

        # Should generate median imputation for numeric column
        numeric_plans = [p for p in plans if p.issue.column_name == 'age']
        assert len(numeric_plans) == 1
        assert numeric_plans[0].remediation_type == RemediationType.IMPUTE_MEDIAN
        assert "median" in numeric_plans[0].code_snippet

    def test_generate_categorical_imputation_plan(self, profiler_agent):
        """Test remediation plan for categorical missing values."""
        df = pd.DataFrame({
            'category': ['A', 'B', np.nan, 'A', 'B']
        })

        issues = profiler_agent.detect_quality_issues(df)
        plans = profiler_agent.generate_remediation_plan(issues, df)

        # Should generate mode imputation for categorical column
        cat_plans = [p for p in plans if p.issue.column_name == 'category']
        assert len(cat_plans) == 1
        assert cat_plans[0].remediation_type == RemediationType.IMPUTE_MODE
        assert "mode" in cat_plans[0].code_snippet

    def test_generate_duplicate_removal_plan(self, profiler_agent):
        """Test remediation plan for duplicate rows."""
        df = pd.DataFrame({
            'A': [1, 2, 3, 1, 2],
            'B': ['x', 'y', 'z', 'x', 'y']
        })

        issues = profiler_agent.detect_quality_issues(df)
        plans = profiler_agent.generate_remediation_plan(issues, df)

        # Should generate drop duplicates plan
        dup_plans = [p for p in plans if p.remediation_type == RemediationType.DROP_DUPLICATES_KEEP_FIRST]
        assert len(dup_plans) == 1
        assert "drop_duplicates" in dup_plans[0].code_snippet


# ============================================================================
# Test Data Profiler PCA Assessment
# ============================================================================

class TestDataProfilerPCAAssessment:
    """Test DataProfilerAgent PCA applicability assessment."""

    @pytest.fixture
    def profiler_agent(self):
        """Create a DataProfilerAgent instance."""
        with patch('src.agents.base.LLMAgent'):
            from src.agents.phase1.data_profiler import DataProfilerAgent
            return DataProfilerAgent()

    def test_pca_applicable_high_dimensionality(self, profiler_agent):
        """Test PCA is recommended for high-dimensional data."""
        # Create DataFrame with 25 numeric columns
        data = np.random.rand(100, 25)
        df = pd.DataFrame(data, columns=[f'col_{i}' for i in range(25)])

        config = profiler_agent.assess_pca_applicability(df)

        assert config is not None
        assert config.enabled is True
        assert config.feature_count_threshold == 20
        assert config.use_llm_decision is True

    def test_pca_not_applicable_low_dimensionality(self, profiler_agent):
        """Test PCA not recommended for low-dimensional data."""
        # Create DataFrame with only 5 numeric columns
        df = pd.DataFrame({
            'col1': np.random.rand(100),
            'col2': np.random.rand(100),
            'col3': np.random.rand(100),
            'col4': np.random.rand(100),
            'col5': np.random.rand(100)
        })

        config = profiler_agent.assess_pca_applicability(df)

        assert config is None

    def test_pca_threshold_boundary(self, profiler_agent):
        """Test PCA at threshold boundary (20 columns)."""
        # Create DataFrame with exactly 20 numeric columns
        data = np.random.rand(100, 20)
        df = pd.DataFrame(data, columns=[f'col_{i}' for i in range(20)])

        config = profiler_agent.assess_pca_applicability(df)

        # 20 columns should not trigger PCA (threshold is > 20)
        assert config is None


# ============================================================================
# Test Orchestrator Mode Detection for Dimensionality
# ============================================================================

class TestModeDetectorDimensionality:
    """Test ModeDetector dimensionality mode detection."""

    def test_mode_detection_explicit_dimensionality(self):
        """Test explicit dimensionality mode flag."""
        mode, method = ModeDetector.determine_mode(
            "dimensionality", None, None
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "explicit"

    def test_mode_detection_explicit_dim(self):
        """Test explicit 'dim' shorthand."""
        mode, method = ModeDetector.determine_mode(
            "dim", None, None
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "explicit"

    def test_mode_detection_explicit_pca(self):
        """Test explicit 'pca' flag."""
        mode, method = ModeDetector.determine_mode(
            "pca", None, None
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "explicit"

    def test_mode_detection_keyword_dimensionality(self):
        """Test keyword inference for dimensionality."""
        mode, method = ModeDetector.determine_mode(
            None, None, "Can you reduce dimensionality of this data?"
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "inferred_keyword"

    def test_mode_detection_keyword_pca(self):
        """Test keyword inference for PCA."""
        mode, method = ModeDetector.determine_mode(
            None, None, "Run PCA on this dataset"
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "inferred_keyword"

    def test_mode_detection_keyword_reduction(self):
        """Test keyword inference for 'reduction'."""
        mode, method = ModeDetector.determine_mode(
            None, None, "I need feature reduction for my data"
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "inferred_keyword"

    def test_mode_detection_keyword_principal_component(self):
        """Test keyword inference for 'principal component'."""
        mode, method = ModeDetector.determine_mode(
            None, None, "Perform principal component analysis"
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "inferred_keyword"

    def test_mode_detection_keyword_compress_features(self):
        """Test keyword inference for 'compress features'."""
        mode, method = ModeDetector.determine_mode(
            None, None, "Compress features to reduce noise"
        )
        assert mode == PipelineMode.DIMENSIONALITY
        assert method == "inferred_keyword"


# ============================================================================
# Test DimensionalityStrategyAgent
# ============================================================================

class TestDimensionalityStrategyAgent:
    """Test DimensionalityStrategyAgent."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock AnalysisState."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.DIMENSIONALITY
        state.user_intent = None

        # Mock profile lock
        col_profile = ColumnProfile(
            name="feature1",
            detected_type=DataType.NUMERIC_CONTINUOUS,
            detection_confidence=0.95,
            unique_count=100,
            null_percentage=0.0
        )

        mock_handoff = MagicMock()
        mock_handoff.column_profiles = [col_profile]

        state.profile_lock = MagicMock(spec=ProfileLock)
        state.profile_lock.is_locked.return_value = True
        state.profile_lock.get_locked_handoff.return_value = mock_handoff
        state.profile_lock.lock_hash = "test_hash"

        return state

    def test_dimensionality_strategy_agent_process(self, mock_state):
        """Test DimensionalityStrategyAgent process method."""
        with patch('src.agents.base.LLMAgent') as MockLLM:
            mock_llm = MockLLM.return_value
            mock_llm.invoke_with_json.return_value = '{"analysis_objective": "Perform PCA", "feature_columns": ["f1"], "preprocessing_steps": [], "models_to_train": [], "result_visualizations": []}'

            from src.agents.phase2.dimensionality_strategy import DimensionalityStrategyAgent
            agent = DimensionalityStrategyAgent()

            result = agent.process(mock_state)

            assert "handoff" in result
            assert result["handoff"].analysis_type == AnalysisType.DIMENSIONALITY

    def test_dimensionality_strategy_agent_fallback(self, mock_state):
        """Test DimensionalityStrategyAgent fallback strategy."""
        with patch('src.agents.base.LLMAgent') as MockLLM:
            mock_llm = MockLLM.return_value
            # Simulate LLM failure
            mock_llm.invoke_with_json.side_effect = Exception("LLM Error")

            from src.agents.phase2.dimensionality_strategy import DimensionalityStrategyAgent
            agent = DimensionalityStrategyAgent()

            result = agent.process(mock_state)

            # Should use fallback strategy
            assert "handoff" in result
            assert result["handoff"].analysis_type == AnalysisType.DIMENSIONALITY


# ============================================================================
# Test AnalysisCodeGen for Dimensionality
# ============================================================================



# ============================================================================
# Test Serialization
# ============================================================================

class TestV190Serialization:
    """Test serialization of v1.9.0 models."""

    def test_quality_issue_serialization(self):
        """Test QualityIssue JSON serialization roundtrip."""
        issue = QualityIssue(
            issue_id="test_issue",
            issue_type=QualityIssueType.MISSING_VALUES,
            column_name="test_col",
            severity="medium",
            affected_count=10,
            affected_percentage=5.0,
            description="Test issue",
            detection_method="test"
        )

        if hasattr(issue, 'model_dump_json'):
            json_str = issue.model_dump_json()
            restored = QualityIssue.model_validate_json(json_str)
        else:
            json_str = issue.json()
            restored = QualityIssue.parse_raw(json_str)

        assert restored.issue_id == issue.issue_id
        assert restored.issue_type == issue.issue_type

    def test_pca_config_serialization(self):
        """Test PCAConfig JSON serialization roundtrip."""
        config = PCAConfig(
            enabled=True,
            feature_count_threshold=25,
            variance_retention_target=0.90
        )

        if hasattr(config, 'model_dump_json'):
            json_str = config.model_dump_json()
            restored = PCAConfig.model_validate_json(json_str)
        else:
            json_str = config.json()
            restored = PCAConfig.parse_raw(json_str)

        assert restored.enabled == config.enabled
        assert restored.feature_count_threshold == config.feature_count_threshold
