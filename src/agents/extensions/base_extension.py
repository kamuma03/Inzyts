"""Shared scaffolding for the Phase-1 mode extensions.

The Forecasting / Comparative / Diagnostic extensions all share the same
outer shape: verify the profile lock, materialise a DataFrame from
``state.csv_data``, run mode-specific statistical detection, build a
context dict, ask the LLM to validate it as the matching extension model,
optionally hydrate the response with hard-computed values, and return
``{<output_key>: response, "confidence": 1.0}``.

This module factors that scaffold into ``BaseExtensionAgent``. Subclasses
override only the unique work: ``compute_features`` returns the per-mode
context fields (and may raise ``EarlyReturn`` to short-circuit when
preconditions aren't met), and ``hydrate`` patches in any exact values
the LLM should not be trusted to fabricate.
"""

from __future__ import annotations

from typing import Any, Dict, Type

import pandas as pd
from pydantic import BaseModel

from src.agents.base import BaseAgent
from src.models.handoffs import ProfileToStrategyHandoff
from src.models.state import AnalysisState, Phase


class EarlyReturn(Exception):
    """Raised by ``compute_features`` to bail out before the LLM call.

    The carried payload becomes the agent's return value (e.g.
    ``{"error": "...", "confidence": 0.0}``).
    """

    def __init__(self, payload: Dict[str, Any]) -> None:
        super().__init__(payload.get("error", "early return"))
        self.payload = payload


class BaseExtensionAgent(BaseAgent):
    """Shared scaffold for Phase-1 extension agents.

    Subclasses set the four class attributes below and override
    ``compute_features`` (always) and ``hydrate`` (optional).
    """

    extension_model: Type[BaseModel]
    output_key: str             # e.g. "forecasting_extension"
    prompt_intro: str           # leading text the LLM sees before the context
    error_no_csv: str = "No CSV data available"

    def __init__(self, name: str, system_prompt: str) -> None:
        super().__init__(name=name, phase=Phase.PHASE_1, system_prompt=system_prompt)

    # ----- overridable hooks --------------------------------------------------

    def compute_features(
        self, df: pd.DataFrame, profile: ProfileToStrategyHandoff, state: AnalysisState
    ) -> Dict[str, Any]:
        """Return the per-mode context fields. Raise ``EarlyReturn`` to bail."""
        raise NotImplementedError

    def hydrate(self, response: BaseModel, computed: Dict[str, Any]) -> BaseModel:
        """Optional: patch hard-computed values back onto the LLM response."""
        return response

    # ----- shared scaffold ----------------------------------------------------

    def process(self, state: AnalysisState, **kwargs: Any) -> Dict[str, Any]:
        profile = (
            state.profile_lock.get_locked_handoff()
            if state.profile_lock.is_locked()
            else None
        )
        if not profile:
            return {"error": "Profile not locked, cannot run extension"}

        if not state.csv_data:
            return {"error": self.error_no_csv}
        try:
            df = pd.DataFrame(state.csv_data)
        except Exception as e:
            return {"error": f"Failed to load dataframe: {e}"}

        try:
            computed = self.compute_features(df, profile, state)
        except EarlyReturn as exc:
            return exc.payload

        context = {
            **computed,
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }

        response_str = self.llm_agent.invoke_with_json(
            prompt=f"{self.prompt_intro}: {context}"
        )
        try:
            response = self.extension_model.model_validate_json(response_str)
        except Exception as e:
            print(f"JSON Validation failed: {e}")
            print(f"Response was: {response_str}")
            raise

        response = self.hydrate(response, computed)
        return {self.output_key: response, "confidence": 1.0}
