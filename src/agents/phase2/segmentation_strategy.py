from typing import Any, Dict

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType
from src.prompts import SEGMENTATION_STRATEGY_PROMPT


class SegmentationStrategyAgent(BaseAgent):
    """
    Segmentation Strategy Agent.
    Plans clustering/segmentation analysis.
    """

    def __init__(self):
        super().__init__(
            name="SegmentationStrategyAgent",
            phase=Phase.PHASE_2,
            system_prompt=SEGMENTATION_STRATEGY_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Design segmentation strategy.
        """
        profile = (
            state.profile_lock.get_locked_handoff()
            if state.profile_lock.is_locked()
            else None
        )

        if not profile:
            return {"error": "Profile not locked"}

        context = {
            "profile_summary": profile.model_dump(
                exclude={"csv_preview", "csv_sample"}
            ),
            "user_intent": state.user_intent.model_dump() if state.user_intent else {},
        }

        response_str = self.llm_agent.invoke_with_json(
            prompt=f"Design segmentation strategy for: {context}"
        )

        try:
            import json

            response_dict = json.loads(response_str)

            # Inject required fields
            response_dict["profile_reference"] = state.profile_lock.lock_hash
            response_dict["analysis_type"] = AnalysisType.CLUSTERING

            response = StrategyToCodeGenHandoff.model_validate(response_dict)

        except Exception as e:
            print(f"JSON Validation failed: {e}")
            print(f"Raw response: {response_str}")
            raise e

        return {"handoff": response, "confidence": 1.0}
