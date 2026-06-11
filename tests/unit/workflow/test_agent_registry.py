"""Guard against agent-registry drift and typo'd ``get_agent`` call sites.

The factory resolves agent names lazily, so a renamed class or a mistyped
``get_agent("...")`` only blows up at the job run that routes to it. These
tests turn that into a fast, deterministic failure.
"""

import re
from pathlib import Path

from src.workflow.agent_factory import AgentFactory

_GRAPH_PY = Path(__file__).resolve().parents[3] / "src" / "workflow" / "graph.py"


def test_every_registry_entry_resolves():
    """All (module, class) entries import cleanly."""
    AgentFactory.validate_registry()  # raises RuntimeError on any bad entry


def test_graph_get_agent_calls_are_registered():
    """Every ``AgentFactory.get_agent("name")`` literal in graph.py exists."""
    source = _GRAPH_PY.read_text()
    referenced = set(re.findall(r"get_agent\(\s*[\"']([a-z0-9_]+)[\"']", source))
    registered = set(AgentFactory.registered_agents())
    missing = referenced - registered
    assert not missing, f"graph.py references unregistered agents: {sorted(missing)}"
