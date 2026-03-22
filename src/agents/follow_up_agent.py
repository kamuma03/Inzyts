"""
Follow-Up Analysis Agent - Generates new notebook cells from follow-up questions.

This agent takes a user's follow-up question about an already-completed analysis,
the current kernel state, and conversation history, then generates NEW code and
markdown cells that investigate the question. It operates outside the main
LangGraph pipeline, invoked on-demand via the API.
"""

import json
import re
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.prompts import FOLLOW_UP_PROMPT
from src.utils.logger import get_logger

logger = get_logger()


class FollowUpAgent(BaseAgent):
    """
    Agent for generating follow-up analysis cells from natural language questions.

    Unlike the heavy-weight pipeline agents, this agent operates on a single
    question at a time with the existing kernel state as context. It generates
    new cells rather than modifying existing ones (contrast with CellEditAgent).
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="FollowUpAgent",
            phase=Phase.PHASE_2,
            system_prompt=FOLLOW_UP_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Process a follow-up question.

        Args:
            state: Current analysis state (used minimally).
            **kwargs:
                question (str): The user's follow-up question.
                df_context (str): DataFrame column names and dtypes.
                kernel_context (str): Current kernel variable state.
                notebook_summary (str): Brief description of notebook contents.
                conversation_history (list): Prior Q&A pairs [{role, content}].

        Returns:
            Dictionary containing 'cells' (list), 'summary' (str), and 'success' (bool).
        """
        question: str = kwargs.get("question", "")
        df_context: str = kwargs.get("df_context", "")
        kernel_context: str = kwargs.get("kernel_context", "")
        notebook_summary: str = kwargs.get("notebook_summary", "")
        conversation_history: List[Dict[str, str]] = kwargs.get(
            "conversation_history", []
        )

        if not question:
            return {
                "cells": [],
                "summary": "",
                "success": False,
                "error": "No question provided",
            }

        prompt = self._build_prompt(
            question, df_context, kernel_context, notebook_summary, conversation_history
        )

        try:
            response = self.llm_agent.invoke(prompt)
            parsed = self._parse_response(response)
            return {
                "cells": parsed.get("cells", []),
                "summary": parsed.get("summary", ""),
                "question_type": parsed.get("question_type", "explain"),
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(f"FollowUpAgent failed: {e}")
            return {
                "cells": [],
                "summary": "",
                "success": False,
                "error": str(e),
            }

    def ask(
        self,
        question: str,
        df_context: str = "",
        kernel_context: str = "",
        notebook_summary: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method for follow-up questions without full state.

        Args:
            question: Natural language follow-up question.
            df_context: DataFrame column names and dtypes.
            kernel_context: Current kernel variable state.
            notebook_summary: Brief notebook description.
            conversation_history: Prior Q&A pairs.

        Returns:
            Dictionary with 'cells', 'summary', 'success', and 'error' keys.
        """
        from src.models.state import AnalysisState

        minimal_state = AnalysisState(csv_path="", current_phase=Phase.PHASE_2)
        return self.process(
            minimal_state,
            question=question,
            df_context=df_context,
            kernel_context=kernel_context,
            notebook_summary=notebook_summary,
            conversation_history=conversation_history or [],
        )

    def _build_prompt(
        self,
        question: str,
        df_context: str,
        kernel_context: str,
        notebook_summary: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Build the follow-up prompt with all available context."""
        parts = []

        if df_context:
            parts.append(f"## DataFrame Context\n{df_context}\n")

        if kernel_context:
            parts.append(f"## Kernel Variables\n{kernel_context}\n")

        if notebook_summary:
            parts.append(f"## Notebook Summary\n{notebook_summary}\n")

        if conversation_history:
            history_text = []
            for msg in conversation_history[-6:]:  # Last 6 messages (3 Q&A pairs)
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_text.append(f"**{role.capitalize()}**: {content}")
            parts.append(
                "## Conversation History\n" + "\n".join(history_text) + "\n"
            )

        parts.append(f"## Follow-Up Question\n{question}")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Extract structured JSON from the LLM response.

        Handles:
        - Clean JSON responses
        - JSON wrapped in ```json ... ``` fences
        - Fallback: wrap raw text as a single markdown cell
        """
        cleaned = response.strip()

        # Try to extract JSON from code fences
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            # Validate expected structure
            if isinstance(parsed, dict) and "cells" in parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: treat the entire response as a markdown explanation
        logger.warning("FollowUpAgent: Could not parse JSON, using fallback")
        return {
            "summary": cleaned[:500] if len(cleaned) > 500 else cleaned,
            "question_type": "explain",
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": f"## Follow-Up Analysis\n\n{cleaned}",
                }
            ],
        }
