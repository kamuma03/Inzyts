import pytest
from src.workflow.agent_factory import AgentFactory
from src.agents.base import BaseAgent

def test_get_agent_creates_instance():
    """Test that getting an agent creates it if it doesn't exist."""
    AgentFactory.reset()
    
    agent = AgentFactory.get_agent("orchestrator")
    assert isinstance(agent, BaseAgent)
    assert "orchestrator" in AgentFactory._instances

def test_get_agent_singleton_behavior():
    """Test that requesting the same agent returns the exact same instance."""
    AgentFactory.reset()
    
    agent1 = AgentFactory.get_agent("data_profiler")
    agent2 = AgentFactory.get_agent("data_profiler")
    
    assert agent1 is agent2

def test_all_known_agents():
    """Test that all supported agents can be instantiated without errors."""
    AgentFactory.reset()
    
    known_agents = [
        "orchestrator",
        "data_merger",
        "data_profiler",
        "profile_codegen",
        "profile_validator",
        "exploratory_conclusions",
        "strategy",
        "analysis_codegen",
        "analysis_validator",
        "forecasting_extension",
        "comparative_extension",
        "diagnostic_extension",
        "forecasting_strategy",
        "comparative_strategy",
        "diagnostic_strategy",
        "segmentation_strategy",
        "dimensionality_strategy",
        "sql_extraction",
        "api_extraction",
    ]
    
    for agent_name in known_agents:
        agent = AgentFactory.get_agent(agent_name)
        assert isinstance(agent, BaseAgent)

def test_unknown_agent_raises_error():
    """Test that an unknown agent name raises a ValueError."""
    AgentFactory.reset()
    
    with pytest.raises(ValueError, match="Unknown agent name:.*fake_agent"):
        AgentFactory.get_agent("fake_agent")

def test_reset():
    """Test that reset clears the cached instances."""
    AgentFactory.reset()
    AgentFactory.get_agent("orchestrator")
    
    assert len(AgentFactory._instances) > 0
    
    AgentFactory.reset()
    assert len(AgentFactory._instances) == 0
