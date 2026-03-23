"""
Strategy Agent - Domain expert for Phase 2.

This agent is the "Brain" of the analysis phase. It consumes the IMMUTABLE
Profile Lock from Phase 1 and designs a complete machine learning or
statistical analysis plan.

Responsibilities:
1. Determine Analysis Type (Regression, Classification, Clustering, etc.).
2. select Target Column (if not specified by user).
3. Adopt Preprocessing Pipeline (Imputation, Encoding, Scaling) from Phase 1.
4. Select Algorithms (e.g., Random Forest vs Linear Regression).
"""

import json
import textwrap
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.prompts import STRATEGY_AGENT_PROMPT
from src.models.state import AnalysisState, Phase
from src.models.handoffs import (
    ProfileToStrategyHandoff,
    StrategyToCodeGenHandoff,
    PreprocessingStep,
    ModelSpec,
    ValidationStrategy,
    ResultVisualization,
    AnalysisType,
    FeatureType,
)
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger()


class StrategyAgent(BaseAgent):
    """
    Strategy Agent for Phase 2.

    Consumes the locked profile (ProfileToStrategyHandoff) and uses it
    to design a structured analysis plan (StrategyToCodeGenHandoff).
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="StrategyAgent",
            phase=Phase.PHASE_2,
            system_prompt=STRATEGY_AGENT_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Design analysis strategy based on locked profile.

        Args:
            state: Current analysis state.
            **kwargs: Must include 'profile_handoff' (ProfileToStrategyHandoff).

        Returns:
            Dictionary containing 'handoff' (StrategyToCodeGenHandoff)
            with the complete analysis plan.
        """
        # Log agent invocation
        logger.agent_execution("StrategyAgent", "invoked")
        logger.phase_transition("phase2", "start")

        profile: ProfileToStrategyHandoff | None = kwargs.get("profile_handoff")

        if profile is None:
            logger.agent_execution(
                "StrategyAgent", "failed", reason="no_profile_handoff"
            )
            return {
                "handoff": None,
                "confidence": 0.0,
                "issues": [
                    self._create_issue(
                        "no_profile",
                        "missing_input",
                        "error",
                        "No locked profile provided",
                    )
                ],
                "suggestions": ["Ensure Phase 1 completes with Profile Lock"],
            }

        # Verify profile lock (Section 8.5 requirement)
        if not state.profile_lock or not state.profile_lock.is_locked():
            logger.warning(
                "Strategy Agent: Profile not locked - possible integrity issue"
            )

        # CACHE CHECK
        from src.utils.cache_manager import CacheManager

        cache_manager = CacheManager()
        csv_hash = cache_manager.get_csv_hash(state.csv_path)

        cached_strategy = None
        if state.using_cached_profile:
            cached_strategy = cache_manager.load_artifact(csv_hash, "analysis_strategy")

        if cached_strategy:
            logger.info(f"Using cached strategy for {state.csv_path}")
            strategy = cached_strategy
        else:
            # Build prompt with profile data
            prompt = self._build_strategy_prompt(profile, state)

            # Get LLM strategy
            try:
                response = self.llm_agent.invoke_with_json(prompt)
                strategy = json.loads(response)
                # Save to cache if successful
                cache_manager.save_artifact(csv_hash, "analysis_strategy", strategy)
            except (json.JSONDecodeError, Exception) as e:
                # Fall back to heuristic strategy
                logger.warning(
                    f"Strategy Agent LLM failed, using heuristic fallback: {str(e)}"
                )
                strategy = self._heuristic_strategy(profile, state)
                # Allow fallback strategy to be cached too?
                # Yes, to avoid repeated failures.
                cache_manager.save_artifact(csv_hash, "analysis_strategy", strategy)

        # Build handoff
        handoff = self._build_handoff(strategy, profile)

        confidence = strategy.get("confidence", 0.8)

        # Log completion
        logger.agent_execution(
            "StrategyAgent",
            "completed",
            analysis_type=handoff.analysis_type.value
            if handoff.analysis_type
            else "unknown",
            models_count=len(handoff.models_to_train),
            confidence=confidence,
        )

        return {
            "handoff": handoff,
            "confidence": confidence,
            "issues": [],
            "suggestions": [],
        }

    def _build_strategy_prompt(
        self, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> str:
        """Build the prompt for strategy generation."""

        # Column summary — exclude pure identifiers and user-excluded columns
        # to reduce prompt size.  Identifiers (e.g. row IDs, UUIDs) carry no
        # analytical value and are never used in modelling.  The full column
        # inventory is still preserved in the locked profile for reference.
        excluded_names = set(
            state.user_intent.exclude_columns if state.user_intent else []
        )
        columns_info = []
        for col in profile.column_profiles:
            if col.name in excluded_names:
                continue
            if col.detected_type.value in ("identifier", "numeric_identifier"):
                continue
            columns_info.append(
                f"  - {col.name}: {col.detected_type.value}, "
                f"unique={col.unique_count}, null={col.null_percentage:.1f}%"
            )

        # Target candidates
        targets_info = []
        for candidate in profile.recommended_target_candidates:
            targets_info.append(
                f"  - {candidate.column_name}: {candidate.suggested_analysis_type.value} "
                f"({candidate.rationale}, confidence: {candidate.confidence})"
            )

        # User intent
        user_intent = ""
        if state.user_intent:
            user_intent = f"""
USER INTENT:
- Question: {state.user_intent.analysis_question or "Not specified"}
- Target Column Hint: {state.user_intent.target_column or "Not specified"}
- Analysis Type Hint: {state.user_intent.analysis_type_hint or "Not specified"}
- Exclude Columns: {state.user_intent.exclude_columns or "None"}
"""

        # Domain Context (v1.8.0)
        domain_context = ""
        if profile.detected_domain:
            d = profile.detected_domain
            domain_context = f"""
DETECTED DOMAIN: {d.domain_name} ({d.description})

DOMAIN CONCEPTS:
{chr(10).join(f"- {c.name}: {c.description}" for c in d.concepts)}

RECOMMENDED ANALYSES:
{chr(10).join(f"- {a.concept} ({a.analysis_type}): {a.description}" for a in d.recommended_analyses)}

DOMAIN KPIS:
{chr(10).join(f"- {k.name}: {k.formula_description}" for k in d.kpis)}
"""

        # Prepare complex strings outside f-string to avoid nesting limit
        dd_str = (
            chr(10).join(f"  - {k}: {v}" for k, v in profile.data_dictionary.items())
            if profile.data_dictionary
            else "  None provided"
        )
        targets_str = (
            chr(10).join(targets_info)
            if targets_info
            else "  No clear candidates identified"
        )
        warnings_str = (
            chr(10).join(f"  - {w}" for w in profile.data_quality_warnings)
            if profile.data_quality_warnings
            else "  None"
        )
        preproc_str = self._format_preprocessing_recommendations(profile)
        # Strip identifiers and excluded columns from feature types dump
        filtered_features = {
            k: v
            for k, v in profile.identified_feature_types.items()
            if k not in excluded_names and v.value not in ("identifier",)
        }
        features_str = json.dumps(dict(filtered_features), indent=2)

        return textwrap.dedent(f"""
            Design an analysis strategy for this LOCKED data profile.

            DATA SUMMARY:
            - Rows: {profile.row_count}
            - Columns: {profile.column_count}
            - Overall Quality Score: {profile.overall_quality_score:.2f}

            COLUMNS:
            {chr(10).join(columns_info)}
            
            DATA DICTIONARY:
            {dd_str}

            TARGET CANDIDATES:
            {targets_str}

                DATA QUALITY WARNINGS:
            {warnings_str}

                REQUIRED PREPROCESSING (FROM PHASE 1):
                {preproc_str}

                FEATURE TYPES:
                {features_str}
                {domain_context}
                {user_intent}

            Design a complete analysis strategy.
            CRITICAL INSTRUCTION: You must ADOPT the 'REQUIRED PREPROCESSING' steps listed above. 
            Do not design new preprocessing steps unless absolutely necessary to fix a critical omission.

            Remember:
            - You CANNOT modify the data profile or column types
            - Work with the data as-is
            - Document any limitations you must work around

            MODEL SPECIFICATION:
            For each model, you may OPTIONALLY include a "tuning_config" to specify hyperparameter search.
            Format for tuning_config:
            {{
                "enabled": true,
                "search_type": "grid",  # or "random"
                "cv_folds": 5,
                "scoring_metric": "accuracy", # or r2, f1, etc.
                "grids": [
                    {{
                        "algorithm_name": "RandomForestClassifier",
                        "param_grid": {{"n_estimators": [100, 200], "max_depth": [None, 10]}}
                    }}
                ]
            }}
            
            Return as JSON with the specified format.
        """)

    def _format_preprocessing_recommendations(
        self, profile: ProfileToStrategyHandoff
    ) -> str:
        """Format preprocessing recommendations for the prompt."""
        if (
            not hasattr(profile, "preprocessing_recommendations")
            or not profile.preprocessing_recommendations
        ):
            return "None"

        formatted = []
        for rec in profile.preprocessing_recommendations:
            formatted.append(
                f"- {rec.step_type.upper()}: {rec.method} on columns {rec.columns} ({rec.rationale})"
            )

        return "\n    ".join(formatted)

    def _heuristic_strategy(
        self, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> Dict[str, Any]:
        """Generate heuristic strategy when LLM fails."""

        # Determine analysis type
        analysis_type = AnalysisType.EXPLORATORY
        target_column = None

        # Use user hint if available
        if state.user_intent and state.user_intent.target_column:
            target_column = state.user_intent.target_column
            if state.user_intent.analysis_type_hint:
                analysis_type = state.user_intent.analysis_type_hint
            else:
                # Infer from target column type
                for col in profile.column_profiles:
                    if col.name == target_column:
                        if col.detected_type.value in ["binary", "categorical"]:
                            analysis_type = AnalysisType.CLASSIFICATION
                        else:
                            analysis_type = AnalysisType.REGRESSION
                        break
        elif profile.recommended_target_candidates:
            # Use first recommended candidate
            candidate = profile.recommended_target_candidates[0]
            target_column = candidate.column_name
            analysis_type = candidate.suggested_analysis_type

        # Identify feature columns (exclude target and identifiers)
        feature_columns = []
        exclude = state.user_intent.exclude_columns if state.user_intent else []
        exclude.append(target_column) if target_column else None

        for col in profile.column_profiles:
            if col.name not in exclude and col.detected_type.value != "identifier":
                feature_columns.append(col.name)

        # Build preprocessing steps
        preprocessing_steps = []
        order = 1

        # Missing value imputation
        cols_with_missing = [
            col.name
            for col in profile.column_profiles
            if col.null_percentage > 0 and col.name in feature_columns
        ]

        if cols_with_missing:
            numeric_missing = [
                c
                for c in cols_with_missing
                if profile.identified_feature_types.get(c)
                in [FeatureType.NUMERIC_CONTINUOUS, FeatureType.NUMERIC_DISCRETE]
            ]
            cat_missing = [c for c in cols_with_missing if c not in numeric_missing]

            if numeric_missing:
                preprocessing_steps.append(
                    {
                        "step_name": "Impute Numeric Missing Values",
                        "step_type": "imputation",
                        "target_columns": numeric_missing,
                        "method": "median",
                        "parameters": {},
                        "rationale": "Median is robust to outliers",
                        "order": order,
                    }
                )
                order += 1

            if cat_missing:
                preprocessing_steps.append(
                    {
                        "step_name": "Impute Categorical Missing Values",
                        "step_type": "imputation",
                        "target_columns": cat_missing,
                        "method": "mode",
                        "parameters": {},
                        "rationale": "Use most frequent value for categorical",
                        "order": order,
                    }
                )
                order += 1

        # Encoding
        cat_columns = [
            name
            for name, ftype in profile.identified_feature_types.items()
            if ftype
            in [
                FeatureType.CATEGORICAL_LOW_CARDINALITY,
                FeatureType.CATEGORICAL_HIGH_CARDINALITY,
            ]
            and name in feature_columns
        ]

        if cat_columns:
            preprocessing_steps.append(
                {
                    "step_name": "Encode Categorical Features",
                    "step_type": "encoding",
                    "target_columns": cat_columns,
                    "method": "one_hot",
                    "parameters": {"drop_first": True},
                    "rationale": "One-hot encoding for categorical variables",
                    "order": order,
                }
            )
            order += 1

        # Scaling
        numeric_columns = [
            name
            for name, ftype in profile.identified_feature_types.items()
            if ftype in [FeatureType.NUMERIC_CONTINUOUS, FeatureType.NUMERIC_DISCRETE]
            and name in feature_columns
        ]

        if numeric_columns:
            preprocessing_steps.append(
                {
                    "step_name": "Scale Numeric Features",
                    "step_type": "scaling",
                    "target_columns": numeric_columns,
                    "method": "standard",
                    "parameters": {},
                    "rationale": "Standardization for numeric stability",
                    "order": order,
                }
            )

        # Model selection
        models_to_train = []

        # Retrieve from registry
        from src.agents.phase2.model_registry import (
            MODEL_REGISTRY,
            METRIC_REGISTRY,
            VIZ_REGISTRY,
        )

        models_to_train = MODEL_REGISTRY.get(analysis_type, [])
        evaluation_metrics = METRIC_REGISTRY.get(analysis_type, [])
        visualizations = list(
            VIZ_REGISTRY.get(analysis_type, [])
        )  # Copy to avoid mutation if we append

        # Add feature importance visualization if valid
        if models_to_train:
            visualizations.append(
                {
                    "viz_type": "feature_importance",
                    "title": "Feature Importance",
                    "when_applicable": "any",
                }
            )

        # Profile limitations
        limitations = list(profile.data_quality_warnings)
        if profile.high_cardinality_columns:
            limitations.append(
                f"High cardinality columns: {', '.join(profile.high_cardinality_columns)}"
            )

        return {
            "analysis_type": analysis_type.value,
            "analysis_objective": f"Perform {analysis_type.value} analysis"
            + (f" to predict {target_column}" if target_column else ""),
            "target_column": target_column,
            "feature_columns": feature_columns,
            "preprocessing_steps": preprocessing_steps,
            "models_to_train": models_to_train,
            "evaluation_metrics": evaluation_metrics,
            "validation_strategy": {
                "method": "train_test_split",
                "parameters": {"test_size": 0.2, "random_state": 42},
            },
            "result_visualizations": visualizations,
            "conclusion_points": [
                "Compare model performance across metrics",
                "Analyze feature importance",
                "Summarize key findings and recommendations",
            ],
            "profile_limitations": limitations,
            "confidence": 0.75,
        }

    def _build_handoff(
        self, strategy: Dict[str, Any], profile: ProfileToStrategyHandoff
    ) -> StrategyToCodeGenHandoff:
        """Build the StrategyToCodeGenHandoff from strategy."""

        preprocessing_steps = []
        for i, step in enumerate(strategy.get("preprocessing_steps", [])):
            if "rationale" not in step:
                step["rationale"] = (
                    f"Automatically generated step for {step.get('step_type', 'preprocessing')}"
                )
            if "order" not in step:
                step["order"] = i + 1
            preprocessing_steps.append(PreprocessingStep(**step))

        models = []
        for i, model in enumerate(strategy.get("models_to_train", [])):
            if "rationale" not in model:
                model["rationale"] = (
                    f"Proposed model strategy: {model.get('model_name', 'Unknown')}"
                )
            if "priority" not in model:
                model["priority"] = i + 1
            models.append(ModelSpec(**model))

        validation = None
        if strategy.get("validation_strategy"):
            validation = ValidationStrategy(**strategy["validation_strategy"])

        visualizations = [
            ResultVisualization(**viz)
            for viz in strategy.get("result_visualizations", [])
        ]

        return StrategyToCodeGenHandoff(
            profile_reference=f"profile_{profile.locked_at.isoformat() if profile.locked_at else 'unknown'}",
            analysis_type=AnalysisType(strategy.get("analysis_type", "exploratory")),
            analysis_objective=strategy.get(
                "analysis_objective", "Perform data analysis"
            ),
            target_column=strategy.get("target_column"),
            feature_columns=strategy.get("feature_columns", []),
            preprocessing_steps=preprocessing_steps,
            models_to_train=models,
            evaluation_metrics=strategy.get("evaluation_metrics", []),
            validation_strategy=validation,
            result_visualizations=visualizations,
            conclusion_points=strategy.get("conclusion_points", []),
            profile_limitations=strategy.get("profile_limitations", []),
        )
