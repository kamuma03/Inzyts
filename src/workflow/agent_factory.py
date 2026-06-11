import threading
from importlib import import_module
from typing import Dict, Tuple

from src.agents.base import BaseAgent

# Each entry maps an agent name → (module path, class name). Imports are
# deferred to first use to preserve the lazy-load behaviour the older
# `_make_X()` helpers provided. Adding a new agent = one line here.
_AGENT_REGISTRY: Dict[str, Tuple[str, str]] = {
    "orchestrator":             ("src.agents.orchestrator", "OrchestratorAgent"),
    "sql_extraction":           ("src.agents.sql_agent", "SQLExtractionAgent"),
    "api_extraction":           ("src.agents.api_agent", "APIExtractionAgent"),
    "data_merger":              ("src.agents.phase1.data_merger", "DataMergerAgent"),
    "data_profiler":            ("src.agents.phase1.data_profiler", "DataProfilerAgent"),
    "profile_codegen":          ("src.agents.phase1.profile_codegen", "ProfileCodeGeneratorAgent"),
    "profile_validator":        ("src.agents.phase1.profile_validator", "ProfileValidatorAgent"),
    "exploratory_conclusions":  ("src.agents.phase1.exploratory_conclusions", "ExploratoryConclusionsAgent"),
    "strategy":                 ("src.agents.phase2.strategy", "StrategyAgent"),
    "analysis_codegen":         ("src.agents.phase2.analysis_codegen", "AnalysisCodeGeneratorAgent"),
    "analysis_validator":       ("src.agents.phase2.analysis_validator", "AnalysisValidatorAgent"),
    "forecasting_extension":    ("src.agents.extensions", "ForecastingExtensionAgent"),
    "comparative_extension":    ("src.agents.extensions", "ComparativeExtensionAgent"),
    "diagnostic_extension":     ("src.agents.extensions", "DiagnosticExtensionAgent"),
    "forecasting_strategy":     ("src.agents.phase2.configurable_strategy", "ForecastingStrategyAgent"),
    "comparative_strategy":     ("src.agents.phase2.configurable_strategy", "ComparativeStrategyAgent"),
    "diagnostic_strategy":      ("src.agents.phase2.configurable_strategy", "DiagnosticStrategyAgent"),
    "segmentation_strategy":    ("src.agents.phase2.configurable_strategy", "SegmentationStrategyAgent"),
    "dimensionality_strategy":  ("src.agents.phase2", "DimensionalityStrategyAgent"),
    "cell_edit":                ("src.agents.cell_edit_agent", "CellEditAgent"),
    "follow_up":                ("src.agents.follow_up_agent", "FollowUpAgent"),
}


class AgentFactory:
    """Factory for creating and caching agent instances within a single job run.

    Token-tracking note: Each agent's LLMAgent wrapper accumulates ``total_tokens``
    across its lifetime. Graph nodes use a *delta* pattern (now in
    ``_track`` / ``_attribute_tokens`` in ``src.workflow.graph``) to isolate
    per-call usage. ``AgentFactory.reset()`` is called at the start of each
    Celery task and in tests to discard stale instances.
    """

    _instances: Dict[str, BaseAgent] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_agent(cls, agent_name: str) -> BaseAgent:
        """Get or create a singleton instance of the requested agent."""
        with cls._lock:
            if agent_name in cls._instances:
                return cls._instances[agent_name]

            entry = _AGENT_REGISTRY.get(agent_name)
            if entry is None:
                raise ValueError(
                    f"Unknown agent name: '{agent_name}'. "
                    f"Available: {sorted(_AGENT_REGISTRY)}"
                )

            module_path, class_name = entry
            agent_cls = getattr(import_module(module_path), class_name)
            agent = agent_cls()
            cls._instances[agent_name] = agent
            return agent

    @classmethod
    def reset(cls) -> None:
        """Reset instances (called at the start of each Celery task and in tests).

        Agents may hold disposable resources (e.g. a pooled validation kernel);
        give each a chance to release them via an optional ``close()`` hook so a
        long-lived worker process doesn't leak kernel subprocesses between jobs.
        """
        with cls._lock:
            for agent in cls._instances.values():
                close = getattr(agent, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            cls._instances = {}

    @classmethod
    def registered_agents(cls) -> Tuple[str, ...]:
        """Names of all registered agents (read-only view of the registry)."""
        return tuple(_AGENT_REGISTRY)

    @classmethod
    def validate_registry(cls) -> None:
        """Resolve every registry entry's ``(module, class)`` without
        instantiating it.

        Catches a typo or a moved/renamed agent class at import time (e.g. in a
        startup smoke test or CI) instead of at the first job run that happens
        to route to that agent. Raises ``RuntimeError`` listing every bad entry.
        """
        broken = []
        for name, (module_path, class_name) in _AGENT_REGISTRY.items():
            try:
                getattr(import_module(module_path), class_name)
            except (ImportError, AttributeError) as e:
                broken.append(f"{name}: {module_path}.{class_name} → {e}")
        if broken:
            raise RuntimeError(
                "Invalid agent registry entries:\n  " + "\n  ".join(broken)
            )
