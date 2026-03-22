"""
Base Agent class - Foundation for all agents.

This module defines the abstract base class that all agents within the
system must inherit from. It bridges the gap between our custom Pydantic-based
workflow (LangGraph) and the agentic capabilities of CrewAI.

Key Features:
- Hybrid Architecture: Wraps CrewAI's `Agent` for potential autonomous behavior
  while maintaining strict state control via LangGraph.
- LLM Abstraction: Handles provider-specific initialization logic (e.g., Gemini
  vs OpenAI vs Anthropic).
- Standardized Interface: Defines the abstract `process` method that all agents
  must implement.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from crewai import Agent as CrewAgent

from src.config import settings
from src.llm.provider import get_llm, LLMAgent
from src.models.state import AnalysisState, Phase
from src.models.common import Issue


class BaseAgent(ABC):
    """
    Base class for all agents in the system.

    Integrates CrewAI for agent definition while maintaining
    the custom Pydantic-based workflow. Every specific agent (Profiler,
    Strategy, etc.) inherits from this.
    """

    def __init__(
        self,
        name: str,
        phase: Phase,
        system_prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the agent.

        Sets up two distinct LLM interfaces:
        1. self.llm_agent: A custom wrapper for direct, structured IO (used by most logic).
        2. self.crew_agent: A CrewAI Agent instance for potential future autonomous tasks.

        Args:
            name: The human-readable name of the agent.
            phase: The high-level phase this agent operates in (Phase 1, 2, or Orchestrator).
            system_prompt: The core personality and instruction set for the agent.
            provider: Optional override for the LLM provider (e.g., force 'openai').
            model: Optional override for the specific model name.
        """
        self.name = name
        self.phase = phase
        self.system_prompt = system_prompt

        self.llm_agent = LLMAgent(
            name=name,
            provider=provider or settings.llm.default_provider,
            model=model,
            system_prompt=system_prompt,
        )

        # Internal storage for lazy CrewAI initialization
        self._crew_agent: Optional[CrewAgent] = None
        self._provider_override = provider
        self._model_override = model

    @property
    def crew_agent(self) -> CrewAgent:
        """Lazily create and return a CrewAI Agent using a string-format LLM."""
        if self._crew_agent is None:
            provider = self._provider_override or settings.llm.default_provider
            model_map = {
                "openai": settings.llm.openai_model,
                "anthropic": settings.llm.anthropic_model,
                "gemini": settings.llm.gemini_model,
                "ollama": settings.llm.ollama_model,
            }
            model_name = self._model_override or model_map.get(provider, "")
            llm_string = f"{provider}/{model_name}"

            goal = self.system_prompt.split("\n", 1)[0]
            self._crew_agent = CrewAgent(
                role=self.name,
                goal=goal,
                backstory=self.system_prompt,
                llm=llm_string,
                allow_delegation=False,
                verbose=True,
                memory=False,
            )
        return self._crew_agent

    @abstractmethod
    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Process the current state and return updates.

        This is the main entry point for the agent's logic when called within a
        LangGraph node.

        Args:
            state: Current analysis state object containing the full history.
            **kwargs: Additional arguments specific to the agent's task.

        Returns:
            Dictionary of state updates to be merged into the global state.
        """
        raise NotImplementedError("Subclasses must implement process()")

    def _create_issue(
        self,
        id: str,
        type: str,
        severity: str,
        description: str,
        location: Optional[str] = None,
    ) -> Issue:
        """
        Helper factory method to create standardised Issue objects.

        Args:
            id: Unique identifier for the issue.
            type: Category of issue (e.g., 'missing_value', 'syntax_error').
            severity: Standardized severity (low, medium, high, critical).
            description: Human-readable explanation.
            location: Where the issue occurred (e.g., cell number, column name).

        Returns:
            A populated Issue model.
        """
        return Issue(
            id=id,
            type=type,
            severity=severity,
            message=description,
            location=location,
            detected_by=self.name,
            phase=self.phase,
        )
