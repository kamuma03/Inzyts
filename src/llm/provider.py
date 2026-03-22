"""
LLM provider abstraction for Ollama, Anthropic, OpenAI, and Gemini.

This module acts as a factory for creating LangChain Chat Model instances.
It abstracts away the differences in initialization (API keys, base URLs,
model names) so that the rest of the system can request an LLM by name.
"""

from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

from src.config import settings
from src.utils.errors import LLMError, ConfigurationError
from src.utils.logger import get_logger

logger = get_logger()

# Token estimation constant (average characters per token)
CHARS_PER_TOKEN_ESTIMATE = 4


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """
    Factory function to get a configured LLM instance.

    Handles provider-specific import logic (lazy loading) and configuration
    to prevent dependency errors if a provider's package is missing but unused.

    Args:
        provider: Provider name ("ollama", "anthropic", "openai", "gemini").
                  Defaults to settings.llm.default_provider.
        model: Specific model name override.
        temperature: Sampling temperature override.

    Returns:
        A ready-to-use LangChain BaseChatModel instance.

    Raises:
        ValueError: If the provider is unknown or API keys are missing.
    """
    provider = provider or settings.llm.default_provider
    temperature = temperature if temperature is not None else settings.llm.temperature

    if provider == "ollama":
        # Lazy import to avoid hard dependency if not using Ollama
        from langchain_ollama import ChatOllama

        target_model = model or settings.llm.ollama_model
        return ChatOllama(
            model=target_model,
            temperature=temperature,
            base_url=settings.llm.ollama_base_url,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = settings.llm.anthropic_api_key
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY not set")

        target_model = model or settings.llm.anthropic_model
        from pydantic import SecretStr

        return ChatAnthropic(  # type: ignore
            model=target_model,
            temperature=temperature,
            api_key=SecretStr(api_key),
            max_tokens=settings.llm.max_tokens,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI  # type: ignore

        api_key = settings.llm.openai_api_key
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY not set")

        target_model = model or settings.llm.openai_model
        return ChatOpenAI(
            model=target_model,
            temperature=temperature,
            api_key=api_key,
            max_tokens=settings.llm.max_tokens,
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = settings.llm.google_api_key
        if not api_key:
            raise ConfigurationError("GOOGLE_API_KEY not set")

        target_model = model or settings.llm.gemini_model
        return ChatGoogleGenerativeAI(
            model=target_model,
            temperature=temperature,
            google_api_key=api_key,
            convert_system_message_to_human=True,
            max_output_tokens=settings.llm.max_tokens,
        )

    else:
        raise ConfigurationError(f"Unknown LLM provider: {provider}")


class LLMAgent:
    """
    Wrapper for LLM interactions with structured prompting.

    Provides a simplified interface for invoking LLMs with system instructions,
    managing token usage (where possible), and enforcing JSON output formats.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """
        Initialize the LLM agent wrapper.

        Args:
            name: Name of the agent (for logging).
            system_prompt: Permanent system instruction.
            provider: LLM provider.
            model: Model name.
            temperature: Sampling temperature.
        """
        self.name = name
        self.system_prompt = system_prompt
        self.provider = provider or settings.llm.default_provider
        self.llm = get_llm(self.provider, model, temperature)
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(
            (
                ConnectionError,
                TimeoutError,
                httpx.HTTPStatusError,
                httpx.RemoteProtocolError,
            )
        ),
        reraise=True,
    )
    def invoke(self, prompt: str) -> str:
        """
        Invoke the LLM with a user prompt.

        Args:
            prompt: The user input or task description.

        Returns:
            The raw string response from the LLM.
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.llm.invoke(messages)

        # Track token usage if provided in response metadata.
        # LangChain normalises provider-specific keys into usage_metadata with
        # input_tokens / output_tokens (matching the Anthropic / OpenAI field names).
        prompt_tok = 0
        completion_tok = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            prompt_tok = int(meta.get("input_tokens", 0))
            completion_tok = int(meta.get("output_tokens", 0))

        # Fallback estimation when metadata is absent (e.g. Ollama local models).
        if prompt_tok == 0 and completion_tok == 0 and response.content:
            prompt_tok = len(prompt) // CHARS_PER_TOKEN_ESTIMATE
            completion_tok = len(response.content) // CHARS_PER_TOKEN_ESTIMATE

        tokens = prompt_tok + completion_tok
        self.prompt_tokens += prompt_tok
        self.completion_tokens += completion_tok
        self.total_tokens += tokens

        # Log granular token usage
        logger.log_token_usage(
            component=self.name,
            tokens=tokens,
            model=getattr(self.llm, "model_name", "unknown"),
        )

        return str(response.content)

    def invoke_with_json(self, prompt: str) -> str:
        """
        Invoke the LLM expecting a JSON response.

        Appends explicit formatting instructions to the prompt to maximize
        the chance of receiving valid JSON.

        Args:
            prompt: The user input.

        Returns:
            Review raw string options.
        """
        json_prompt = (
            f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        )
        response = self.invoke(json_prompt)

        import re
        
        # Strip markdown code blocks if present
        cleaned_response = response.strip()
        
        # Look for JSON between ```json and ```
        json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned_response, re.DOTALL)
        if json_match:
            cleaned_response = json_match.group(1)
        else:
            # Try to find the first { or [ and last } or ]
            start_idx = -1
            end_idx = -1
            
            # Find first { or [
            for i, char in enumerate(cleaned_response):
                if char in ('{', '['):
                    start_idx = i
                    break
                    
            # Find last } or ]
            for i in range(len(cleaned_response)-1, -1, -1):
                if cleaned_response[i] in ('}', ']'):
                    end_idx = i
                    break
                    
            if start_idx != -1 and end_idx != -1 and start_idx <= end_idx:
                cleaned_response = cleaned_response[start_idx:end_idx+1]

        return cleaned_response.strip()
