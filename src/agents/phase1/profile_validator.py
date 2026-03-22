"""
Profile Validator Agent - QA specialist for Phase 1.

The Validator acts as the pipeline's circuit breaker. It:
1. Static Analysis: Checks generated code for syntax errors.
2. Content Validation: Ensures generated code meets the Profiler's requirements
   (e.g., did it generate the histogram we asked for?).
3. Profile Locking: Decides if Phase 1 is complete ("Locked") or if we need
   to recurse back to fix issues.
4. Strategy Prep: If successful, it performs a deep scan of the data to prepare
   a rich context for the Phase 2 Strategy Agent.
"""

import ast
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import BaseAgent
from src.agents.validation_utils import (
    validate_syntax,
    count_visualizations,
    calculate_pep8_score,
    lint_line,
)
from src.models.state import AnalysisState, Phase
from src.models.common import Issue
from src.models.cells import NotebookCell
from src.models.handoffs import (
    ProfileCodeToValidatorHandoff,
    ProfileToStrategyHandoff,
    ColumnProfile,
    TargetCandidate,
    NumericStats,
    DataType,
    FeatureType,
    AnalysisType,
)
from src.models.validation import (
    ProfileValidationResult,
    ValidationReport,
    calculate_phase1_quality,
)
from src.services.sandbox_executor import SandboxExecutor
from src.utils.logger import get_logger

logger = get_logger()


class ProfileValidatorAgent(BaseAgent):
    """
    Profile Validator Agent for Phase 1.

    Validates Profile Code Generator output and determines
    if Profile Lock should be granted.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="ProfileValidator",
            phase=Phase.PHASE_1,
            system_prompt="You are a Profile Validator Agent.",  # Not heavily LLM-dependent
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Validate profile code and determine lock status.

        Args:
            state: Current analysis state.
            **kwargs: Must include 'code_handoff' (ProfileCodeToValidatorHandoff).

        Returns:
            Dictionary with validation results, quality scores, and the
            crucial 'should_lock' boolean.
        """
        # Log agent invocation
        logger.agent_execution("ProfileValidator", "invoked")

        code_handoff: ProfileCodeToValidatorHandoff | None = kwargs.get("code_handoff")

        if code_handoff is None:
            logger.agent_execution(
                "ProfileValidator", "failed", reason="no_code_handoff"
            )
            return {
                "validation_result": None,
                "report": None,
                "strategy_handoff": None,
                "confidence": 0.0,
                "issues": [
                    self._create_issue(
                        "no_code", "missing_input", "error", "No code handoff provided"
                    )
                ],
                "suggestions": ["Ensure Profile Code Generator runs first"],
            }

        # Validate cells
        validation_result = self._validate_cells(code_handoff, state)

        # Calculate quality score
        quality_score, should_lock = calculate_phase1_quality(validation_result)

        # Build validation report with routing decision
        report = self._build_report(
            validation_result, quality_score, should_lock, state
        )

        # Build strategy handoff if lock is granted
        strategy_handoff = None
        if should_lock:
            strategy_handoff = self._build_strategy_handoff(
                code_handoff, validation_result, quality_score, state
            )

        # Log validation result
        logger.validation(
            "phase1",
            passed=should_lock,
            quality_score=quality_score,
            issues_count=len(validation_result.issues),
        )

        # Log Profile Lock decision
        logger.profile_lock(granted=should_lock, quality_score=quality_score)

        # Log completion
        logger.agent_execution(
            "ProfileValidator",
            "completed",
            should_lock=should_lock,
            quality_score=quality_score,
        )

        return {
            "validation_result": validation_result,
            "report": report,
            "strategy_handoff": strategy_handoff,
            "quality_score": quality_score,
            "should_lock": should_lock,
            "confidence": 0.9 if should_lock else 0.6,
            "issues": validation_result.issues,
            "suggestions": report.suggestions,
        }

    def _validate_cells(
        self, code_handoff: ProfileCodeToValidatorHandoff, state: AnalysisState
    ) -> ProfileValidationResult:
        """Validate all cells in the code handoff."""
        cells = code_handoff.cells
        issues: List[Issue] = []

        cells_passed = 0
        viz_count = 0
        markdown_sections: List[str] = []
        min_confidence = 1.0
        stats_columns: List[str] = []

        with SandboxExecutor(execution_timeout=120) as executor:
            for idx, cell in enumerate(cells):
                try:
                    if cell.cell_type == "code":
                        # Validate Python syntax
                        is_valid, error = self._validate_syntax(cell.source)
                        if is_valid:
                            # Execute the code in the sandbox
                            exec_result = executor.execute_cell(cell.source)
                            if exec_result.success:
                                cells_passed += 1
                                # Count visualizations (simple heuristic still okay if it runs)
                                viz_count += self._count_visualizations(cell.source)
                                # Check for statistics
                                if "describe" in cell.source or "corr" in cell.source:
                                    stats_columns.extend(
                                        self._extract_stat_columns(cell.source)
                                    )
                            else:
                                issues.append(
                                    self._create_issue(
                                        f"runtime_error_{idx}",
                                        "runtime_error",
                                        "error",
                                        f"Cell {idx} failed to execute: {exec_result.error_name}: {exec_result.error_value}",
                                        f"cell_{idx}",
                                    )
                                )
                        else:
                            issues.append(
                                self._create_issue(
                                    f"syntax_error_{idx}",
                                    "syntax_error",
                                    "error",
                                    f"Cell {idx} syntax error: {error}",
                                    f"cell_{idx}",
                                )
                            )
                    else:
                        cells_passed += 1
                        # Extract markdown section titles
                        section = self._extract_markdown_section(cell.source)
                        if section:
                            markdown_sections.append(section)

                except Exception as e:
                    issues.append(
                        self._create_issue(
                            f"validation_error_{idx}",
                            "system_error",
                            "error",
                            f"Cell {idx} validation system failed: {str(e)}",
                            f"cell_{idx}",
                        )
                    )

        # Get type detection confidence from spec
        spec = code_handoff.source_specification
        type_confidences = [col.detection_confidence for col in spec.columns]
        min_confidence = min(type_confidences) if type_confidences else 0.0
        low_confidence_cols = [
            col.name for col in spec.columns if col.detection_confidence < 0.7
        ]

        # Calculate stats coverage
        total_numeric = len(
            [
                col
                for col in spec.columns
                if col.detected_type
                in [DataType.NUMERIC_CONTINUOUS, DataType.NUMERIC_DISCRETE]
            ]
        )
        if "all_numeric" in stats_columns:
            stats_coverage = 1.0
        else:
            stats_coverage = (
                1.0
                if total_numeric == 0
                else min(len(set(stats_columns)) / max(total_numeric, 1), 1.0)
            )

        # Required report sections
        required_sections = [
            "Data Profiling Report",
            "Data Overview",
            "Statistics",
            "Quality",
        ]
        sections_present = sum(
            1
            for req in required_sections
            if any(req.lower() in sec.lower() for sec in markdown_sections)
        )

        # Calculate PEP8 score (enhanced v0.10.0)
        pep8_score = self._calculate_pep8_score(cells)

        # Check encoding consistency (v0.10.0)
        encoding_score, encoding_issues = self._check_encoding_consistency(cells, spec)
        for enc_issue in encoding_issues:
            issues.append(
                self._create_issue(
                    "encoding_consistency",
                    "encoding_warning",
                    "warning",
                    enc_issue,
                    "encoding",
                )
            )

        # Performance linting (v0.10.0)
        perf_score, perf_warnings = self._performance_linting(cells)
        for perf_warn in perf_warnings:
            issues.append(
                self._create_issue(
                    "performance",
                    "performance_warning",
                    "warning",
                    perf_warn,
                    "performance",
                )
            )

        # Log enhanced validation metrics
        logger.info(
            f"Enhanced Validation: PEP8={pep8_score:.2f}, "
            f"Encoding={encoding_score:.2f}, Performance={perf_score:.2f}"
        )

        # Check for preprocessing recommendations
        prep_recs_count = len(getattr(spec, "preprocessing_recommendations", []))

        return ProfileValidationResult(
            cells_passed=cells_passed,
            total_cells=len(cells),
            min_type_confidence=min_confidence,
            columns_with_low_confidence=low_confidence_cols,
            stats_coverage=stats_coverage,
            viz_count=viz_count,
            viz_failures=[],
            preprocessing_recommendations_count=prep_recs_count,  # Kept for observation/metadata, but unused in scoring
            report_sections_present=sections_present,
            report_sections_required=len(required_sections),
            pep8_score=pep8_score,
            style_issues=[],
            issues=issues,
        )

    def _validate_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax."""
        return validate_syntax(code)

    _PROFILE_VIZ_PATTERNS = [
        "plt.show()",
        ".plot(",
        "sns.",
        "plt.figure(",
        "plt.subplot",
        ".hist(",
        ".bar(",
        ".scatter(",
        "heatmap(",
        "boxplot(",
    ]

    def _count_visualizations(self, code: str) -> int:
        """Count visualization calls in code."""
        return count_visualizations(code, self._PROFILE_VIZ_PATTERNS, cap=5)

    def _extract_stat_columns(self, code: str) -> List[str]:
        """Extract column names from statistics code."""
        # Simplified extraction - in production would parse AST
        columns = []
        if "describe" in code:
            columns.append("all_numeric")
        if "corr" in code:
            columns.append("correlation")
        return columns

    def _extract_markdown_section(self, source: str) -> Optional[str]:
        """Extract section title from markdown."""
        lines = source.split("\n")
        for line in lines:
            if line.startswith("#"):
                return line.strip("#").strip()
        return None

    def _check_encoding_consistency(
        self, cells: List[NotebookCell], spec
    ) -> Tuple[float, List[str]]:
        """
        Check encoding consistency across Phase 1 (v0.10.0 Enhanced).

        Validates:
        - Categorical encoding methods mentioned in code
        - One-hot encoding for low-cardinality categoricals
        - Label encoding for ordinals
        - Consistency with profiler's recommendations

        Returns:
            (consistency_score, issues_list)
        """
        encoding_issues = []
        encoding_methods = []

        # Extract encoding patterns from code
        for cell in cells:
            if cell.cell_type == "code":
                code = cell.source.lower()

                if "onehotencoder" in code or "get_dummies" in code:
                    encoding_methods.append("one-hot")
                if "labelencoder" in code or "factorize" in code:
                    encoding_methods.append("label")
                if "ordinalencoder" in code:
                    encoding_methods.append("ordinal")

        # Check categorical columns
        categorical_cols = [
            col
            for col in spec.columns
            if col.detected_type
            in [DataType.CATEGORICAL_NOMINAL, DataType.CATEGORICAL_ORDINAL]
        ]

        for col in categorical_cols:
            # High cardinality (>10 unique) should not use one-hot
            if hasattr(col, "unique_count") and col.unique_count:
                if col.unique_count > 10 and "one-hot" in encoding_methods:
                    encoding_issues.append(
                        f"Column '{col.name}' has high cardinality ({col.unique_count}), "
                        f"one-hot encoding may be inefficient"
                    )

                # Ordinal columns should use ordinal/label encoding
                if col.detected_type == DataType.CATEGORICAL_ORDINAL:
                    if (
                        "one-hot" in encoding_methods
                        and "ordinal" not in encoding_methods
                    ):
                        encoding_issues.append(
                            f"Ordinal column '{col.name}' should use ordinal encoding, not one-hot"
                        )

        # Calculate consistency score
        if len(categorical_cols) == 0:
            consistency_score = 1.0  # No categoricals, perfect consistency
        else:
            # Penalize based on issues
            consistency_score = max(0.0, 1.0 - (len(encoding_issues) * 0.15))

        return consistency_score, encoding_issues

    def _performance_linting(
        self, cells: List[NotebookCell]
    ) -> Tuple[float, List[str]]:
        """
        Performance linting for generated code using AST analysis.

        Checks for:
        - Inefficient loops (iterating over DataFrame rows)
        - Missing vectorization opportunities
        - Unnecessary memory allocations
        - DataFrame copying issues

        Returns:
            (performance_score, warnings_list)
        """
        perf_warnings = []
        total_checks = 0
        issues_found = 0.0

        for cell in cells:
            if cell.cell_type != "code":
                continue

            code = cell.source

            # Try AST-based analysis first
            try:
                tree = ast.parse(code)
                cell_warnings, cell_issues = self._analyze_ast_for_performance(
                    tree, code
                )
                perf_warnings.extend(cell_warnings)
                total_checks += len(cell_warnings) + 1  # At least 1 for attempting
                issues_found += cell_issues
            except SyntaxError:
                # Fall back to simple string checks for invalid syntax
                lines = code.split("\n")
                for i, line in enumerate(lines):
                    if ".iterrows()" in line:
                        total_checks += 1
                        issues_found += 1
                        perf_warnings.append(
                            f"Line {i + 1}: Avoid .iterrows(), use vectorized operations"
                        )

        # Calculate performance score
        if total_checks == 0:
            performance_score = 1.0
        else:
            performance_score = max(0.0, 1.0 - (issues_found / max(1, total_checks)))

        return performance_score, perf_warnings

    def _analyze_ast_for_performance(
        self, tree: ast.AST, source: str
    ) -> Tuple[List[str], float]:
        """
        Analyze AST for performance issues.

        Returns:
            (warnings_list, issue_count)
        """
        warnings = []
        issues = 0.0

        for node in ast.walk(tree):
            # Check for .iterrows() and .itertuples() calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    lineno = getattr(node, "lineno", 0)

                    if method_name == "iterrows":
                        warnings.append(
                            f"Line {lineno}: Avoid .iterrows(), use vectorized operations or .apply()"
                        )
                        issues += 1.0
                    elif method_name == "itertuples":
                        warnings.append(
                            f"Line {lineno}: Consider vectorized operations instead of .itertuples()"
                        )
                        issues += 0.5

            # Check for .copy() inside For loops
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if (
                            isinstance(child.func, ast.Attribute)
                            and child.func.attr == "copy"
                        ):
                            lineno = getattr(child, "lineno", 0)
                            warnings.append(
                                f"Line {lineno}: Avoid .copy() inside loops, causes unnecessary memory allocation"
                            )
                            issues += 1.0

            # Check for += string concatenation in loops
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.AugAssign) and isinstance(
                        child.op, ast.Add
                    ):
                        if isinstance(child.value, ast.Constant) and isinstance(
                            child.value.value, str
                        ):
                            lineno = getattr(child, "lineno", 0)
                            warnings.append(
                                f"Line {lineno}: String concatenation in loop, consider list.append() + join()"
                            )
                            issues += 0.5

        return warnings, issues

    def _calculate_pep8_score(self, cells: List[NotebookCell]) -> float:
        """Calculate comprehensive PEP8 compliance score."""
        return calculate_pep8_score(cells, lint_fn=lint_line)

    def _build_report(
        self,
        result: ProfileValidationResult,
        quality_score: float,
        should_lock: bool,
        state: AnalysisState,
    ) -> ValidationReport:
        """Build validation report with routing decision."""
        issues = result.issues
        suggestions: List[str] = []

        # Use centralized routing logic
        from src.workflow.routing import route_phase1_recursion

        next_agent, reason = route_phase1_recursion(result, state)

        if next_agent is None:
            # Grant lock
            route_to = "GRANT_LOCK"
            route_reason = "Phase 1 quality threshold met"
        else:
            route_to = next_agent
            route_reason = reason

            # Add specific suggestions based on next agent
            if next_agent == "DataProfiler":
                suggestions.append("Review column type detection and data patterns")
            elif next_agent == "ProfileCodeGenerator":
                suggestions.append("Fix syntax errors and improve code coverage")

        # Add specific suggestions based on results
        if result.min_type_confidence < 0.7:
            suggestions.append(
                f"Improve type detection for: {', '.join(result.columns_with_low_confidence)}"
            )
        if result.viz_count < 3:
            suggestions.append(
                f"Add more visualizations (current: {result.viz_count}, required: 3)"
            )
        if result.stats_coverage < 1.0:
            suggestions.append(
                "Ensure statistics are generated for all numeric columns"
            )

        return ValidationReport(
            phase="phase1",
            passed=should_lock,
            quality_score=quality_score,
            execution_success=result.cells_passed == result.total_cells,
            all_criteria_met=should_lock,
            issues=issues,
            route_to=route_to,
            route_reason=route_reason,
            suggestions=suggestions,
        )

    def _build_strategy_handoff(
        self,
        code_handoff: ProfileCodeToValidatorHandoff,
        validation_result: ProfileValidationResult,
        quality_score: float,
        state: AnalysisState,
    ) -> ProfileToStrategyHandoff:
        """Build the locked handoff for Phase 2."""
        from datetime import datetime
        import pandas as pd

        spec = code_handoff.source_specification

        # Extract preprocessing recommendations (if any)
        # Handle backward compatibility if attribute missing in runtime object
        prep_recommendations = getattr(spec, "preprocessing_recommendations", [])

        # Load data for additional analysis
        df = getattr(state, "_df", None)
        if df is None:
            try:
                from src.utils.file_utils import load_csv_robust

                df = load_csv_robust(state.csv_path)
            except Exception as e:
                logger.warning(f"Failed to load CSV for profile verification: {e}")
                df = None

        # Identify target candidates

        # Build missing value summary first
        missing_summary: Dict[str, float] = {}
        if df is not None:
            missing_summary = {
                str(k): float(v)
                for k, v in (df.isnull().mean() * 100).to_dict().items()
            }

        # Build column profiles
        column_profiles = []
        for col in spec.columns:
            stats = None
            null_pct = 0.0
            unique_count = 0
            sample_values: List[Any] = []

            if df is not None and col.name in df.columns:
                null_pct = missing_summary.get(col.name, 0.0)
                unique_count = df[col.name].nunique()
                sample_values = df[col.name].dropna().head(5).tolist()

                if col.detected_type in [
                    DataType.NUMERIC_CONTINUOUS,
                    DataType.NUMERIC_DISCRETE,
                ]:
                    is_numeric_actual = pd.api.types.is_numeric_dtype(df[col.name])
                    stats = NumericStats(
                        mean=df[col.name].mean() if is_numeric_actual else None,
                        median=df[col.name].median() if is_numeric_actual else None,
                        std=df[col.name].std() if is_numeric_actual else None,
                        min=df[col.name].min()
                        if pd.api.types.is_numeric_dtype(df[col.name])
                        else None,
                        max=df[col.name].max()
                        if pd.api.types.is_numeric_dtype(df[col.name])
                        else None,
                    )

            column_profiles.append(
                ColumnProfile(
                    name=col.name,
                    detected_type=col.detected_type,
                    detection_confidence=col.detection_confidence,
                    unique_count=unique_count,
                    null_percentage=null_pct,
                    sample_values=sample_values[:5],
                    statistics=stats,
                )
            )

        # Already computed missing_summary above

        # Identify target candidates
        target_candidates = []
        for profile in column_profiles:
            if profile.detected_type == DataType.BINARY:
                target_candidates.append(
                    TargetCandidate(
                        column_name=profile.name,
                        suggested_analysis_type=AnalysisType.CLASSIFICATION,
                        rationale="Binary column suitable for classification",
                        confidence=0.8,
                    )
                )
            elif (
                profile.detected_type == DataType.CATEGORICAL
                and profile.unique_count < 10
            ):
                target_candidates.append(
                    TargetCandidate(
                        column_name=profile.name,
                        suggested_analysis_type=AnalysisType.CLASSIFICATION,
                        rationale="Low-cardinality categorical suitable for classification",
                        confidence=0.7,
                    )
                )
            elif profile.detected_type == DataType.NUMERIC_CONTINUOUS:
                target_candidates.append(
                    TargetCandidate(
                        column_name=profile.name,
                        suggested_analysis_type=AnalysisType.REGRESSION,
                        rationale="Continuous numeric column suitable for regression",
                        confidence=0.6,
                    )
                )

        # Map column types to feature types
        feature_types = {}
        for profile in column_profiles:
            if profile.detected_type == DataType.NUMERIC_CONTINUOUS:
                feature_types[profile.name] = FeatureType.NUMERIC_CONTINUOUS
            elif profile.detected_type == DataType.NUMERIC_DISCRETE:
                feature_types[profile.name] = FeatureType.NUMERIC_DISCRETE
            elif profile.detected_type == DataType.CATEGORICAL:
                if profile.unique_count > 20:
                    feature_types[profile.name] = (
                        FeatureType.CATEGORICAL_HIGH_CARDINALITY
                    )
                else:
                    feature_types[profile.name] = (
                        FeatureType.CATEGORICAL_LOW_CARDINALITY
                    )
            elif profile.detected_type == DataType.BINARY:
                feature_types[profile.name] = FeatureType.BINARY
            elif profile.detected_type == DataType.DATETIME:
                feature_types[profile.name] = FeatureType.DATETIME
            elif profile.detected_type == DataType.TEXT:
                feature_types[profile.name] = FeatureType.TEXT
            elif profile.detected_type == DataType.IDENTIFIER:
                feature_types[profile.name] = FeatureType.IDENTIFIER

        # Identify temporal columns
        temporal_cols = [
            p.name for p in column_profiles if p.detected_type == DataType.DATETIME
        ]

        # Identify high cardinality columns
        high_card_cols = [p.name for p in column_profiles if p.unique_count > 50]

        # Calculate overall quality score
        overall_quality = (
            1.0 - (sum(missing_summary.values()) / (len(missing_summary) * 100))
            if missing_summary
            else 1.0
        )

        # Data quality warnings
        warnings = []
        for m_col, pct in missing_summary.items():
            if pct > 20:
                warnings.append(f"High missing values in {m_col}: {pct:.1f}%")

        return ProfileToStrategyHandoff(
            lock_status="locked",
            locked_at=datetime.now(),
            phase1_quality_score=quality_score,
            row_count=spec.row_count,
            column_count=spec.column_count,
            column_profiles=tuple(column_profiles),
            overall_quality_score=overall_quality,
            missing_value_summary=missing_summary,
            data_quality_warnings=tuple(warnings),
            recommended_target_candidates=tuple(target_candidates[:3]),
            identified_feature_types=feature_types,
            temporal_columns=tuple(temporal_cols),
            high_cardinality_columns=tuple(high_card_cols),
            correlation_matrix=None,  # Would be computed from actual execution
            detected_patterns=tuple(),
            data_dictionary=(
                state.user_intent.data_dictionary
                if state.user_intent and state.user_intent.data_dictionary
                else {}
            ),
            preprocessing_recommendations=tuple(prep_recommendations),
            profile_cells=tuple(code_handoff.cells),
        )
