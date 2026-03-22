"""
Exploratory Conclusions Agent.

This agent runs at the end of Phase 1 when the pipeline mode is EXPLORATORY.
It consumes the verified data profile and uses the LLM to generate insights,
answers the user's question, and provides recommendations, effectively
concluding the analysis without building predictive models.
"""

from typing import Any, Dict, Optional
import json

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import (
    ExploratoryConclusionsOutput,
    ExploratoryConclusionsToAssemblyHandoff,
    NotebookCell,
)
from src.prompts import EXPLORATORY_CONCLUSIONS_PROMPT
from src.config import settings
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger()


class ExploratoryConclusionsAgent(BaseAgent):
    """
    Agent responsible for synthesizing insights from the data profile.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="Exploratory Conclusions Agent",
            phase=Phase.EXPLORATORY_CONCLUSIONS,
            system_prompt=EXPLORATORY_CONCLUSIONS_PROMPT,
            provider=provider,
            model=model or settings.exploratory.llm_model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Generate conclusions based on the locked profile.

        Args:
            state: Current analysis state.
            **kwargs: unused.

        Returns:
            Dict containing the 'handoff' (ExploratoryConclusionsToAssemblyHandoff).
        """
        # Log exploratory conclusions start
        logger.exploratory_conclusions("start")
        logger.agent_execution("ExploratoryConclusionsAgent", "invoked")

        # 1. Retrieve locked profile
        if not state.profile_lock.is_locked():
            logger.agent_execution(
                "ExploratoryConclusionsAgent", "failed", reason="profile_not_locked"
            )
            return {
                "error": "Profile not locked. Cannot generate conclusions.",
                "confidence": 0.0,
            }

        profile_handoff = state.profile_lock.get_locked_handoff()

        # 2a. CACHE CHECK
        if state.using_cached_profile:
            from src.utils.cache_manager import CacheManager
            import hashlib

            cache_manager = CacheManager()
            csv_hash = cache_manager.get_csv_hash(state.csv_path)

            # Hash the question to create a unique cache key
            question_text = (
                state.user_intent.analysis_question
                if state.user_intent and state.user_intent.analysis_question
                else "General Exploratory Analysis"
            )
            q_hash = hashlib.sha256(question_text.encode("utf-8")).hexdigest()
            cache_key = f"exploratory_conclusions_{q_hash}"

            cached_output = cache_manager.load_artifact(csv_hash, cache_key)

            if cached_output:
                logger.info(
                    f"Using cached exploratory conclusions for question: '{question_text}'"
                )
                try:
                    # Rehydrate Pydantic models from dict
                    output = ExploratoryConclusionsOutput(**cached_output)

                    # Create assembly handoff from cached output
                    handoff = ExploratoryConclusionsToAssemblyHandoff(
                        conclusions_cells=output.conclusions_cells,
                        visualization_cells=output.visualization_cells,
                        direct_answer_summary=output.direct_answer,
                        key_findings_count=len(output.key_findings),
                        confidence_score=output.confidence_score,
                        limitations=output.limitations,
                    )

                    logger.exploratory_conclusions(
                        "complete", confidence=output.confidence_score
                    )
                    return {
                        "exploratory_conclusions": output,
                        "assembly_handoff": handoff,
                        "confidence": output.confidence_score,
                    }
                except Exception as e:
                    logger.warning(f"Failed to load cached conclusions: {e}")
        else:
            # Need to initialize cache_manager for saving later even if not loading
            from src.utils.cache_manager import CacheManager
            import hashlib

            cache_manager = CacheManager()
            csv_hash = cache_manager.get_csv_hash(state.csv_path)
            # Hash the question to create a unique cache key
            question_text = (
                state.user_intent.analysis_question
                if state.user_intent and state.user_intent.analysis_question
                else "General Exploratory Analysis"
            )
            q_hash = hashlib.sha256(question_text.encode("utf-8")).hexdigest()
            cache_key = f"exploratory_conclusions_{q_hash}"

        # 2b. Construct Prompt Input
        # We need to serialize the relevant parts of the profile for the LLM
        prompt_input = {
            "user_question": question_text,
            "data_summary": {
                "rows": profile_handoff.row_count,
                "columns": profile_handoff.column_count,
                "quality_score": profile_handoff.overall_quality_score,
                "missing_values": profile_handoff.missing_value_summary,
            },
            "columns": [
                c.model_dump() if hasattr(c, "model_dump") else str(c)
                for c in profile_handoff.column_profiles
            ],
            "correlations": profile_handoff.correlation_matrix,
            "detected_patterns": profile_handoff.detected_patterns,
        }

        # 3. Call LLM with Retry Logic
        max_retries = 3

        for attempt in range(max_retries):
            try:
                prompt_input["attempt"] = attempt + 1  # Hint to LLM?
                prompt = f"Generate conclusions for this profile: {json.dumps(prompt_input, default=str)}"

                response = self.llm_agent.invoke_with_json(prompt)

                # 4. Parse Response
                # If response is string (from some providers), parse it
                if isinstance(response, str):
                    response_data = json.loads(response)
                else:
                    response_data = response

                output = ExploratoryConclusionsOutput(**response_data)

                # Save to cache
                if output.confidence_score > 0.0:
                    # Use model_dump for Pydantic v2 or dict() for v1
                    cache_data = output.model_dump()
                    cache_manager.save_artifact(csv_hash, cache_key, cache_data)

                # If we get here, success!
                break

            except Exception as e:
                pass
                logger.agent_execution(
                    "ExploratoryConclusionsAgent",
                    "retry",
                    attempt=attempt + 1,
                    reason=str(e),
                )
                if attempt == max_retries - 1:
                    # Final attempt failed, use fallback
                    logger.agent_execution(
                        "ExploratoryConclusionsAgent",
                        "failed",
                        reason=f"parse_error_final: {str(e)}",
                    )

                    # Create a fallback output so the notebook section still exists
                    fallback_md = f"### Analysis Generation Failed\n\nWe encountered an error generating the detailed conclusions after {max_retries} attempts. \n\n**Error Details:** {str(e)}\n\nPlease try running the analysis again or simplify the question."

                    output = ExploratoryConclusionsOutput(
                        original_question=(
                            state.user_intent.analysis_question
                            if state.user_intent and state.user_intent.analysis_question
                            else "General Exploratory Analysis"
                        ),
                        conclusions_cells=[
                            NotebookCell(cell_type="markdown", source=fallback_md)
                        ],
                        visualization_cells=[],
                        direct_answer="Analysis generation failed due to technical error.",
                        key_findings=[],
                        statistical_insights=[],
                        data_quality_notes=["Analysis generation failed"],
                        recommendations=[],
                        limitations=["Output generation failed"],
                        confidence_score=0.0,
                    )

                    # Save fallback to cache to avoid repeated slow failures
                    cache_data = output.model_dump()
                    cache_manager.save_artifact(csv_hash, cache_key, cache_data)

        # 5. Create Assembly Handoff
        handoff = ExploratoryConclusionsToAssemblyHandoff(
            conclusions_cells=output.conclusions_cells,
            visualization_cells=output.visualization_cells,
            direct_answer_summary=output.direct_answer,
            key_findings_count=len(output.key_findings),
            confidence_score=output.confidence_score,
            limitations=output.limitations,
        )

        # Log low confidence warning if needed
        if output.confidence_score < settings.exploratory.min_confidence:
            logger.exploratory_conclusions(
                "low_confidence", confidence=output.confidence_score
            )

        # Log completion
        logger.exploratory_conclusions("complete", confidence=output.confidence_score)
        logger.agent_execution(
            "ExploratoryConclusionsAgent",
            "completed",
            findings_count=len(output.key_findings),
            recommendations_count=len(output.recommendations),
            confidence=output.confidence_score,
        )

        # 6. Update State via AgentOutput mechanism (standardized return)
        # Note: The Orchestrator/Graph will actually update the state object
        # The method here returns the updates to be applied.

        return {
            "exploratory_conclusions": output,  # Store full output in state
            "assembly_handoff": handoff,  # Helper for assembly node
            "confidence": output.confidence_score,
        }
