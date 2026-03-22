"""
Unit tests for BaseAgent class.

Tests the foundation class that all 23 agents inherit from, including:
- LLM initialization for different providers
- CrewAI agent creation
- Issue creation helper
- Provider string formatting
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.common import Issue


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def process(self, state: AnalysisState, **kwargs):
        """Minimal implementation of abstract method."""
        return {"test": "result"}


class TestBaseAgentInitialization:
    """Test BaseAgent initialization with different providers."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_default_provider(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with default provider from settings."""
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance

        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.openai_model = "gpt-4"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt for agent"
            )

            assert agent.name == "TestAgent"
            assert agent.phase == Phase.PHASE_1
            assert agent.system_prompt == "Test prompt for agent"

            # Verify LLMAgent was initialized
            mock_llm_agent.assert_called_once_with(
                name="TestAgent",
                provider="openai",
                model=None,
                system_prompt="Test prompt for agent"
            )

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_anthropic_provider(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with Anthropic provider."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.anthropic_model = "claude-3-5-sonnet-20241022"
            mock_settings.llm.anthropic_api_key = "test-key"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt",
                provider="anthropic"
            )

            # Verify LLMAgent was initialized with anthropic
            mock_llm_agent.assert_called_once_with(
                name="TestAgent",
                provider="anthropic",
                model=None,
                system_prompt="Test prompt"
            )

            # Trigger lazy initialization
            _ = agent.crew_agent

            # Verify CrewAgent was initialized with string format
            mock_crew_agent.assert_called_once()
            call_kwargs = mock_crew_agent.call_args[1]
            assert call_kwargs['llm'] == "anthropic/claude-3-5-sonnet-20241022"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_gemini_provider(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with Gemini provider."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.gemini_model = "gemini-1.5-pro"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_2,
                system_prompt="Test prompt",
                provider="gemini"
            )

            # Verify LLMAgent was initialized with gemini
            mock_llm_agent.assert_called_once_with(
                name="TestAgent",
                provider="gemini",
                model=None,
                system_prompt="Test prompt"
            )

            # Trigger lazy initialization
            _ = agent.crew_agent

            # Verify CrewAgent was initialized with string format (workaround for API key check)
            mock_crew_agent.assert_called_once()
            call_kwargs = mock_crew_agent.call_args[1]
            assert call_kwargs['llm'] == "gemini/gemini-1.5-pro"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_ollama_provider(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with Ollama provider."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.ollama_model = "llama3:8b"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt",
                provider="ollama"
            )

            # Trigger lazy initialization
            _ = agent.crew_agent

            # Verify CrewAgent was initialized with ollama string format
            mock_crew_agent.assert_called_once()
            call_kwargs = mock_crew_agent.call_args[1]
            assert call_kwargs['llm'] == "ollama/llama3:8b"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_openai_provider(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with OpenAI provider (uses string format)."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.openai_model = "gpt-4"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt",
                provider="openai"
            )

            # Trigger lazy initialization
            _ = agent.crew_agent

            # Verify CrewAgent was initialized with string format
            mock_crew_agent.assert_called_once()
            call_kwargs = mock_crew_agent.call_args[1]
            assert call_kwargs['llm'] == "openai/gpt-4"
            assert isinstance(call_kwargs['llm'], str)

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_init_with_custom_model(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test initialization with custom model override."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.anthropic_api_key = "dummy-key"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt",
                provider="anthropic",
                model="claude-opus-4-5-20241101"
            )

            # Verify model was passed to LLMAgent
            mock_llm_agent.assert_called_once_with(
                name="TestAgent",
                provider="anthropic",
                model="claude-opus-4-5-20241101",
                system_prompt="Test prompt"
            )


class TestCrewAgentConfiguration:
    """Test CrewAI agent configuration."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_crew_agent_configuration(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test CrewAI agent is configured correctly."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            system_prompt = "First line is goal\nRest is backstory"
            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt=system_prompt
            )

            # Trigger lazy initialization
            _ = agent.crew_agent

            # Verify CrewAgent configuration
            mock_crew_agent.assert_called_once()
            call_kwargs = mock_crew_agent.call_args[1]

            assert call_kwargs['role'] == "TestAgent"
            assert call_kwargs['goal'] == "First line is goal"
            assert call_kwargs['backstory'] == system_prompt
            assert call_kwargs['allow_delegation'] is False
            assert call_kwargs['verbose'] is True
            assert call_kwargs['memory'] is False

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_crew_agent_with_multiline_prompt(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test goal extraction from multiline system prompt."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            system_prompt = "Agent goal on first line\nLine 2\nLine 3"
            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt=system_prompt
            )

            _ = agent.crew_agent
            call_kwargs = mock_crew_agent.call_args[1]
            assert call_kwargs['goal'] == "Agent goal on first line"


class TestIssueCreation:
    """Test issue creation helper method."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_create_issue_basic(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test creating a basic issue."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            issue = agent._create_issue(
                id="test-001",
                type="missing_value",
                severity="medium",
                description="Column X has missing values"
            )

            assert isinstance(issue, Issue)
            assert issue.id == "test-001"
            assert issue.type == "missing_value"
            assert issue.severity == "medium"
            assert issue.message == "Column X has missing values"
            assert issue.location is None
            assert issue.detected_by == "TestAgent"
            assert issue.phase == Phase.PHASE_1

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_create_issue_with_location(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test creating an issue with location."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="ValidatorAgent",
                phase=Phase.PHASE_2,
                system_prompt="Test prompt"
            )

            issue = agent._create_issue(
                id="val-002",
                type="syntax_error",
                severity="critical",
                description="Invalid Python syntax",
                location="cell_5"
            )

            assert issue.id == "val-002"
            assert issue.type == "syntax_error"
            assert issue.severity == "critical"
            assert issue.message == "Invalid Python syntax"
            assert issue.location == "cell_5"
            assert issue.detected_by == "ValidatorAgent"
            assert issue.phase == Phase.PHASE_2

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_create_issue_all_severities(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test creating issues with all severity levels."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            for severity in ["low", "medium", "high", "critical"]:
                issue = agent._create_issue(
                    id=f"issue-{severity}",
                    type="test_issue",
                    severity=severity,
                    description=f"Test {severity} issue"
                )
                assert issue.severity == severity


class TestProcessMethod:
    """Test abstract process method."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_process_implemented(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test that concrete agent implements process method."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            state = MagicMock(spec=AnalysisState)
            result = agent.process(state)

            assert isinstance(result, dict)
            assert result["test"] == "result"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_process_not_implemented_raises(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test that BaseAgent without process implementation cannot be instantiated."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            # Cannot instantiate abstract class
            with pytest.raises(TypeError, match="Can't instantiate abstract class"):
                agent = BaseAgent(
                    name="TestAgent",
                    phase=Phase.PHASE_1,
                    system_prompt="Test prompt"
                )


class TestLLMAgentAccess:
    """Test LLM agent access."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_llm_agent_accessible(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test that llm_agent is accessible."""
        mock_llm_instance = MagicMock()
        mock_llm_agent.return_value = mock_llm_instance

        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            assert agent.llm_agent == mock_llm_instance

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_crew_agent_accessible(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test that crew_agent is accessible."""
        mock_crew_instance = MagicMock()
        mock_crew_agent.return_value = mock_crew_instance

        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            assert agent.crew_agent == mock_crew_instance


class TestProviderStringFormatting:
    """Test provider string formatting for different LLM providers."""

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_gemini_string_format(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test Gemini provider uses string format to avoid API key check."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "gemini"
            mock_settings.llm.gemini_model = "gemini-1.5-flash"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            _ = agent.crew_agent
            call_kwargs = mock_crew_agent.call_args[1]
            # Verify string format is used (not LangChain object)
            assert isinstance(call_kwargs['llm'], str)
            assert call_kwargs['llm'] == "gemini/gemini-1.5-flash"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_anthropic_string_format(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test Anthropic provider uses string format for consistency."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "anthropic"
            mock_settings.llm.anthropic_model = "claude-3-5-sonnet-20241022"
            mock_settings.llm.anthropic_api_key = "test-key"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            _ = agent.crew_agent
            call_kwargs = mock_crew_agent.call_args[1]
            assert isinstance(call_kwargs['llm'], str)
            assert call_kwargs['llm'] == "anthropic/claude-3-5-sonnet-20241022"

    @patch('src.agents.base.LLMAgent')
    @patch('src.agents.base.get_llm')
    @patch('src.agents.base.CrewAgent')
    def test_openai_string_format(self, mock_crew_agent, mock_get_llm, mock_llm_agent):
        """Test OpenAI provider uses string format."""
        with patch('src.agents.base.settings') as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.openai_model = "gpt-4"

            agent = ConcreteAgent(
                name="TestAgent",
                phase=Phase.PHASE_1,
                system_prompt="Test prompt"
            )

            _ = agent.crew_agent
            call_kwargs = mock_crew_agent.call_args[1]
            # OpenAI now uses string format
            assert isinstance(call_kwargs['llm'], str)
            assert call_kwargs['llm'] == "openai/gpt-4"
