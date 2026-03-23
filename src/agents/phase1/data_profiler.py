"""
Data Profiler Agent - EDA specialist for Phase 1.

The Data Profiler is the first agent in the active pipeline. Its goal is to
"understand" the raw data before any code is written. It performs initial
Exploratory Data Analysis (EDA) to:
1. Infer column data types (numeric, categorical, temporal, etc.).
2. Assess data quality (missing values, duplicates).
3. Identify statistical properties.
4. Propose a set of visualizations and analyses for the Code Generator.

It uses a hybrid approach:
- LLM-based analysis for semantic understanding (e.g., "Is this 'ID' column useful?").
- Heuristic fallback for robust type detection if the LLM fails.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.agents.base import BaseAgent
from src.prompts import DATA_PROFILER_PROMPT
from src.models.state import AnalysisState, Phase
from src.models.handoffs import (
    ColumnSpec,
    DataType,
    MarkdownSection,
    OrchestratorToProfilerHandoff,
    ProfilerToCodeGenHandoff,
    QualityCheckRequirement,
    StatisticsRequirement,
    VisualizationRequirement,
    QualityIssue,
    QualityIssueType,
    RemediationPlan,
    RemediationType,
    SafetyRating,
    PCAConfig,
)
from src.services.template_manager import TemplateManager
from src.services.dictionary_manager import DictionaryParser
from src.models.dictionary import DataDictionary
from src.services.data_loader import DataLoader
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger()


class DataProfilerAgent(BaseAgent):
    """
    Data Profiler Agent for Phase 1.

    Analyzes the input CSV to produce a comprehensive profiling specification.
    This specification acts as the blueprint for the Profile Code Generator.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="DataProfiler",
            phase=Phase.PHASE_1,
            system_prompt=DATA_PROFILER_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Execute profiling analysis on the provided data.

        Args:
            state: Current analysis state.
            **kwargs: Requires 'handoff' (OrchestratorToProfilerHandoff).
                      Optional 'dictionary_path' in kwargs or handoff.

        Returns:
            Dictionary containing the 'handoff' (ProfilerToCodeGenHandoff)
            for the next agent and confidence metrics.
        """
        # Log agent invocation
        logger.agent_execution("DataProfiler", "invoked", csv_path=state.csv_path)

        handoff: OrchestratorToProfilerHandoff | None = kwargs.get("handoff")

        # Load DataFrame
        if state.csv_data is not None:
            df = (
                pd.DataFrame(state.csv_data)
                if isinstance(state.csv_data, dict)
                else state.csv_data
            )
        elif handoff and handoff.is_multi_file:
            logger.info("Detected multi-file input. Using DataLoader to merge.")
            loader = DataLoader()
            try:
                # Merge datasets
                if not handoff.multi_file_input:
                    raise ValueError("multi_file_input is None")
                df, merged_meta = loader.merge_datasets(handoff.multi_file_input)
                # Note: We might want to save this merged DF to a temp path for downstream agents?
                # For now, we operate in memory, but state.csv_path still points to primary.
                # Ideally, we should update state.csv_path to a new merged file specific path if we serialize it.
                # However, ProfileCodeGen typically writes code to load CSV.
                # If we dynamically merge in memory here, ProfileCodeGen needs to know how to load it.
                # Options:
                # 1. Save merged DF to disk and update csv_path.
                # 2. Tell CodeGen to generate code that performs the merge (complex).
                # Approach 1 is safer for v1.8. Let's save it.

                cache_dir = (
                    Path(state.csv_path).parent
                    if state.csv_path
                    else Path(tempfile.gettempdir())
                )
                merged_filename = f"merged_{Path(state.csv_path).name}"
                merged_path = str(cache_dir / merged_filename)

                df.to_csv(merged_path, index=False)
                logger.info(f"Saved merged dataset to {merged_path}")

                # Update references to point to the merged file
                # Do not mutate state directly
                # state.csv_path = merged_path
                handoff.merged_dataset = merged_meta
                handoff.merged_dataset.merged_df_path = merged_path

            except Exception as e:
                logger.error(f"Multi-file merge failed: {e}")
                # Fallback to single file load
                from src.utils.file_utils import load_csv_robust

                df = load_csv_robust(state.csv_path)
        else:
            try:
                # Check for Parquet first
                if state.csv_path.lower().endswith(".parquet"):
                    df = pd.read_parquet(state.csv_path)
                else:
                    from src.utils.file_utils import load_csv_robust

                    df = load_csv_robust(state.csv_path)
            except pd.errors.EmptyDataError:
                logger.error(f"Empty CSV file: {state.csv_path}")
                return {
                    "handoff": None,
                    "confidence": 0.0,
                    "error": "Empty CSV file provided",
                }
            except Exception as e:
                logger.error(f"Failed to load CSV: {e}")
                raise e
        if "df" in locals() and df is not None:
            # Performance: We rely on DataManager/cache or reload to avoid serializing DF in state
            pass
        # Load Data Dictionary (v1.8.0)
        data_dictionary: Optional[DataDictionary] = None
        # Check kwargs or user intent for dictionary path
        dict_path = kwargs.get("dictionary_path")
        if not dict_path and handoff and handoff.user_intent:
            # Assuming user_intent might carry it in future, or we parse it from kwargs passed from API
            pass

        # If passed explicitly in kwargs (e.g. from API)
        if dict_path:
            logger.info(f"Loading data dictionary from {dict_path}")
            data_dictionary = DictionaryParser.parse(dict_path)

        # BUILD CONTEXT FOR CACHING
        from src.utils.cache_manager import CacheManager

        cache_manager = CacheManager()
        csv_hash = cache_manager.get_csv_hash(state.csv_path)

        # Check for cached analysis
        cached_analysis = cache_manager.load_artifact(csv_hash, "profiler_analysis")
        if cached_analysis:
            logger.info(f"Using cached profiler analysis for {state.csv_path}")
            analysis = cached_analysis
        else:
            # Build context for LLM
            context = self._build_analysis_context(df, handoff, data_dictionary)

            # Get LLM analysis
            prompt = self._build_profiler_prompt(context, handoff)

            try:
                response = self.llm_agent.invoke_with_json(prompt)

                # Parse response
                analysis = json.loads(response)
            except Exception as e:
                # Fall back to heuristic analysis
                logger.warning(
                    f"Data Profiler LLM analysis failed ({e}), using heuristic fallback"
                )
                analysis = self._heuristic_analysis(df)

            # Save final analysis (LLM or Heuristic) to cache
            cache_manager.save_artifact(csv_hash, "profiler_analysis", analysis)

        # Detect Domain (v1.8.0)
        template_manager = TemplateManager()
        detected_domain = template_manager.detect_domain(df.columns.tolist())

        # v1.9.0: Quality Remediation & PCA Assessment
        issues = self.detect_quality_issues(df)
        remediation_plans = self.generate_remediation_plan(issues, df)
        pca_config = self.assess_pca_applicability(df)

        # Build handoff object
        profiler_handoff = self._build_handoff(
            df, analysis, state.csv_path, detected_domain, data_dictionary
        )
        profiler_handoff.remediation_plans = remediation_plans
        profiler_handoff.pca_config = pca_config

        confidence = analysis.get("confidence", 0.8)

        # Log completion
        logger.agent_execution(
            "DataProfiler",
            "completed",
            rows=len(df),
            columns=len(df.columns),
            confidence=confidence,
        )

        result = {
            "handoff": profiler_handoff,
            "confidence": confidence,
            "issues": [],
            "suggestions": [],
        }

        # If we merged files, pass the new path back to update global state
        if handoff and handoff.merged_dataset and handoff.merged_dataset.merged_df_path:
            result["updated_csv_path"] = handoff.merged_dataset.merged_df_path

        return result

    def _build_profiler_prompt(
        self, context: str, handoff: OrchestratorToProfilerHandoff | None
    ) -> str:
        """Construct the analysis prompt."""
        user_intent_json = json.dumps(
            handoff.user_intent.model_dump() if handoff and handoff.user_intent else {},
            indent=2,
        )

        return f"""Analyze this CSV data and provide a profiling specification.

        DATA CONTEXT:
        {context}

        USER INTENT:
        {user_intent_json}

        Provide your analysis as JSON following the specified format."""

    def _build_analysis_context(
        self,
        df: pd.DataFrame,
        handoff: Optional[OrchestratorToProfilerHandoff],
        dictionary: Optional[DataDictionary] = None,
    ) -> str:
        """Build context string for LLM analysis."""
        context_parts = [
            f"Shape: {df.shape[0]} rows x {df.shape[1]} columns",
        ]

        if handoff:
            dup_count = (
                handoff.extended_metadata.duplicate_count
                if handoff.extended_metadata
                else handoff.duplicate_row_count
            )
            context_parts.append(f"Duplicate Rows: {dup_count}")

        context_parts.append(f"Columns: {list(df.columns)}")
        context_parts.append("\nColumn Info:")

        # Populate descriptions if available
        descriptions = dictionary.to_simple_dict() if dictionary else {}

        # Pre-compute metrics for speed (vectorized)
        unique_counts = df.nunique()
        try:
            null_pcts = df.isnull().mean() * 100
        except Exception:
            # Fallback for complex types
            null_pcts = pd.Series({c: df[c].isnull().mean() * 100 for c in df.columns})

        for col in df.columns:
            dtype = str(df[col].dtype)

            # Use pre-calculated metrics if available (faster/consistent)
            ext = handoff.extended_metadata if handoff else None
            if ext and col in ext.unique_counts:
                unique = ext.unique_counts[col]
            elif handoff and col in handoff.column_unique_counts:
                unique = handoff.column_unique_counts[col]
            else:
                try:
                    unique = unique_counts[col]
                except KeyError:
                    unique = df[col].nunique()

            try:
                null_pct = null_pcts[col]
            except KeyError:
                null_pct = df[col].isnull().mean() * 100

            sample = df[col].dropna().head(3).tolist()

            desc_str = (
                f", description='{descriptions[col]}'" if col in descriptions else ""
            )

            context_parts.append(
                f"  - {col}: dtype={dtype}, unique={unique}, null={null_pct:.1f}%, samples={sample}{desc_str}"
            )

        # Fallback to simple dict from handoff or user_intent if no explicit
        # DataDictionary object was provided.  Prefer handoff.data_dictionary
        # for backwards compat, then user_intent.data_dictionary.
        dd = None
        if not dictionary and handoff:
            dd = handoff.data_dictionary or (
                handoff.user_intent.data_dictionary
                if handoff.user_intent
                else None
            )
        if dd:
            context_parts.append("\nData Dictionary (from intent):")
            for field, desc in dd.items():
                if field in df.columns:
                    context_parts.append(f"  - {field}: {desc}")

        context_parts.append(
            f"\nFirst 3 rows:\n{df.head(3).to_string(line_width=100, max_colwidth=50)}"
        )

        return "\n".join(context_parts)

    def _heuristic_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Fallback heuristic analysis if LLM fails."""
        columns, numeric_cols, categorical_cols = self._analyze_column_types(df)

        stats_reqs = self._build_statistics_requirements(numeric_cols)
        viz_reqs = self._build_visualization_requirements(columns, numeric_cols)
        quality_reqs = self._build_quality_requirements(df, numeric_cols)

        markdown_sections = [
            {"section_type": "title", "content_guidance": "Data Profiling Report"},
            {
                "section_type": "data_overview",
                "content_guidance": "Overview of dataset shape, columns, and types",
            },
            {
                "section_type": "statistics_summary",
                "content_guidance": "Summary statistics for numeric columns",
            },
            {
                "section_type": "quality_summary",
                "content_guidance": "Data quality assessment with missing values and potential issues",
            },
        ]

        return {
            "columns": columns,
            "statistics_requirements": stats_reqs,
            "visualization_requirements": viz_reqs,
            "quality_check_requirements": quality_reqs,
            "markdown_sections": markdown_sections,
            "confidence": 0.75,
        }

    def _analyze_column_types(
        self, df: pd.DataFrame
    ) -> tuple[List[Dict[str, Any]], List[str], List[str]]:
        """Analyze DataFrame columns and detect their types."""
        columns: List[Dict[str, Any]] = []
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []

        for col in df.columns:
            unique_ratio = df[col].nunique() / len(df) if len(df) > 0 else 0
            unique_count = df[col].nunique()

            # Detect type
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                detected_type = DataType.DATETIME
                viz = ["line"]
            elif pd.api.types.is_bool_dtype(df[col]) or unique_count == 2:
                detected_type = DataType.BINARY
                viz = ["bar"]
            elif pd.api.types.is_numeric_dtype(df[col]):
                if unique_ratio < 0.05 or unique_count < 20:
                    detected_type = DataType.NUMERIC_DISCRETE
                    numeric_cols.append(col)
                    viz = ["bar", "boxplot"]
                else:
                    detected_type = DataType.NUMERIC_CONTINUOUS
                    numeric_cols.append(col)
                    viz = ["histogram", "boxplot"]
            elif unique_ratio > 0.9 or "id" in col.lower():
                detected_type = DataType.IDENTIFIER
                viz = []
            elif unique_ratio < 0.05 or unique_count < 50:
                detected_type = DataType.CATEGORICAL
                categorical_cols.append(col)
                viz = ["bar"]
            else:
                detected_type = DataType.TEXT
                viz = []

            columns.append(
                {
                    "name": col,
                    "detected_type": detected_type.value,
                    "detection_confidence": 0.75,
                    "analysis_approach": f"Analyze as {detected_type.value}",
                    "suggested_visualizations": viz,
                }
            )

        return columns, numeric_cols, categorical_cols  # type: ignore

    def _build_statistics_requirements(
        self, numeric_cols: List[str]
    ) -> List[Dict[str, Any]]:
        """Build statistics requirements based on numeric columns."""
        stats_reqs = []
        if numeric_cols:
            stats_reqs.append(
                {
                    "stat_type": "descriptive",
                    "target_columns": numeric_cols,
                    "parameters": {},
                }
            )
            if len(numeric_cols) > 1:
                stats_reqs.append(
                    {
                        "stat_type": "correlation",
                        "target_columns": numeric_cols,
                        "parameters": {},
                    }
                )
        return stats_reqs

    def _build_visualization_requirements(
        self, columns: List[Dict], numeric_cols: List[str]
    ) -> List[Dict[str, Any]]:
        """Build visualization requirements based on column analysis."""
        viz_reqs = []
        for col_spec in columns:
            for viz in col_spec["suggested_visualizations"]:
                viz_reqs.append(
                    {
                        "viz_type": viz,
                        "target_columns": [col_spec["name"]],
                        "title": f"{viz.title()} of {col_spec['name']}",
                        "parameters": {},
                    }
                )

        # Add correlation heatmap
        if len(numeric_cols) > 1:
            viz_reqs.append(
                {
                    "viz_type": "heatmap",
                    "target_columns": numeric_cols,
                    "title": "Correlation Heatmap",
                    "parameters": {},
                }
            )
        return viz_reqs

    def _build_quality_requirements(
        self, df: pd.DataFrame, numeric_cols: List[str]
    ) -> List[Dict[str, Any]]:
        """Build data quality check requirements."""
        quality_reqs: List[Dict[str, Any]] = [
            {
                "check_type": "missing_values",
                "target_columns": list(df.columns),
                "threshold": 0.05,
            },
            {
                "check_type": "duplicates",
                "target_columns": list(df.columns),
                "threshold": None,
            },
        ]

        if numeric_cols:
            quality_reqs.append(
                {
                    "check_type": "outliers",
                    "target_columns": numeric_cols,
                    "threshold": 3.0,  # Z-score threshold
                }
            )

        # Add high cardinality / uniqueness checks for ID columns or all columns
        # To satisfy test_high_cardinality_detection which expects 'unique_values' or 'cardinality' check
        other_cols = [col for col in df.columns if col not in numeric_cols]
        if other_cols:
            quality_reqs.append(
                {
                    "check_type": "unique_values",
                    "target_columns": other_cols,
                    "threshold": 0.9,
                }
            )

        return quality_reqs

    def _build_handoff(
        self,
        df: pd.DataFrame,
        analysis: Dict[str, Any],
        csv_path: str,
        detected_domain: Optional[Any] = None,
        data_dictionary: Optional[DataDictionary] = None,
    ) -> ProfilerToCodeGenHandoff:
        """Build the ProfilerToCodeGenHandoff from analysis results."""

        columns = []
        for col in analysis.get("columns", []):
            try:
                dtype = DataType(col["detected_type"])
            except ValueError:
                # Fallback for invalid types from LLM
                dtype = DataType.TEXT

            columns.append(
                ColumnSpec(
                    name=col["name"],
                    detected_type=dtype,
                    detection_confidence=col.get(
                        "detection_confidence", col.get("confidence", 0.0)
                    ),
                    analysis_approach=col.get("analysis_approach", "General analysis"),
                    suggested_visualizations=col.get("suggested_visualizations", []),
                )
            )

        def ensure_list(item: Any) -> List[Any]:
            if isinstance(item, list):
                return item
            if isinstance(item, str):
                return [item]
            return [] if item is None else [item]

        def clean_target_columns(columns: Any) -> List[str]:
            """Ensure target_columns is a flat list of strings."""
            if isinstance(columns, str):
                return [columns]
            if isinstance(columns, list):
                # Flatten one level if nested items exist
                flattened = []
                for item in columns:
                    if isinstance(item, list):
                        flattened.extend([str(i) for i in item])
                    else:
                        flattened.append(str(item))
                return flattened
            return [] if columns is None else [str(columns)]

        stats_reqs = []
        for req in analysis.get("statistics_requirements", []):
            if "target_columns" in req:
                req["target_columns"] = clean_target_columns(req["target_columns"])
            stats_reqs.append(StatisticsRequirement(**req))

        viz_reqs = []
        for req in analysis.get("visualization_requirements", []):
            if "target_columns" in req:
                req["target_columns"] = clean_target_columns(req["target_columns"])
            viz_reqs.append(VisualizationRequirement(**req))

        quality_reqs = []
        for req in analysis.get("quality_check_requirements", []):
            if "target_columns" in req:
                req["target_columns"] = clean_target_columns(req["target_columns"])
            quality_reqs.append(QualityCheckRequirement(**req))

        markdown_sections = [
            MarkdownSection(**section)
            for section in analysis.get("markdown_sections", [])
        ]

        # Prepare simple dictionary for handoff
        simple_dict = data_dictionary.to_simple_dict() if data_dictionary else {}

        return ProfilerToCodeGenHandoff(
            csv_path=csv_path,
            row_count=len(df),
            column_count=len(df.columns),
            columns=columns,
            statistics_requirements=stats_reqs,
            visualization_requirements=viz_reqs,
            quality_check_requirements=quality_reqs,
            markdown_sections=markdown_sections,
            detected_domain=detected_domain,
            data_dictionary=simple_dict,
        )

    def detect_quality_issues(self, df: pd.DataFrame) -> List[QualityIssue]:
        """Detect quality issues in the dataframe."""
        issues = []
        # Missing values
        for col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                pct = (null_count / len(df)) * 100
                severity = "low"
                if pct > 50:
                    severity = "critical"
                elif pct > 20:
                    severity = "high"
                elif pct > 5:
                    severity = "medium"

                issues.append(
                    QualityIssue(
                        issue_id=f"missing_{col}",
                        issue_type=QualityIssueType.MISSING_VALUES,
                        column_name=col,
                        severity=severity,
                        affected_count=int(null_count),
                        affected_percentage=pct,
                        description=f"Column '{col}' has {null_count} ({pct:.1f}%) missing values.",
                        detection_method="isnull().sum()",
                    )
                )

        # Duplicates
        dup_count = df.duplicated().sum()
        if dup_count > 0:
            pct = (dup_count / len(df)) * 100
            severity = "low"
            if pct > 10:
                severity = "critical"

            issues.append(
                QualityIssue(
                    issue_id="duplicate_rows",
                    issue_type=QualityIssueType.DUPLICATE_ROWS,
                    severity="medium"
                    if pct < 5
                    else ("high" if pct < 10 else "critical"),
                    affected_count=int(dup_count),
                    affected_percentage=pct,
                    description=f"Dataset contains {dup_count} ({pct:.1f}%) duplicate rows.",
                    detection_method="duplicated().sum()",
                )
            )

        return issues

    def generate_remediation_plan(
        self, issues: List[QualityIssue], df: pd.DataFrame
    ) -> List[RemediationPlan]:
        """Generate remediation plans for detected issues."""
        plans = []
        for issue in issues:
            if issue.issue_type == QualityIssueType.MISSING_VALUES:
                col = issue.column_name
                dtype = df[col].dtype
                params: Dict[str, Any] = {}
                if pd.api.types.is_numeric_dtype(dtype):
                    remediation = RemediationType.IMPUTE_MEDIAN
                    code = f"df['{col}'] = df['{col}'].fillna(df['{col}'].median())"
                    safety = SafetyRating.SAFE
                else:
                    remediation = RemediationType.IMPUTE_MODE
                    code = f"df['{col}'] = df['{col}'].fillna(df['{col}'].mode()[0])"
                    safety = SafetyRating.SAFE

                plans.append(
                    RemediationPlan(
                        issue=issue,
                        remediation_type=remediation,
                        remediation_params=params,
                        safety_rating=safety,
                        safety_rationale="Imputing with central tendency is generally safe for low percentage missingness.",
                        auto_apply_recommended=True,
                        code_snippet=code,
                        code_explanation=f"Impute missing values in '{col}' with median/mode.",
                        estimated_rows_affected=issue.affected_count,
                        estimated_data_loss=0.0,
                    )
                )
            elif issue.issue_type == "duplicate_rows":
                plans.append(
                    RemediationPlan(
                        issue=issue,
                        remediation_type=RemediationType.DROP_DUPLICATES_KEEP_FIRST,
                        remediation_params={"keep": "first"},
                        safety_rating=SafetyRating.SAFE
                        if issue.affected_percentage < 1
                        else SafetyRating.REVIEW,
                        safety_rationale="Dropping duplicates is standard if they are true duplicates.",
                        auto_apply_recommended=True,
                        code_snippet="df = df.drop_duplicates(keep='first')",
                        code_explanation="Remove duplicate rows, keeping the first occurrence.",
                        estimated_rows_affected=issue.affected_count,
                        estimated_data_loss=0.0,
                    )
                )
        return plans

    def assess_pca_applicability(self, df: pd.DataFrame) -> Optional[PCAConfig]:
        """Assess if PCA should be applied."""
        numeric_cols = df.select_dtypes(include=["number"]).columns
        n_features = len(numeric_cols)

        if n_features > 20:
            return PCAConfig(
                enabled=True, feature_count_threshold=20, use_llm_decision=True
            )
        return None
