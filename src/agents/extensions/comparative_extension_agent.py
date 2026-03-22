from typing import Any, Dict
import pandas as pd

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import ComparativeExtension
from src.prompts import COMPARATIVE_EXTENSION_PROMPT


class ComparativeExtensionAgent(BaseAgent):
    """
    Comparative Extension Agent.
    Analyzes data for A/B testing and group comparison feasibility.
    """

    def __init__(self):
        super().__init__(
            name="ComparativeExtensionAgent",
            phase=Phase.PHASE_1,
            system_prompt=COMPARATIVE_EXTENSION_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Run the comparative analysis extension.
        """
        # 1. Verify Profile Lock
        profile = (
            state.profile_lock.get_locked_handoff()
            if state.profile_lock.is_locked()
            else None
        )
        if not profile:
            return {"error": "Profile not locked, cannot run extension"}

        # 2. Load Data
        if not state.csv_data:
            return {"error": "No CSV data available"}
        try:
            df = pd.DataFrame(state.csv_data)
        except Exception as e:
            return {"error": f"Failed to load dataframe: {e}"}

        # 3. Analyze Potential Group Columns (Low Cardinality Categoricals)
        categorical_candidates = []
        for col_profile in profile.column_profiles:
            if col_profile.detected_type in [
                "categorical",
                "categorical_nominal",
                "categorical_ordinal",
                "binary",
                "categorical_binary",
            ]:
                if col_profile.unique_count < 20:  # Reasonable limit for A/B/n test
                    categorical_candidates.append(col_profile.name)

        group_summaries = {}
        for col in categorical_candidates:
            if col not in df.columns:
                continue
            counts = df[col].value_counts().to_dict()

            # Simple balance check
            min_size = min(counts.values()) if counts else 0
            max_size = max(counts.values()) if counts else 0
            balance_ratio = min_size / max_size if max_size > 0 else 0

            group_summaries[col] = {
                "values": list(counts.keys()),
                "counts": counts,
                "balance_ratio": balance_ratio,
                "is_balanced": balance_ratio > 0.4,  # Loose threshold
            }

        # 4. Prepare Context for LLM
        numeric_cols = [
            c.name
            for c in profile.column_profiles
            if c.detected_type in ["numeric_continuous", "numeric_discrete"]
        ]

        context = {
            "group_candidates": group_summaries,
            "numeric_metrics": numeric_cols,
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }

        # 5. Execute LLM
        response_str = self.llm_agent.invoke_with_json(
            prompt=f"Analyze these potential groups and metrics for a comparative analysis/AB test: {context}"
        )

        try:
            response = ComparativeExtension.model_validate_json(response_str)
        except Exception as e:
            print(f"JSON Validation failed: {e}")
            raise e

        # 6. Hydrate Response with exact calculations
        selected_group_col = response.group_column
        if selected_group_col in group_summaries:
            summary = group_summaries[selected_group_col]
            response.group_sizes = summary["counts"]
            response.balance_ratio = summary["balance_ratio"]
            response.is_balanced = summary["is_balanced"]
            # Ensure group values match actual data
            response.group_values = [str(v) for v in summary["values"]]

        return {"comparative_extension": response, "confidence": 1.0}
