from datetime import datetime
from typing import Any, Dict

import numpy as np
import pandas as pd

from src.agents.extensions.base_extension import BaseExtensionAgent, logger
from src.models.handoffs import DataType, DiagnosticExtension, ProfileToStrategyHandoff
from src.models.state import AnalysisState
from src.prompts import DIAGNOSTIC_EXTENSION_PROMPT

_NUMERIC_TYPES = (DataType.NUMERIC_CONTINUOUS, DataType.NUMERIC_DISCRETE)


class DiagnosticExtensionAgent(BaseExtensionAgent):
    """Detects change-points + anomalies (temporal or distributional) for root-cause analysis."""

    extension_model = DiagnosticExtension
    output_key = "diagnostic_extension"
    prompt_intro = "Analyze these anomalies and metrics to suggest a diagnostic root cause analysis"

    def __init__(self) -> None:
        super().__init__(name="DiagnosticExtensionAgent", system_prompt=DIAGNOSTIC_EXTENSION_PROMPT)

    def compute_features(
        self, df: pd.DataFrame, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> Dict[str, Any]:
        date_col = next(
            (c.name for c in profile.column_profiles if c.detected_type == DataType.DATETIME),
            None,
        )
        metric_cols = [
            c.name for c in profile.column_profiles
            if c.detected_type in _NUMERIC_TYPES
        ]

        anomalies: list = []
        change_points: list = []

        if date_col:
            try:
                # Work on a copy — never mutate the caller's frame in place.
                df = df.copy()
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.sort_values(date_col)
                # Top-5 metrics only — keep prompt context tight.
                for col in metric_cols[:5]:
                    series = df[col].ffill()
                    rolling_mean = series.rolling(window=7, min_periods=1).mean()
                    pct_change = rolling_mean.pct_change()
                    for idx, val in pct_change[abs(pct_change) > 0.5].items():
                        change_points.append({
                            "timestamp": str(df.loc[idx, date_col]),
                            "metric": col,
                            "magnitude": float(val),
                            "direction": "increase" if val > 0 else "decrease",
                        })
                    z = (series - series.mean()) / series.std()
                    for idx, val in z[abs(z) > 3].items():
                        anomalies.append({
                            "timestamp": str(df.loc[idx, date_col]),
                            "metric": col,
                            "severity": float(abs(val)),
                            "description": f"Z-score {val:.2f}",
                        })
            except Exception as e:
                logger.error(f"Diagnostic date processing failed: {e}")
        else:
            # Distributional outliers for non-temporal data.
            for col in metric_cols[:5]:
                series = df[col]
                if not np.issubdtype(series.dtype, np.number):
                    continue
                z = (series - series.mean()) / series.std()
                for idx, val in z[abs(z) > 3].head(5).items():
                    anomalies.append({
                        "timestamp": datetime.now(),
                        "metric": col,
                        "severity": float(abs(val)),
                        "description": f"Value {series[idx]} is outlier (Z={val:.2f})",
                    })

        return {
            "has_temporal_data": bool(date_col),
            "temporal_column": date_col,
            "metric_candidates": metric_cols,
            "detected_change_points_summary": f"Found {len(change_points)} potential change points.",
            "detected_anomalies_summary": f"Found {len(anomalies)} potential anomalies.",
            "top_anomalies": anomalies[:5],
            "top_change_points": change_points[:5],
        }
