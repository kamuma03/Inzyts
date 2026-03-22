from datetime import datetime
from typing import Any, Dict
import pandas as pd
import numpy as np

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import DiagnosticExtension
from src.prompts import DIAGNOSTIC_EXTENSION_PROMPT


class DiagnosticExtensionAgent(BaseAgent):
    """
    Diagnostic Extension Agent.
    Analyzes data for root cause and diagnostic feasibility.
    """

    def __init__(self):
        super().__init__(
            name="DiagnosticExtensionAgent",
            phase=Phase.PHASE_1,
            system_prompt=DIAGNOSTIC_EXTENSION_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Run the diagnostic analysis extension.
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

        # 3. Detect Temporal Column
        date_col = None
        for col_profile in profile.column_profiles:
            if col_profile.detected_type.lower() == "datetime":
                date_col = col_profile.name
                break

        # 4. Perform Anomaly/Change Point Detection
        detected_anomalies = []
        detected_change_points = []

        # Select numeric metrics
        metric_cols = [
            c.name
            for c in profile.column_profiles
            if c.detected_type in ["numeric_continuous", "numeric_discrete"]
        ]

        if date_col:
            try:
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.sort_values(date_col)

                # Check metrics for shifts
                for col in metric_cols[:5]:  # Check top 5 metrics to avoid overload
                    series = df[col].fillna(method="ffill")

                    # Simple Change Point: Rolling Mean Shift
                    rolling_mean = series.rolling(window=7, min_periods=1).mean()
                    pct_change = rolling_mean.pct_change()

                    # Threshold: > 50% change in rolling mean
                    corrections = pct_change[abs(pct_change) > 0.5]
                    for idx, val in corrections.items():
                        ts = df.loc[idx, date_col]
                        detected_change_points.append(
                            {
                                "timestamp": str(ts),
                                "metric": col,
                                "magnitude": float(val),
                                "direction": "increase" if val > 0 else "decrease",
                            }
                        )

                    # Simple Anomaly: Z-score > 3
                    z_score = (series - series.mean()) / series.std()
                    anomalies = z_score[abs(z_score) > 3]
                    for idx, val in anomalies.items():
                        ts = df.loc[idx, date_col]
                        detected_anomalies.append(
                            {
                                "timestamp": str(ts),
                                "metric": col,
                                "severity": float(abs(val)),
                                "description": f"Z-score {val:.2f}",
                            }
                        )

            except Exception as e:
                print(f"Diagnostic date processing failed: {e}")
        else:
            # Non-temporal checks (Distributional outliers)
            for col in metric_cols[:5]:
                series = df[col]
                # Z-score > 3
                if np.issubdtype(series.dtype, np.number):
                    z_score = (series - series.mean()) / series.std()
                    anomalies = z_score[abs(z_score) > 3]
                    # Limit to top 5 anomalies per col
                    for idx, val in anomalies.head(5).items():
                        detected_anomalies.append(
                            {
                                "timestamp": datetime.now(),  # Placeholder for "row index" effectively
                                "metric": col,
                                "severity": float(abs(val)),
                                "description": f"Value {series[idx]} is outlier (Z={val:.2f})",
                            }
                        )

        # 5. Prepare Context for LLM
        context = {
            "has_temporal_data": bool(date_col),
            "temporal_column": date_col,
            "metric_candidates": metric_cols,
            "detected_change_points_summary": f"Found {len(detected_change_points)} potential change points.",
            "detected_anomalies_summary": f"Found {len(detected_anomalies)} potential anomalies.",
            "top_anomalies": detected_anomalies[:5],
            "top_change_points": detected_change_points[:5],
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }

        # 6. Execute LLM
        response_str = self.llm_agent.invoke_with_json(
            prompt=f"Analyze these anomalies and metrics to suggest a diagnostic root cause analysis: {context}"
        )

        try:
            response = DiagnosticExtension.model_validate_json(response_str)
        except Exception as e:
            # Fallback or re-raise. For now re-raise to see errors in tests
            print(f"JSON Validation failed: {e}")
            print(f"Response was: {response_str}")
            raise e

        # 7. Hydrate Response
        # We manually attach the full list of detected points if the LLM didn't return them all (it likely won't return strict objects)
        # Actually, predicting the 'DiagnosticExtension' model means the LLM attempts to construct the List[Anomaly].
        # We should trust the LLM's selection or merge?
        # Let's trust the LLM to filter the "Top" ones from context, but we ensure the structure is valid.
        # If LLM returns empty list but we found some, maybe we should warn?
        # For this implementation, we rely on the LLM to pick the *meaningful* ones from the context we provided.

        return {"diagnostic_extension": response, "confidence": 1.0}
