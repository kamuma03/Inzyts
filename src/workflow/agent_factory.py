import threading
from typing import Callable, Dict
from src.agents.base import BaseAgent


def _make_orchestrator():
    from src.agents.orchestrator import OrchestratorAgent
    return OrchestratorAgent()

def _make_sql_extraction():
    from src.agents.sql_agent import SQLExtractionAgent
    return SQLExtractionAgent()

def _make_api_extraction():
    from src.agents.api_agent import APIExtractionAgent
    return APIExtractionAgent()

def _make_data_merger():
    from src.agents.phase1.data_merger import DataMergerAgent
    return DataMergerAgent()

def _make_data_profiler():
    from src.agents.phase1.data_profiler import DataProfilerAgent
    return DataProfilerAgent()

def _make_profile_codegen():
    from src.agents.phase1.profile_codegen import ProfileCodeGeneratorAgent
    return ProfileCodeGeneratorAgent()

def _make_profile_validator():
    from src.agents.phase1.profile_validator import ProfileValidatorAgent
    return ProfileValidatorAgent()

def _make_exploratory_conclusions():
    from src.agents.phase1.exploratory_conclusions import ExploratoryConclusionsAgent
    return ExploratoryConclusionsAgent()

def _make_strategy():
    from src.agents.phase2.strategy import StrategyAgent
    return StrategyAgent()

def _make_analysis_codegen():
    from src.agents.phase2.analysis_codegen import AnalysisCodeGeneratorAgent
    return AnalysisCodeGeneratorAgent()

def _make_analysis_validator():
    from src.agents.phase2.analysis_validator import AnalysisValidatorAgent
    return AnalysisValidatorAgent()

def _make_forecasting_extension():
    from src.agents.extensions import ForecastingExtensionAgent
    return ForecastingExtensionAgent()

def _make_comparative_extension():
    from src.agents.extensions import ComparativeExtensionAgent
    return ComparativeExtensionAgent()

def _make_diagnostic_extension():
    from src.agents.extensions import DiagnosticExtensionAgent
    return DiagnosticExtensionAgent()

def _make_forecasting_strategy():
    from src.agents.phase2 import ForecastingStrategyAgent
    return ForecastingStrategyAgent()

def _make_comparative_strategy():
    from src.agents.phase2 import ComparativeStrategyAgent
    return ComparativeStrategyAgent()

def _make_diagnostic_strategy():
    from src.agents.phase2 import DiagnosticStrategyAgent
    return DiagnosticStrategyAgent()

def _make_segmentation_strategy():
    from src.agents.phase2 import SegmentationStrategyAgent
    return SegmentationStrategyAgent()

def _make_dimensionality_strategy():
    from src.agents.phase2 import DimensionalityStrategyAgent
    return DimensionalityStrategyAgent()

def _make_cell_edit():
    from src.agents.cell_edit_agent import CellEditAgent
    return CellEditAgent()

def _make_follow_up():
    from src.agents.follow_up_agent import FollowUpAgent
    return FollowUpAgent()


# Registry maps agent name -> factory callable. All imports are deferred inside
# each factory function to preserve lazy-loading behaviour. Adding a new agent
# only requires adding one entry here.
_AGENT_REGISTRY: Dict[str, Callable[[], BaseAgent]] = {
    "orchestrator": _make_orchestrator,
    "sql_extraction": _make_sql_extraction,
    "api_extraction": _make_api_extraction,
    "data_merger": _make_data_merger,
    "data_profiler": _make_data_profiler,
    "profile_codegen": _make_profile_codegen,
    "profile_validator": _make_profile_validator,
    "exploratory_conclusions": _make_exploratory_conclusions,
    "strategy": _make_strategy,
    "analysis_codegen": _make_analysis_codegen,
    "analysis_validator": _make_analysis_validator,
    "forecasting_extension": _make_forecasting_extension,
    "comparative_extension": _make_comparative_extension,
    "diagnostic_extension": _make_diagnostic_extension,
    "forecasting_strategy": _make_forecasting_strategy,
    "comparative_strategy": _make_comparative_strategy,
    "diagnostic_strategy": _make_diagnostic_strategy,
    "segmentation_strategy": _make_segmentation_strategy,
    "dimensionality_strategy": _make_dimensionality_strategy,
    "cell_edit": _make_cell_edit,
    "follow_up": _make_follow_up,
}


class AgentFactory:
    """Factory for creating and caching agent instances within a single job run.

    Token-tracking note: Each agent's LLMAgent wrapper accumulates ``total_tokens``
    across its lifetime. Graph nodes use a *delta* pattern to isolate per-call usage::

        start_tokens = agent.llm_agent.total_tokens
        result = agent.process(state, ...)
        tokens_used = agent.llm_agent.total_tokens - start_tokens

    This means the accumulator itself is harmless as long as agents are not shared
    across Celery jobs. ``AgentFactory.reset()`` is called at the start of each
    ``execution_task`` to discard stale instances and prevent cross-job token
    count contamination in shared-worker-process deployments.
    """

    _instances: Dict[str, BaseAgent] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_agent(cls, agent_name: str) -> BaseAgent:
        """Get or create a singleton instance of the requested agent."""
        with cls._lock:
            if agent_name in cls._instances:
                return cls._instances[agent_name]

            factory = _AGENT_REGISTRY.get(agent_name)
            if factory is None:
                raise ValueError(f"Unknown agent name: '{agent_name}'. "
                                 f"Available: {sorted(_AGENT_REGISTRY)}")

            agent = factory()
            cls._instances[agent_name] = agent
            return agent

    @classmethod
    def reset(cls):
        """Reset instances (called at the start of each Celery task and in tests)."""
        with cls._lock:
            cls._instances = {}
