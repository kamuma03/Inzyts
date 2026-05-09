from typing import Any, Dict

import pandas as pd

from src.agents.extensions.base_extension import BaseExtensionAgent
from src.models.handoffs import ComparativeExtension, ProfileToStrategyHandoff
from src.models.state import AnalysisState
from src.prompts import COMPARATIVE_EXTENSION_PROMPT


class ComparativeExtensionAgent(BaseExtensionAgent):
    """Identifies low-cardinality grouping columns + balance ratios for A/B-style comparisons."""

    extension_model = ComparativeExtension
    output_key = "comparative_extension"
    prompt_intro = "Analyze these potential groups and metrics for a comparative analysis/AB test"

    def __init__(self) -> None:
        super().__init__(name="ComparativeExtensionAgent", system_prompt=COMPARATIVE_EXTENSION_PROMPT)

    def compute_features(
        self, df: pd.DataFrame, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> Dict[str, Any]:
        categorical_candidates = [
            c.name for c in profile.column_profiles
            if c.detected_type in ("categorical", "categorical_nominal", "categorical_ordinal", "binary", "categorical_binary")
            and c.unique_count < 20
        ]

        group_summaries: Dict[str, Dict[str, Any]] = {}
        for col in categorical_candidates:
            if col not in df.columns:
                continue
            counts = df[col].value_counts().to_dict()
            min_size = min(counts.values()) if counts else 0
            max_size = max(counts.values()) if counts else 0
            balance_ratio = min_size / max_size if max_size > 0 else 0
            group_summaries[col] = {
                "values": list(counts.keys()),
                "counts": counts,
                "balance_ratio": balance_ratio,
                "is_balanced": balance_ratio > 0.4,
            }

        numeric_cols = [
            c.name for c in profile.column_profiles
            if c.detected_type in ("numeric_continuous", "numeric_discrete")
        ]

        return {
            "group_candidates": group_summaries,
            "numeric_metrics": numeric_cols,
            "_group_summaries": group_summaries,  # consumed by hydrate()
        }

    def hydrate(self, response: ComparativeExtension, computed: Dict[str, Any]) -> ComparativeExtension:
        summaries = computed["_group_summaries"]
        chosen = response.group_column
        if chosen in summaries:
            s = summaries[chosen]
            response.group_sizes = s["counts"]
            response.balance_ratio = s["balance_ratio"]
            response.is_balanced = s["is_balanced"]
            response.group_values = [str(v) for v in s["values"]]
        return response
