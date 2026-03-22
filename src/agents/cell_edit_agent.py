"""
Cell Edit Agent - Lightweight micro-agent for interactive cell-level edits.

This agent takes a user's natural language instruction (e.g., "Make this a pie chart"),
the current cell's Python code, and a compact dataframe context, then returns
the modified code. It is designed for minimal token usage (~500 tokens per call).
"""

import re
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.prompts import CELL_EDIT_PROMPT
from src.utils.logger import get_logger

logger = get_logger()


class CellEditAgent(BaseAgent):
    """
    Lightweight agent for editing individual notebook cells.

    Unlike the heavy-weight CodeGen agents, this agent operates on a single
    cell at a time with minimal context, making it fast and token-efficient.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="CellEditAgent",
            phase=Phase.PHASE_2,
            system_prompt=CELL_EDIT_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Process a cell edit request.

        Args:
            state: Current analysis state (used minimally).
            **kwargs:
                instruction (str): The user's natural language edit instruction.
                current_code (str): The current Python code of the cell.
                df_context (str): Compact dataframe context (column names + dtypes).

        Returns:
            Dictionary containing 'new_code' (str) and 'success' (bool).
        """
        instruction: str = kwargs.get("instruction", "")
        current_code: str = kwargs.get("current_code", "")
        df_context: str = kwargs.get("df_context", "")

        if not instruction:
            return {
                "new_code": current_code,
                "success": False,
                "error": "No instruction provided",
            }

        if not current_code:
            return {
                "new_code": "",
                "success": False,
                "error": "No current code provided",
            }

        prompt = self._build_prompt(instruction, current_code, df_context)

        try:
            response = self.llm_agent.invoke(prompt)
            new_code = self._extract_code(response)
            return {
                "new_code": new_code,
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(f"CellEditAgent failed: {e}")
            return {
                "new_code": current_code,
                "success": False,
                "error": str(e),
            }

    def _build_prompt(
        self, instruction: str, current_code: str, df_context: str
    ) -> str:
        """Build the edit prompt with minimal context."""
        parts = [
            "## Current Cell Code",
            f"```python\n{current_code}\n```",
            "",
            "## User Instruction",
            instruction,
        ]

        if df_context:
            parts.insert(0, f"## DataFrame Context\n{df_context}\n")

        return "\n".join(parts)

    def _extract_code(self, response: str) -> str:
        """Extract Python code from the LLM response."""
        cleaned = response.strip()

        # Try to find code inside ```python ... ```
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no code block, return the raw response (assume it's just code)
        return cleaned

    def edit_cell(
        self, instruction: str, current_code: str, df_context: str = ""
    ) -> Dict[str, Any]:
        """
        Convenience method for direct cell editing without full state.

        Args:
            instruction: Natural language edit instruction.
            current_code: Current Python source of the cell.
            df_context: Optional dataframe context string.

        Returns:
            Dictionary with 'new_code', 'success', and 'error' keys.
        """
        # Create a minimal state — the agent doesn't really need it
        from src.models.state import AnalysisState

        minimal_state = AnalysisState(csv_path="", current_phase=Phase.PHASE_2)
        return self.process(
            minimal_state,
            instruction=instruction,
            current_code=current_code,
            df_context=df_context,
        )
