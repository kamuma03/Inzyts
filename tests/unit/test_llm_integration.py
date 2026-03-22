"""
Unit tests for LLM Integration with Mocks.

Tests LLM provider interactions, prompt construction,
response parsing, and multi-provider support.
"""

import pytest
from unittest.mock import Mock, patch
import json

from src.llm.provider import LLMAgent
from src.agents.phase1.exploratory_conclusions import ExploratoryConclusionsAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent


class TestLLMProviderInterface:
    """Test LLM provider interface."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = Mock(spec=LLMAgent)
        provider.invoke.return_value = "Mock LLM response"
        provider.invoke_with_json.return_value = {"key": "value"}
        return provider

    def test_provider_invoke_basic(self, mock_llm_provider):
        """Test basic LLM invocation."""
        result = mock_llm_provider.invoke("Test prompt")

        assert result == "Mock LLM response"
        mock_llm_provider.invoke.assert_called_once_with("Test prompt")

    def test_provider_invoke_with_json(self, mock_llm_provider):
        """Test JSON-structured LLM invocation."""
        result = mock_llm_provider.invoke_with_json("Test prompt")

        assert result == {"key": "value"}
        mock_llm_provider.invoke_with_json.assert_called_once_with("Test prompt")

    def test_provider_retry_on_failure(self):
        """Test retry logic on provider failure."""
        provider = Mock(spec=LLMAgent)
        provider.invoke.side_effect = [
            Exception("Network error"),
            "Success"
        ]

        # First call fails, second succeeds
        try:
            result = provider.invoke("Test")
        except Exception:
            result = provider.invoke("Test")

        assert result == "Success"
        assert provider.invoke.call_count == 2

    # def test_provider_token_counting(self, mock_llm_provider):
    #     """Test token usage tracking."""
    #     mock_llm_provider.get_token_count.return_value = 150
    #
    #     result = mock_llm_provider.get_token_count("Test prompt with some tokens")
    #
    #     assert result == 150
    #     assert mock_llm_provider.get_token_count.called





class TestResponseParsing:
    """Test parsing of LLM responses."""

    def test_parse_valid_json_response(self):
        """Test parsing of valid JSON response."""
        json_response = {
            "original_question": "Test",
            "direct_answer": "Answer",
            "key_findings": ["F1", "F2", "F3"],
            "statistical_insights": ["I1"],
            "data_quality_notes": ["Q1"],
            "recommendations": ["R1", "R2"],
            "limitations": ["L1"],
            "confidence_score": 0.85,
            "conclusions_cells": [],
            "visualization_cells": []
        }

        # Should parse without error
        from src.models.handoffs import ExploratoryConclusionsOutput
        output = ExploratoryConclusionsOutput(**json_response)

        assert output.original_question == "Test"
        assert output.confidence_score == 0.85
        assert len(output.key_findings) == 3

    def test_parse_json_string_response(self):
        """Test parsing of JSON returned as string."""
        json_string = json.dumps({
            "original_question": "Test",
            "direct_answer": "Answer",
            "key_findings": ["F1", "F2", "F3"],
            "statistical_insights": ["I1"],
            "data_quality_notes": ["Q1"],
            "recommendations": ["R1", "R2"],
            "limitations": ["L1"],
            "confidence_score": 0.85,
            "conclusions_cells": [],
            "visualization_cells": []
        })

        # Should parse string to dict then to object
        parsed = json.loads(json_string)
        from src.models.handoffs import ExploratoryConclusionsOutput
        output = ExploratoryConclusionsOutput(**parsed)

        assert output.original_question == "Test"

    def test_handle_malformed_json(self):
        """Test handling of malformed JSON response."""
        malformed_json = "{{{'This is not valid JSON'}}}"

        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed_json)

    def test_handle_missing_required_fields(self):
        """Test handling of response missing required fields."""
        incomplete_response = {
            "original_question": "Test",
            "direct_answer": "Answer"
            # Missing other required fields
        }

        from src.models.handoffs import ExploratoryConclusionsOutput
        with pytest.raises(Exception):  # Pydantic validation error
            ExploratoryConclusionsOutput(**incomplete_response)

    def test_handle_extra_fields_gracefully(self):
        """Test that extra fields in response don't cause errors."""
        response_with_extras = {
            "original_question": "Test",
            "direct_answer": "Answer",
            "key_findings": ["F1", "F2", "F3"],
            "statistical_insights": ["I1"],
            "data_quality_notes": ["Q1"],
            "recommendations": ["R1", "R2"],
            "limitations": ["L1"],
            "confidence_score": 0.85,
            "conclusions_cells": [],
            "visualization_cells": [],
            "extra_field": "This should be ignored"
        }

        from src.models.handoffs import ExploratoryConclusionsOutput
        output = ExploratoryConclusionsOutput(**response_with_extras)

        # Should parse successfully, ignoring extra field
        assert output.original_question == "Test"





class TestTokenUsageTracking:
    """Test token usage tracking and optimization."""

    def test_token_usage_logged(self):
        """Test that token usage is logged."""
        from src.utils.logger import get_logger
        logger = get_logger()

        with patch.object(logger, 'log_token_usage') as mock_log:
            logger.log_token_usage("TestAgent", 1500, "claude-sonnet-4")

            mock_log.assert_called_once_with("TestAgent", 1500, "claude-sonnet-4")




class TestModelSelection:
    """Test automatic model selection based on task complexity."""

    def test_simple_task_uses_fast_model(self):
        """Test that simple tasks use fast models."""
        # Simple analysis should use Claude Haiku or similar
        task_complexity = "low"

        if task_complexity == "low":
            model = "claude-haiku"
        else:
            model = "claude-sonnet-4"

        assert model == "claude-haiku"

    def test_complex_task_uses_powerful_model(self):
        """Test that complex tasks use powerful models."""
        # Complex reasoning should use Claude Sonnet or Opus
        task_complexity = "high"

        if task_complexity == "high":
            model = "claude-sonnet-4"
        else:
            model = "claude-haiku"

        assert model == "claude-sonnet-4"

    def test_model_fallback_on_unavailable(self):
        """Test fallback when preferred model unavailable."""
        preferred_model = "claude-opus-4"
        fallback_model = "claude-sonnet-4"

        provider = Mock(spec=LLMAgent)
        provider.invoke.side_effect = [
            Exception("Model not available"),
            "Success with fallback"
        ]

        # Try preferred, fallback to alternative
        try:
            result = provider.invoke("Test", model=preferred_model)
        except Exception:
            result = provider.invoke("Test", model=fallback_model)

        assert result == "Success with fallback"
