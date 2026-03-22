from typing import Any, Dict
import pandas as pd

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import ForecastingExtension, GapAnalysis
from src.prompts import FORECASTING_EXTENSION_PROMPT


class ForecastingExtensionAgent(BaseAgent):
    """
    Forecasting Extension Agent.
    Analyzes data for time series forecasting feasibility and parameters.
    """

    def __init__(self):
        super().__init__(
            name="ForecastingExtensionAgent",
            phase=Phase.PHASE_1,
            system_prompt=FORECASTING_EXTENSION_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Run the forecasting analysis extension.
        """
        # 1. Verify Profile Lock
        profile = (
            state.profile_lock.get_locked_handoff()
            if state.profile_lock.is_locked()
            else None
        )
        if not profile:
            return {"error": "Profile not locked, cannot run extension"}

        # 2. Load Data for Analysis
        if not state.csv_data:
            return {"error": "No CSV data available in state"}

        try:
            df = pd.DataFrame(state.csv_data)
        except Exception as e:
            return {"error": f"Failed to load dataframe: {e}"}

        # 3. Identify Date Column
        # Use profile hints first
        date_col = None
        for col_profile in profile.column_profiles:
            if col_profile.detected_type.lower() == "datetime":
                date_col = col_profile.name
                break

        # Fallback: Try to parse if not detected
        if not date_col:
            # Simple heuristic
            for col in df.columns:
                if "date" in col.lower() or "time" in col.lower():
                    try:
                        pd.to_datetime(df[col].iloc[:10])
                        date_col = col
                        break
                    except Exception:
                        pass

        if not date_col:
            # Just return an empty/error result via LLM or hard error?
            # Better to fail gracefully if we can't forecast.
            return {
                "error": "No datetime column found for forecasting",
                "confidence": 0.0,
            }

        # 4. Perform Hard Calculation (Frequency, Gaps)
        try:
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)

            # Infer Frequency
            inferred_freq = pd.infer_freq(df[date_col])

            # Gap Analysis
            # Create expected range
            if inferred_freq:
                full_range = pd.date_range(
                    start=df[date_col].min(), end=df[date_col].max(), freq=inferred_freq
                )
                missing_periods = full_range.difference(pd.DatetimeIndex(df[date_col]))
                has_gaps = len(missing_periods) > 0
                gap_count = len(missing_periods)
                # Max gap
                # This is a bit complex to calculate efficiently for large data in pure pandas without resampling
                # Simplified: just count
            else:
                has_gaps = False  # Can't determine without freq
                gap_count = 0
                missing_periods = pd.DatetimeIndex([])

            gap_analysis = GapAnalysis(
                has_gaps=has_gaps,
                gap_count=gap_count,
                largest_gap_periods=0,  # Placeholder
                gap_locations=[str(d) for d in missing_periods[:5]],  # Top 5
            )

            freq_str = inferred_freq if inferred_freq else "Unknown"
            date_range = (df[date_col].min(), df[date_col].max())
            total_periods = len(df)

        except Exception as e:
            return {"error": f"Time series analysis failed: {e}", "confidence": 0.0}

        # 5. Prepare Context for LLM
        context = {
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
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }

        # 6. Execute LLM
        # We pass our calculated hard-facts and let the LLM fill in the qualitative parts (Model selection, Stationarity hints)
        response_str = self.llm_agent.invoke_with_json(
            prompt=f"Analyze this time series metadata and recommend forecasting approach: {context}"
        )
        try:
            response = ForecastingExtension.model_validate_json(response_str)
        except Exception as e:
            print(f"JSON Validation failed: {e}")
            raise e

        # Inject our hard calculations back into the response to ensure accuracy
        # The LLM might hallucinate freq or dates from the 'context' string.
        response.datetime_column = date_col
        response.frequency = str(freq_str)
        response.date_range = date_range
        response.gap_analysis = gap_analysis
        response.total_periods = total_periods
        # response.missing_periods = [p for p in missing_periods] # Pydantic expects List[datetime]

        return {"forecasting_extension": response, "confidence": 1.0}
