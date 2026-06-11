"""Shared scaffolding for the Phase-1 mode extensions.

The Forecasting / Comparative / Diagnostic extensions all share the same
outer shape: verify the profile lock, materialise a DataFrame from
``state.csv_path`` (the full frame is deliberately never serialised onto
state — see ``orchestrator``), run mode-specific statistical detection,
build a context dict, ask the LLM to validate it as the matching extension model,
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
from src.utils.file_utils import load_csv_robust
from src.utils.logger import get_logger

logger = get_logger()


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

    # Extensions profile a sample only; exact counts come from the locked
    # profile, so a bounded read keeps large uploads off the worker's heap.
    max_rows: int = 50000

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

        # The full DataFrame is intentionally not serialised onto state
        # (orchestrator sets ``csv_data=None`` for performance); load from the
        # path every other agent reads from instead.
        if not state.csv_path:
            return {"error": self.error_no_csv}
        try:
            df = load_csv_robust(state.csv_path, nrows=self.max_rows)
        except Exception as e:
            logger.error(f"{self.name}: failed to load CSV from {state.csv_path}: {e}")
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
            # A single malformed LLM reply must not kill the whole run; degrade
            # gracefully like every Phase-1/Phase-2 agent does. The extension
            # output is advisory pre-strategy context, so a low-confidence error
            # return lets the graph continue to the strategy node.
            logger.error(
                f"{self.name}: extension JSON validation failed: {e}; "
                f"response was: {response_str[:500]}"
            )
            return {"error": f"Extension output invalid: {e}", "confidence": 0.0}

        response = self.hydrate(response, computed)
        return {self.output_key: response, "confidence": 1.0}
