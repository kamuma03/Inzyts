from typing import Any, Dict, Optional
import json

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import (
    ProfileToStrategyHandoff,
    StrategyToCodeGenHandoff,
    AnalysisType,
    PreprocessingStep,
    ModelSpec,
    ResultVisualization,
)

# We need a prompt for Dimensionality Strategy
from src.prompts import DIMENSIONALITY_STRATEGY_PROMPT


class DimensionalityStrategyAgent(BaseAgent):
    """
    Dimensionality Strategy Agent for Phase 2.

    Develops a strategy for performing Dimensionality Reduction (PCA).
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="DimensionalityStrategy",
            phase=Phase.PHASE_2,
            system_prompt=DIMENSIONALITY_STRATEGY_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Develop dimensionality reduction strategy.
        """
        # Get locked profile
        profile = state.profile_lock.get_locked_handoff()

        # Build context
        context = self._build_context(profile)

        # Prompt LLM
        prompt = self._build_strategy_prompt(context, state.user_intent)

        try:
            response = self.llm_agent.invoke_with_json(prompt)
            strategy_dict = json.loads(response)
        except Exception:
            # Fallback strategy
            strategy_dict = self._fallback_strategy(profile)

        # Convert to Handoff
        # Use default PCA config if not present, or refine it if needed
        # The strategy format is standard StrategyToCodeGenHandoff

        handoff = StrategyToCodeGenHandoff(
            profile_reference=state.profile_lock.lock_hash,
            analysis_type=AnalysisType.DIMENSIONALITY,
            analysis_objective=strategy_dict.get(
                "analysis_objective", "Reduce dimensionality using PCA"
            ),
            target_column=None,  # Unsupervised
            feature_columns=strategy_dict.get("feature_columns", []),
            preprocessing_steps=[
                PreprocessingStep(**step)
                for step in strategy_dict.get("preprocessing_steps", [])
            ],
            models_to_train=[
                ModelSpec(**model) for model in strategy_dict.get("models_to_train", [])
            ],  # Usually just PCA "model"
            evaluation_metrics=strategy_dict.get(
                "evaluation_metrics", ["explained_variance_ratio"]
            ),
            result_visualizations=[
                ResultVisualization(**viz)
                for viz in strategy_dict.get("result_visualizations", [])
            ],
            conclusion_points=strategy_dict.get("conclusion_points", []),
        )

        return {"handoff": handoff, "confidence": 0.9, "issues": [], "suggestions": []}

    def _build_context(self, profile: ProfileToStrategyHandoff) -> str:
        # Build context (simplified)
        numeric_cols = [
            c.name
            for c in profile.column_profiles
            if "numeric" in c.detected_type.value
        ]
        return f"""
        Analysis Type: DIMENSIONALITY REDUCTION
        Available Feature Columns ({len(numeric_cols)}): {numeric_cols}
        """

    def _build_strategy_prompt(self, context: str, user_intent: Any) -> str:
        return f"""
        Develop a strategy for Principal Component Analysis (PCA).
        
        CONTEXT:
        {context}
        
        Requirements:
        1. Select all appropriate numeric columns.
        2. Preprocessing: Standard Scaling is mandatory.
        3. Model: PCA.
        4. Visualizations: Scree Plot, 2D/3D Scatter of components, Loadings Heatmap.
        
        Return JSON fitting StrategyToCodeGenHandoff structure.
        """

    def _fallback_strategy(self, profile: ProfileToStrategyHandoff) -> Dict[str, Any]:
        numeric_cols = [
            c.name
            for c in profile.column_profiles
            if "numeric" in c.detected_type.value
        ]
        return {
            "analysis_objective": "Perform PCA analysis",
            "feature_columns": numeric_cols,
            "preprocessing_steps": [
                {
                    "step_name": "Imputation",
                    "step_type": "imputation",
                    "target_columns": numeric_cols,
                    "method": "mean",
                    "parameters": {},
                    "rationale": "PCA requires no missing values",
                    "order": 1,
                },
                {
                    "step_name": "Scaling",
                    "step_type": "scaling",
                    "target_columns": numeric_cols,
                    "method": "standard",
                    "parameters": {},
                    "rationale": "PCA requires standardized data",
                    "order": 2,
                },
            ],
            "models_to_train": [
                {
                    "model_name": "PCA",
                    "import_path": "sklearn.decomposition.PCA",
                    "hyperparameters": {"n_components": 0.95},  # Explain 95% variance
                    "rationale": "Reduce dimensions while retaining 95% variance",
                    "priority": 1,
                }
            ],
            "result_visualizations": [
                {
                    "viz_type": "scree_plot",
                    "title": "Scree Plot",
                    "when_applicable": "always",
                },
                {
                    "viz_type": "pca_2d_scatter",
                    "title": "PCA First 2 Components",
                    "when_applicable": "always",
                },
                {
                    "viz_type": "loadings_heatmap",
                    "title": "Component Loadings",
                    "when_applicable": "always",
                },
            ],
        }
