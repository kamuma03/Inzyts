"""
Unit tests for FollowUpAgent.

Tests the agent that generates new notebook cells from follow-up questions
about a completed analysis.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.follow_up_agent import FollowUpAgent
from src.models.state import AnalysisState, Phase


class TestFollowUpAgentInitialization:
    """Test FollowUpAgent initialization."""

    @patch('src.agents.follow_up_agent.BaseAgent.__init__')
    def test_init_default(self, mock_base_init):
        """Test initialization with default parameters."""
        mock_base_init.return_value = None

        agent = FollowUpAgent()

        mock_base_init.assert_called_once_with(
            name="FollowUpAgent",
            phase=Phase.PHASE_2,
            system_prompt=pytest.importorskip("src.prompts").FOLLOW_UP_PROMPT,
            provider=None,
            model=None,
        )

    @patch('src.agents.follow_up_agent.BaseAgent.__init__')
    def test_init_with_custom_provider(self, mock_base_init):
        """Test initialization with custom provider and model."""
        mock_base_init.return_value = None

        agent = FollowUpAgent(provider="anthropic", model="claude-3")

        call_kwargs = mock_base_init.call_args[1]
        assert call_kwargs['provider'] == "anthropic"
        assert call_kwargs['model'] == "claude-3"


class TestFollowUpAgentProcess:
    """Test the process method."""

    def _make_agent(self):
        agent = FollowUpAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_process_success(self):
        """Test successful follow-up question processing."""
        agent = self._make_agent()
        response_json = json.dumps({
            "summary": "Cluster 2 is largest because of high-value customers.",
            "question_type": "drill-down",
            "cells": [
                {"cell_type": "markdown", "source": "## Cluster 2 Analysis"},
                {"cell_type": "code", "source": "df[df['cluster']==2].describe()"},
            ],
        })
        agent.llm_agent.invoke.return_value = response_json

        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)
        result = agent.process(
            state,
            question="Why is Cluster 2 the largest?",
            df_context="col1: int64\ncol2: object",
        )

        assert result["success"] is True
        assert len(result["cells"]) == 2
        assert result["cells"][0]["cell_type"] == "markdown"
        assert result["cells"][1]["cell_type"] == "code"
        assert "Cluster 2" in result["summary"]
        assert result["question_type"] == "drill-down"
        assert result["error"] is None

    def test_process_no_question(self):
        """Test process without question returns error."""
        agent = self._make_agent()
        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)

        result = agent.process(state, question="")

        assert result["success"] is False
        assert "No question" in result["error"]
        assert result["cells"] == []

    def test_process_llm_failure(self):
        """Test that LLM failure returns error gracefully."""
        agent = self._make_agent()
        agent.llm_agent.invoke.side_effect = Exception("API Error")

        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)
        result = agent.process(
            state,
            question="What happened?",
            df_context="col1: int64",
        )

        assert result["success"] is False
        assert "API Error" in result["error"]
        assert result["cells"] == []

    def test_process_with_conversation_history(self):
        """Test that conversation history is passed to the prompt."""
        agent = self._make_agent()
        response_json = json.dumps({
            "summary": "Answer based on prior context.",
            "question_type": "explain",
            "cells": [{"cell_type": "markdown", "source": "## Explanation"}],
        })
        agent.llm_agent.invoke.return_value = response_json

        state = AnalysisState(csv_path="test.csv", current_phase=Phase.PHASE_2)
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        result = agent.process(
            state,
            question="Follow-up question",
            conversation_history=history,
        )

        assert result["success"] is True
        # Verify history was included in the prompt
        call_args = agent.llm_agent.invoke.call_args[0][0]
        assert "First question" in call_args
        assert "First answer" in call_args


class TestBuildPrompt:
    """Test prompt building."""

    def _make_agent(self):
        agent = FollowUpAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_build_prompt_includes_context(self):
        """Test that prompt includes all context sections."""
        agent = self._make_agent()
        prompt = agent._build_prompt(
            question="Why is accuracy low?",
            df_context="col1: int64\ncol2: float64",
            kernel_context="df: DataFrame shape=(100, 5)\nmodel: RandomForest",
            notebook_summary="Predictive analysis of churn data",
            conversation_history=[],
        )

        assert "Why is accuracy low?" in prompt
        assert "col1: int64" in prompt
        assert "DataFrame Context" in prompt
        assert "Kernel Variables" in prompt
        assert "RandomForest" in prompt
        assert "Notebook Summary" in prompt

    def test_build_prompt_no_context(self):
        """Test that prompt works with minimal context."""
        agent = self._make_agent()
        prompt = agent._build_prompt("A question?", "", "", "", [])

        assert "A question?" in prompt
        assert "DataFrame Context" not in prompt

    def test_build_prompt_includes_history(self):
        """Test that conversation history appears in prompt."""
        agent = self._make_agent()
        history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]
        prompt = agent._build_prompt("Q2", "", "", "", history)

        assert "Q1" in prompt
        assert "A1" in prompt
        assert "Conversation History" in prompt

    def test_build_prompt_limits_history(self):
        """Test that history is truncated to last 6 messages."""
        agent = self._make_agent()
        history = [
            {"role": "user", "content": f"Q{i}"}
            for i in range(10)
        ]
        prompt = agent._build_prompt("Latest?", "", "", "", history)

        # Last 6 messages should be present (Q4..Q9)
        assert "Q9" in prompt
        assert "Q4" in prompt
        # Older messages should not be present
        assert "Q0" not in prompt


class TestParseResponse:
    """Test response parsing."""

    def _make_agent(self):
        agent = FollowUpAgent()
        agent.llm_agent = MagicMock()
        return agent

    def test_parse_json_response(self):
        """Test parsing a clean JSON response."""
        agent = self._make_agent()
        response = json.dumps({
            "summary": "Here's the analysis.",
            "question_type": "explain",
            "cells": [{"cell_type": "code", "source": "print(1)"}],
        })
        result = agent._parse_response(response)

        assert result["summary"] == "Here's the analysis."
        assert len(result["cells"]) == 1

    def test_parse_json_in_code_fences(self):
        """Test parsing JSON wrapped in ```json fences."""
        agent = self._make_agent()
        response = '```json\n{"summary": "test", "cells": [{"cell_type": "markdown", "source": "# Hi"}]}\n```'
        result = agent._parse_response(response)

        assert result["summary"] == "test"
        assert len(result["cells"]) == 1

    def test_parse_fallback_for_non_json(self):
        """Test fallback when response is not valid JSON."""
        agent = self._make_agent()
        response = "Here is some free-text explanation about the data."
        result = agent._parse_response(response)

        assert "cells" in result
        assert len(result["cells"]) == 1
        assert result["cells"][0]["cell_type"] == "markdown"
        assert "free-text" in result["cells"][0]["source"]


class TestAskConvenience:
    """Test the ask convenience method."""

    def test_ask_delegates_to_process(self):
        """Test that ask() calls process with correct args."""
        agent = FollowUpAgent()
        agent.llm_agent = MagicMock()
        agent.llm_agent.invoke.return_value = json.dumps({
            "summary": "Result",
            "question_type": "explain",
            "cells": [{"cell_type": "markdown", "source": "# Answer"}],
        })

        result = agent.ask(
            question="Why?",
            df_context="x: float64",
            kernel_context="df: DataFrame",
            notebook_summary="Analysis notebook",
        )

        assert result["success"] is True
        assert result["summary"] == "Result"
        assert len(result["cells"]) == 1
        agent.llm_agent.invoke.assert_called_once()
