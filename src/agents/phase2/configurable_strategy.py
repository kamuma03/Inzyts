"""Mode-specific Phase-2 strategy agents share an identical scaffold:
verify lock → build context → invoke LLM → inject required fields → return.

This module collapses Forecasting/Comparative/Diagnostic/Segmentation into
one ``ConfigurableStrategyAgent`` parametrised by ``StrategyConfig``. The
named subclasses at the bottom of the file preserve the public API used
by ``agent_factory`` and the test suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.models.handoffs import AnalysisType, StrategyToCodeGenHandoff
from src.models.state import AnalysisState, Phase
from src.prompts import (
    COMPARATIVE_STRATEGY_PROMPT,
    DIAGNOSTIC_STRATEGY_PROMPT,
    FORECASTING_STRATEGY_PROMPT,
    SEGMENTATION_STRATEGY_PROMPT,
)


@dataclass(frozen=True)
class StrategyConfig:
    """Per-mode bindings for ``ConfigurableStrategyAgent``."""

    name: str
    system_prompt: str
    analysis_type: AnalysisType
    prompt_verb: str
    extension_attr: Optional[str] = None  # e.g. "forecasting_extension"; None = no extension input


class ConfigurableStrategyAgent(BaseAgent):
    """Single LLM-driven strategy agent parametrised by ``StrategyConfig``."""

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(name=config.name, phase=Phase.PHASE_2, system_prompt=config.system_prompt)
        self._config = config

    def process(self, state: AnalysisState, **kwargs: Any) -> Dict[str, Any]:
        cfg = self._config
        profile = (
            state.profile_lock.get_locked_handoff()
            if state.profile_lock.is_locked()
            else None
        )
        if not profile:
            return {"error": "Profile not locked"}

        context: Dict[str, Any] = {
            "profile_summary": profile.model_dump(exclude={"csv_preview", "csv_sample"}),
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }
        if cfg.extension_attr:
            extension_output = getattr(state, cfg.extension_attr, None)
            context["extension_output"] = (
                extension_output.model_dump() if extension_output else "None"
            )

        response_str = self.llm_agent.invoke_with_json(
            prompt=f"Design {cfg.prompt_verb} strategy for: {context}"
        )
        try:
            response_dict = json.loads(response_str)
            response_dict["profile_reference"] = state.profile_lock.lock_hash
            response_dict["analysis_type"] = cfg.analysis_type
            handoff = StrategyToCodeGenHandoff.model_validate(response_dict)
        except Exception as e:
            print(f"JSON Validation failed: {e}")
            print(f"Raw response: {response_str}")
            raise

        return {"handoff": handoff, "confidence": 1.0}


# ---------------------------------------------------------------------------
# Per-mode subclasses — preserved as the public surface for agent_factory
# and the test suite. Each is a 3-line binding to its config.
# ---------------------------------------------------------------------------


_COMPARATIVE = StrategyConfig(
    name="ComparativeStrategyAgent",
    system_prompt=COMPARATIVE_STRATEGY_PROMPT,
    analysis_type=AnalysisType.COMPARATIVE,
    prompt_verb="comparative",
    extension_attr="comparative_extension",
)

_DIAGNOSTIC = StrategyConfig(
    name="DiagnosticStrategyAgent",
    system_prompt=DIAGNOSTIC_STRATEGY_PROMPT,
    analysis_type=AnalysisType.CAUSAL,
    prompt_verb="diagnostic",
    extension_attr="diagnostic_extension",
)

_FORECASTING = StrategyConfig(
    name="ForecastingStrategyAgent",
    system_prompt=FORECASTING_STRATEGY_PROMPT,
    analysis_type=AnalysisType.TIME_SERIES,
    prompt_verb="forecasting",
    extension_attr="forecasting_extension",
)

_SEGMENTATION = StrategyConfig(
    name="SegmentationStrategyAgent",
    system_prompt=SEGMENTATION_STRATEGY_PROMPT,
    analysis_type=AnalysisType.CLUSTERING,
    prompt_verb="segmentation",
    extension_attr=None,
)


class ComparativeStrategyAgent(ConfigurableStrategyAgent):
    def __init__(self) -> None:
        super().__init__(_COMPARATIVE)


class DiagnosticStrategyAgent(ConfigurableStrategyAgent):
    def __init__(self) -> None:
        super().__init__(_DIAGNOSTIC)


class ForecastingStrategyAgent(ConfigurableStrategyAgent):
    def __init__(self) -> None:
        super().__init__(_FORECASTING)


class SegmentationStrategyAgent(ConfigurableStrategyAgent):
    def __init__(self) -> None:
        super().__init__(_SEGMENTATION)
