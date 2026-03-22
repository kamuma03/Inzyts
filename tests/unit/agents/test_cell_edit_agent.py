"""
Unit tests for CellEditAgent.

Tests the lightweight micro-agent that modifies individual notebook cells
based on natural language instructions.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.cell_edit_agent import CellEditAgent
from src.models.state import AnalysisState, Phase


class TestCellEditAgentInitialization:
    """Test CellEditAgent initialization."""

    @patch('src.agents.cell_edit_agent.BaseAgent.__init__')
    def test_init_default(self, mock_base_init):
        """Test initialization with default parameters."""
        mock_base_init.return_value = None

        agent = CellEditAgent()

        mock_base_init.assert_called_once_with(
            name="CellEditAgent",
            phase=Phase.PHASE_2,
            system_prompt=pytest.importorskip("src.prompts").CELL_EDIT_PROMPT,
            provider=None,
            model=None,
        )

    @patch('src.agents.cell_edit_agent.BaseAgent.__init__')
    def test_init_with_custom_provider(self, mock_base_init):
        """Test initialization with custom provider and model."""
        mock_base_init.return_value = None

        agent = CellEditAgent(provider="anthropic", model="claude-3")

        call_kwargs = mock_base_init.call_args[1]
        assert call_kwargs['provider'] == "anthropic"
        assert call_kwargs['model'] == "claude-3"


class TestCellEditAgentProcess:
    """Test the process method."""

    def _make_agent(self):
        agent = CellEditAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_process_success(self):
        """Test successful cell editing."""
        agent = self._make_agent()
        agent.llm_agent.invoke.return_value = '```python\ndf.plot(kind="pie")\nplt.show()\n```'

        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)
        result = agent.process(
            state,
            instruction="Make this a pie chart",
            current_code='df.plot(kind="bar")\nplt.show()',
            df_context="col1: int64\ncol2: object",
        )

        assert result["success"] is True
        assert 'pie' in result["new_code"]
        assert result["error"] is None

    def test_process_no_instruction(self):
        """Test process without instruction returns error."""
        agent = self._make_agent()
        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)

        result = agent.process(
            state,
            instruction="",
            current_code="print('hello')",
        )

        assert result["success"] is False
        assert "No instruction" in result["error"]

    def test_process_no_current_code(self):
        """Test process without current code returns error."""
        agent = self._make_agent()
        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)

        result = agent.process(
            state,
            instruction="Change this",
            current_code="",
        )

        assert result["success"] is False
        assert "No current code" in result["error"]

    def test_process_llm_failure_returns_original(self):
        """Test that LLM failure returns the original code."""
        agent = self._make_agent()
        agent.llm_agent.invoke.side_effect = Exception("API Error")

        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)
        result = agent.process(
            state,
            instruction="Change to scatter plot",
            current_code="original_code()",
        )

        assert result["success"] is False
        assert result["new_code"] == "original_code()"
        assert "API Error" in result["error"]


class TestBuildPrompt:
    """Test prompt building."""

    def _make_agent(self):
        agent = CellEditAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_build_prompt_includes_code(self):
        """Test that prompt includes the current code."""
        agent = self._make_agent()
        prompt = agent._build_prompt("Make it better", "df.head()", "")

        assert "df.head()" in prompt
        assert "Make it better" in prompt

    def test_build_prompt_includes_context(self):
        """Test that prompt includes df context when provided."""
        agent = self._make_agent()
        prompt = agent._build_prompt(
            "Add title",
            "plt.plot()",
            "age: int64\nname: object"
        )

        assert "age: int64" in prompt
        assert "DataFrame Context" in prompt

    def test_build_prompt_no_context(self):
        """Test that prompt works without context."""
        agent = self._make_agent()
        prompt = agent._build_prompt("Do something", "print(1)", "")

        assert "DataFrame Context" not in prompt


class TestExtractCode:
    """Test code extraction from LLM responses."""

    def _make_agent(self):
        agent = CellEditAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_extract_from_python_block(self):
        """Test extraction from ```python ... ``` blocks."""
        agent = self._make_agent()
        response = '```python\ndf.plot(kind="bar")\nplt.show()\n```'
        code = agent._extract_code(response)

        assert 'df.plot(kind="bar")' in code
        assert "```" not in code

    def test_extract_from_plain_block(self):
        """Test extraction from ``` ... ``` blocks without language."""
        agent = self._make_agent()
        response = '```\nprint("hello")\n```'
        code = agent._extract_code(response)

        assert 'print("hello")' in code

    def test_extract_raw_code(self):
        """Test extraction when response has no code fences."""
        agent = self._make_agent()
        response = 'df.head(10)'
        code = agent._extract_code(response)

        assert code == 'df.head(10)'

    def test_extract_with_surrounding_text(self):
        """Test extraction when there's text outside code fences."""
        agent = self._make_agent()
        response = 'Here is the code:\n```python\nresult = df.sum()\n```\nDone!'
        code = agent._extract_code(response)

        assert code == 'result = df.sum()'


class TestEditCellConvenience:
    """Test the edit_cell convenience method."""

    def test_edit_cell_delegates_to_process(self):
        """Test that edit_cell calls process with correct args."""
        agent = CellEditAgent()
        agent.llm_agent = MagicMock()
        agent.llm_agent.invoke.return_value = '```python\nnew_code()\n```'

        result = agent.edit_cell(
            instruction="Fix this",
            current_code="old_code()",
            df_context="x: float64",
        )

        assert result["success"] is True
        assert "new_code()" in result["new_code"]
        agent.llm_agent.invoke.assert_called_once()
