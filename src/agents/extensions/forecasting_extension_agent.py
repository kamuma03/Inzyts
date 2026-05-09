from typing import Any, Dict

import pandas as pd

from src.agents.extensions.base_extension import BaseExtensionAgent, EarlyReturn
from src.models.handoffs import ForecastingExtension, GapAnalysis, ProfileToStrategyHandoff
from src.models.state import AnalysisState
from src.prompts import FORECASTING_EXTENSION_PROMPT


class ForecastingExtensionAgent(BaseExtensionAgent):
    """Analyses time-series feasibility (date column, frequency, gaps)."""

    extension_model = ForecastingExtension
    output_key = "forecasting_extension"
    prompt_intro = "Analyze this time series metadata and recommend forecasting approach"
    error_no_csv = "No CSV data available in state"

    def __init__(self) -> None:
        super().__init__(name="ForecastingExtensionAgent", system_prompt=FORECASTING_EXTENSION_PROMPT)

    def compute_features(
        self, df: pd.DataFrame, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> Dict[str, Any]:
        # 1. Identify date column (profile hint → name-heuristic fallback).
        date_col = next(
            (c.name for c in profile.column_profiles if c.detected_type.lower() == "datetime"),
            None,
        )
        if not date_col:
            for col in df.columns:
                if "date" in col.lower() or "time" in col.lower():
                    try:
                        pd.to_datetime(df[col].iloc[:10])
                        date_col = col
                        break
                    except Exception:
                        pass
        if not date_col:
            raise EarlyReturn({"error": "No datetime column found for forecasting", "confidence": 0.0})

        # 2. Frequency + gap analysis.
        try:
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)
            inferred_freq = pd.infer_freq(df[date_col])
            if inferred_freq:
                full_range = pd.date_range(
                    start=df[date_col].min(), end=df[date_col].max(), freq=inferred_freq
                )
                missing_periods = full_range.difference(pd.DatetimeIndex(df[date_col]))
                gap_count = len(missing_periods)
                has_gaps = gap_count > 0
            else:
                has_gaps, gap_count = False, 0
                missing_periods = pd.DatetimeIndex([])

            gap_analysis = GapAnalysis(
                has_gaps=has_gaps,
                gap_count=gap_count,
                largest_gap_periods=0,
                gap_locations=[str(d) for d in missing_periods[:5]],
            )
            freq_str = inferred_freq if inferred_freq else "Unknown"
            date_range = (df[date_col].min(), df[date_col].max())
            total_periods = len(df)
        except Exception as e:
            raise EarlyReturn({"error": f"Time series analysis failed: {e}", "confidence": 0.0})

        return {
            "date_column": date_col,
            "frequency_detected": freq_str,
            "period_start": str(date_range[0]),
            "period_end": str(date_range[1]),
            "total_rows": total_periods,
            "gap_analysis": gap_analysis.model_dump(),
            "target_candidates": [
                c.name
                for c in profile.column_profiles
                if c.detected_type in ["numeric_continuous", "numeric_discrete"]
                and c.name != date_col
            ],
            # Fields below are stashed for hydrate() — not sent to the LLM as
            # standalone keys, just as part of the context dict it sees.
            "_date_col": date_col,
            "_freq_str": freq_str,
            "_date_range": date_range,
            "_gap_analysis": gap_analysis,
            "_total_periods": total_periods,
        }

    def hydrate(self, response: ForecastingExtension, computed: Dict[str, Any]) -> ForecastingExtension:
        # The LLM sees the hard facts in context, but may still hallucinate;
        # overwrite with our calculations so downstream agents get truth.
        response.datetime_column = computed["_date_col"]
        response.frequency = str(computed["_freq_str"])
        response.date_range = computed["_date_range"]
        response.gap_analysis = computed["_gap_analysis"]
        response.total_periods = computed["_total_periods"]
        return response
