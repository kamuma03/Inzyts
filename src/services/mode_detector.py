"""
Mode Detector Service.

Handles the logic for determining the appropriate analysis pipeline mode
based on user input (explicit args, target columns, question keywords).
"""

from typing import Optional, Tuple
from src.models.handoffs import PipelineMode


class ModeDetector:
    """
    Service to determine the pipeline execution mode.
    """

    @staticmethod
    def determine_mode(
        mode_arg: Optional[str],
        target_column: Optional[str],
        user_question: Optional[str],
    ) -> Tuple[PipelineMode, str]:
        """
        Determine the pipeline mode based on inputs.

        Priority:
        1. Explicit Argument --mode
        2. Target Column Presence -> PREDICTIVE (Implied)
        3. LLM Inference / Keyword Matching from Question
        4. Default -> EXPLORATORY

        Args:
            mode_arg: Explicit mode string from CLI or API.
            target_column: Target column name if provided.
            user_question: User's natural language question.

        Returns:
            Tuple containing the detected PipelineMode and the method used for detection.
        """
        # 1. Explicit Override
        if mode_arg:
            try:
                mode_map = {
                    "pred": PipelineMode.PREDICTIVE,
                    "predictive": PipelineMode.PREDICTIVE,
                    "exp": PipelineMode.EXPLORATORY,
                    "exploratory": PipelineMode.EXPLORATORY,
                    "diag": PipelineMode.DIAGNOSTIC,
                    "diagnostic": PipelineMode.DIAGNOSTIC,
                    "comp": PipelineMode.COMPARATIVE,
                    "comparative": PipelineMode.COMPARATIVE,
                    "forecast": PipelineMode.FORECASTING,
                    "forecasting": PipelineMode.FORECASTING,
                    "seg": PipelineMode.SEGMENTATION,
                    "segmentation": PipelineMode.SEGMENTATION,
                    "dim": PipelineMode.DIMENSIONALITY,
                    "dimensionality": PipelineMode.DIMENSIONALITY,
                    "pca": PipelineMode.DIMENSIONALITY,
                }

                return mode_map.get(
                    mode_arg.lower(), PipelineMode.EXPLORATORY
                ), "explicit"
            except ValueError:
                pass  # Fallback

        # 2. Implied by Target Column (if not explicitly overridden)
        if target_column:
            return PipelineMode.PREDICTIVE, "target_column"

        # 3. Inference from Question
        if user_question:
            q = user_question.lower()

            # Forecasting signals
            if any(
                k in q
                for k in [
                    "forecast",
                    "future",
                    "predict next",
                    "time series",
                    "prophet",
                ]
            ):
                return PipelineMode.FORECASTING, "inferred_keyword"

            # Diagnostic signals
            if any(
                k in q
                for k in [
                    "why did",
                    "root cause",
                    "explain the drop",
                    "explain the increase",
                    "what drove",
                    "drivers of",
                ]
            ):
                return PipelineMode.DIAGNOSTIC, "inferred_keyword"

            # Comparative signals
            if any(
                k in q
                for k in [
                    "compare",
                    "ab test",
                    "a/b",
                    "lift",
                    "experiment",
                    "control",
                    "treatment",
                ]
            ):
                return PipelineMode.COMPARATIVE, "inferred_keyword"

            # Segmentation signals
            if any(
                k in q
                for k in ["segment", "cluster", "group users", "customer persona"]
            ):
                return PipelineMode.SEGMENTATION, "inferred_keyword"

            # Predictive signals (general)
            if any(k in q for k in ["classify", "predict", "model", "regression"]):
                return PipelineMode.PREDICTIVE, "inferred_keyword"

            # Dimensionality signals
            if any(
                k in q
                for k in [
                    "dimensionality",
                    "pca",
                    "reduction",
                    "compress features",
                    "principal component",
                ]
            ):
                return PipelineMode.DIMENSIONALITY, "inferred_keyword"

        # 4. Default
        return PipelineMode.EXPLORATORY, "default"
