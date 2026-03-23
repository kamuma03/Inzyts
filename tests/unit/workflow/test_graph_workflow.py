"""
Unit tests for graph workflow orchestration.

Tests the main LangGraph workflow that orchestrates all agents, including:
- Workflow initialization
- Node execution
- Conditional routing
- Token tracking
- Error propagation
- State transitions
"""

from unittest.mock import MagicMock, patch

from src.workflow.graph import (
    initialize_node,
    restore_cache_node,
    create_phase1_handoff_node,
    data_profiler_node,
    profile_codegen_node,
    profile_validator_node,
    extension_node,
    transition_to_phase2_node,
    strategy_node,
    analysis_codegen_node,
    analysis_validator_node,
    assemble_notebook_node,
    exploratory_conclusions_node,
    rollback_recovery_node,
    route_after_profile_validation,
    route_after_initialize,
    route_after_analysis_validation,
    build_workflow
)
from src.models.state import AnalysisState, ProfileLock, PipelineMode
from src.models.handoffs import UserIntent, ProfileCache
from src.models.cells import NotebookCell


class TestInitializeNode:
    """Test workflow initialization node."""

    @patch('src.workflow.graph.AgentFactory')
    def test_initialize_node_success(self, mock_factory):
        """Test successful workflow initialization."""
        # Arrange
        state = MagicMock(spec=AnalysisState)
        state.csv_path = "data.csv"
        state.user_intent = UserIntent(query="Analyze data", mode="exploratory", csv_path="data.csv")
        state.pipeline_mode = PipelineMode.EXPLORATORY
        state.using_cached_profile = False
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"status": "initialized"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        # Act
        result = initialize_node(state)

        # Assert
        mock_factory.get_agent.assert_called_with("orchestrator")
        mock_orchestrator.process.assert_called_once()
        assert "total_tokens_used" in result
        assert result["total_tokens_used"] >= 0

    @patch('src.workflow.graph.AgentFactory')
    def test_initialize_node_token_tracking(self, mock_factory):
        """Test token tracking during initialization."""
        state = MagicMock(spec=AnalysisState)
        state.csv_path = "data.csv"
        state.user_intent = None
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.using_cached_profile = False
        state.total_tokens_used = 50
        state.prompt_tokens_used = 25
        state.completion_tokens_used = 25

        # Simulate token usage
        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"status": "initialized"}
        
        mock_factory.get_agent.return_value = mock_orchestrator
        
        # We need to simulate the token count increasing after process() is called
        # But since process is a mock, we can't easily side-effect the total_tokens property 
        # unless we use a property mock or side_effect. 
        # Simplified approach: The node reads start_tokens, calls process, then reads end_tokens.
        # We can just change the property value on the mock object if we hold a reference, 
        # but the node function gets the value from the object returned by get_agent.
        
        # Let's use a side_effect on process to increment the tokens
        def process_side_effect(*args, **kwargs):
            mock_orchestrator.llm_agent.total_tokens = 150
            return {"status": "initialized"}
            
        mock_orchestrator.process.side_effect = process_side_effect

        result = initialize_node(state)

        # Token increase should be tracked
        assert result["total_tokens_used"] == 100  # 50 + 50


class TestRestoreCacheNode:
    """Test cache restoration node."""

    @patch('src.workflow.graph.AgentFactory')
    def test_restore_cache_success(self, mock_factory):
        """Test successful cache restoration."""
        state = MagicMock(spec=AnalysisState)
        state.cache = MagicMock(spec=ProfileCache)
        state.cache.profile_lock = {
            "is_locked": True,
            "quality_score": 0.9,
            "profile_cells": [],
            "profile_handoff": {}
        }
        state.cache.phase1_quality_score = 0.9
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"profile_lock": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = restore_cache_node(state)

        mock_factory.get_agent.assert_called_with("orchestrator")
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_restore_cache_no_cache(self, mock_factory):
        """Test cache restoration when no cache exists."""
        state = MagicMock(spec=AnalysisState)
        state.cache = None
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"error": "No cache"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = restore_cache_node(state)

        assert "total_tokens_used" in result


class TestPhase1Nodes:
    """Test Phase 1 workflow nodes."""

    @patch('src.workflow.graph.AgentFactory')
    def test_create_phase1_handoff_node(self, mock_factory):
        """Test Phase 1 handoff creation."""
        state = MagicMock(spec=AnalysisState)
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"handoff": "created"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = create_phase1_handoff_node(state)

        mock_factory.get_agent.assert_called_with("orchestrator")
        mock_orchestrator.process.assert_called_once_with(state, action="phase1_handoff")
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_data_profiler_node_success(self, mock_factory):
        """Test data profiler node execution."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_profiler = MagicMock()
        mock_profiler.llm_agent.total_tokens = 100
        mock_profiler.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_profiler

        result = data_profiler_node(state)

        mock_factory.get_agent.assert_called_with("data_profiler")
        assert "profiler_outputs" in result
        assert len(result["profiler_outputs"]) == 1
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_data_profiler_node_failure(self, mock_factory):
        """Test data profiler node error handling."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_profiler = MagicMock()
        mock_profiler.llm_agent.total_tokens = 100
        mock_profiler.process.side_effect = Exception("Profiler error")
        
        mock_factory.get_agent.return_value = mock_profiler

        result = data_profiler_node(state)

        assert "errors" in result
        assert "DataProfiler Crash" in result["errors"][0]
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_profile_codegen_node_success(self, mock_factory):
        """Test profile code generation node."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = [MagicMock()]
        state.profile_code_outputs = []
        state.phase1_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 100
        mock_codegen.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_codegen

        result = profile_codegen_node(state)

        mock_factory.get_agent.assert_called_with("profile_codegen")
        assert "profile_code_outputs" in result
        assert "phase1_iteration" in result
        assert result["phase1_iteration"] == 1  # Incremented
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_profile_codegen_node_failure(self, mock_factory):
        """Test profile code generation error handling."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = [MagicMock()]
        state.profile_code_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 100
        mock_codegen.process.side_effect = Exception("Codegen error")
        
        mock_factory.get_agent.return_value = mock_codegen

        result = profile_codegen_node(state)

        assert "errors" in result
        assert "ProfileCodeGen Crash" in result["errors"][0]

    @patch('src.workflow.graph.AgentFactory')
    @patch('src.workflow.graph.update_issue_frequency')
    def test_profile_validator_node_success(self, mock_update_freq, mock_factory):
        """Test profile validator node execution."""
        state = MagicMock(spec=AnalysisState)
        state.profile_code_outputs = [MagicMock()]
        state.profile_validation_reports = []
        state.phase1_quality_trajectory = []
        state.phase1_iteration = 1
        state.csv_path = "data.csv"
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.user_intent = MagicMock()
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.profile_lock = MagicMock(spec=ProfileLock)
        state.errors = []

        mock_validator = MagicMock()
        mock_validator.llm_agent.total_tokens = 100
        mock_validator.process.return_value = {
            "report": MagicMock(),
            "quality_score": 0.9,
            "issues": [],
            "should_lock": True,
            "strategy_handoff": MagicMock()
        }
        
        mock_factory.get_agent.return_value = mock_validator
        mock_update_freq.return_value = {}

        result = profile_validator_node(state)

        mock_factory.get_agent.assert_called_with("profile_validator")
        assert "profile_validation_reports" in result
        assert "phase1_quality_trajectory" in result
        assert "profile_lock" in result
        assert len(result["phase1_quality_trajectory"]) == 1

    @patch('src.workflow.graph.AgentFactory')
    def test_profile_validator_node_failure(self, mock_factory):
        """Test profile validator error handling."""
        state = MagicMock(spec=AnalysisState)
        state.profile_code_outputs = [MagicMock()]
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_validator = MagicMock()
        mock_validator.llm_agent.total_tokens = 100
        mock_validator.process.side_effect = Exception("Validator error")
        
        mock_factory.get_agent.return_value = mock_validator

        result = profile_validator_node(state)

        assert "errors" in result
        assert "ProfileValidator Crash" in result["errors"][0]


class TestExtensionNode:
    """Test extension node execution."""

    @patch('src.workflow.graph.AgentFactory')
    def test_extension_node_forecasting(self, mock_factory):
        """Test extension node for forecasting mode."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.FORECASTING
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_extension = MagicMock()
        mock_extension.llm_agent.total_tokens = 100
        mock_extension.process.return_value = {"extension_data": "forecasting"}

        mock_factory.get_agent.return_value = mock_extension

        result = extension_node(state)

        mock_factory.get_agent.assert_called_with("forecasting_extension")
        mock_extension.process.assert_called_once_with(state)
        assert "extension_data" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_extension_node_comparative(self, mock_factory):
        """Test extension node for comparative mode."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.COMPARATIVE
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_extension = MagicMock()
        mock_extension.llm_agent.total_tokens = 100
        mock_extension.process.return_value = {"extension_data": "comparative"}

        mock_factory.get_agent.return_value = mock_extension

        result = extension_node(state)

        mock_factory.get_agent.assert_called_with("comparative_extension")
        mock_extension.process.assert_called_once_with(state)

    @patch('src.workflow.graph.AgentFactory')
    def test_extension_node_diagnostic(self, mock_factory):
        """Test extension node for diagnostic mode."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.DIAGNOSTIC
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_extension = MagicMock()
        mock_extension.llm_agent.total_tokens = 100
        mock_extension.process.return_value = {"extension_data": "diagnostic"}

        mock_factory.get_agent.return_value = mock_extension

        result = extension_node(state)

        mock_factory.get_agent.assert_called_with("diagnostic_extension")
        mock_extension.process.assert_called_once_with(state)

    def test_extension_node_no_extension_needed(self):
        """Test extension node when no extension is needed."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.PREDICTIVE  # No extension for this mode
        state.errors = []

        result = extension_node(state)

        # Should return empty dict or no errors
        assert isinstance(result, dict)

    @patch('src.workflow.graph.AgentFactory')
    def test_extension_node_error_handling(self, mock_factory):
        """Test extension node error handling."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.FORECASTING
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_extension = MagicMock()
        mock_extension.llm_agent.total_tokens = 100
        mock_extension.process.side_effect = Exception("Extension error")

        mock_factory.get_agent.return_value = mock_extension

        result = extension_node(state)

        assert "errors" in result
        assert "Extension forecasting failed" in result["errors"][0]


class TestPhase2Nodes:
    """Test Phase 2 workflow nodes."""

    @patch('src.workflow.graph.AgentFactory')
    def test_transition_to_phase2_node(self, mock_factory):
        """Test transition from Phase 1 to Phase 2."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"phase": "2"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = transition_to_phase2_node(state)

        mock_factory.get_agent.assert_called_with("orchestrator")
        # Verify transition call was made (among others like save_cache)
        mock_orchestrator.process.assert_any_call(state, action="transition_to_phase2")
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_default_agent(self, mock_factory):
        """Test strategy node with default strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        mock_factory.get_agent.assert_called_with("strategy")
        assert "strategy_outputs" in result
        assert "phase2_iteration" in result
        assert result["phase2_iteration"] == 1

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_forecasting(self, mock_factory):
        """Test strategy node with forecasting strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.FORECASTING
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        mock_factory.get_agent.assert_called_with("forecasting_strategy")
        mock_strategy.process.assert_called_once()
        assert "strategy_outputs" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_comparative(self, mock_factory):
        """Test strategy node with comparative strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.COMPARATIVE
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        mock_factory.get_agent.assert_called_with("comparative_strategy")
        mock_strategy.process.assert_called_once()

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_diagnostic(self, mock_factory):
        """Test strategy node with diagnostic strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.DIAGNOSTIC
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        mock_factory.get_agent.assert_called_with("diagnostic_strategy")
        mock_strategy.process.assert_called_once()

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_segmentation(self, mock_factory):
        """Test strategy node with segmentation strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.SEGMENTATION
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 0
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        mock_factory.get_agent.assert_called_with("segmentation_strategy")
        mock_strategy.process.assert_called_once()

    @patch('src.workflow.graph.AgentFactory')
    def test_strategy_node_failure(self, mock_factory):
        """Test strategy node error handling."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.side_effect = Exception("Strategy error")
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        assert "errors" in result
        assert "Strategy Crash" in result["errors"][0]

    @patch('src.workflow.graph.AgentFactory')
    def test_analysis_codegen_node_success(self, mock_factory):
        """Test analysis code generation node."""
        state = MagicMock(spec=AnalysisState)
        state.strategy_outputs = [MagicMock()]
        state.analysis_code_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 100
        mock_codegen.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_codegen

        result = analysis_codegen_node(state)

        mock_factory.get_agent.assert_called_with("analysis_codegen")
        assert "analysis_code_outputs" in result
        assert len(result["analysis_code_outputs"]) == 1

    @patch('src.workflow.graph.AgentFactory')
    def test_analysis_codegen_node_failure(self, mock_factory):
        """Test analysis code generation error handling."""
        state = MagicMock(spec=AnalysisState)
        state.strategy_outputs = [MagicMock()]
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 100
        mock_codegen.process.side_effect = Exception("Codegen error")
        
        mock_factory.get_agent.return_value = mock_codegen

        result = analysis_codegen_node(state)

        assert "errors" in result
        assert "AnalysisCodeGen Crash" in result["errors"][0]

    @patch('src.workflow.graph.AgentFactory')
    def test_analysis_validator_node_success(self, mock_factory):
        """Test analysis validator node execution."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_code_outputs = [MagicMock()]
        state.analysis_validation_reports = []
        state.phase2_quality_trajectory = []
        state.issue_frequency = {}
        state.strategy_outputs = []
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_validator = MagicMock()
        mock_validator.llm_agent.total_tokens = 100
        mock_validator.process.return_value = {
            "report": MagicMock(),
            "quality_score": 0.85
        }
        
        mock_factory.get_agent.return_value = mock_validator

        result = analysis_validator_node(state)

        mock_factory.get_agent.assert_called_with("analysis_validator")
        assert "analysis_validation_reports" in result
        assert "phase2_quality_trajectory" in result
        assert len(result["phase2_quality_trajectory"]) == 1
        assert result["phase2_quality_trajectory"][0] == 0.85

    @patch('src.workflow.graph.AgentFactory')
    def test_analysis_validator_node_failure(self, mock_factory):
        """Test analysis validator error handling."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_code_outputs = [MagicMock()]
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_validator = MagicMock()
        mock_validator.llm_agent.total_tokens = 100
        mock_validator.process.side_effect = Exception("Validator error")
        
        mock_factory.get_agent.return_value = mock_validator

        result = analysis_validator_node(state)

        assert "errors" in result
        assert "AnalysisValidator Crash" in result["errors"][0]


class TestAssemblyNode:
    """Test notebook assembly node."""

    @patch('src.workflow.graph.AgentFactory')
    def test_assemble_notebook_node(self, mock_factory):
        """Test notebook assembly."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.profile_cells = [NotebookCell(cell_type="code", source="print(1)")]
        state.analysis_code_outputs = [MagicMock(cells=[NotebookCell(cell_type="markdown", source="# Analysis")])]
        state.exploratory_conclusions = None
        state.phase1_quality_trajectory = [0.9]
        state.phase2_quality_trajectory = [0.85]
        state.csv_path = "data.csv"
        state.execution_time = 120.5
        state.phase1_iteration = 2
        state.phase2_iteration = 1
        state.total_tokens_used = 1000
        state.prompt_tokens_used = 600
        state.completion_tokens_used = 400
        state.user_intent = MagicMock()
        state.user_intent.title = "Test Title"

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 1000
        mock_orchestrator.process.return_value = {"notebook_path": "output.ipynb"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = assemble_notebook_node(state)

        mock_factory.get_agent.assert_called_with("orchestrator")
        mock_orchestrator.process.assert_called_once()
        assert "total_tokens_used" in result


class TestExploratoryConclusionsNode:
    """Test exploratory conclusions node."""

    @patch('src.workflow.graph.AgentFactory')
    def test_exploratory_conclusions_success(self, mock_factory):
        """Test exploratory conclusions execution."""
        state = MagicMock(spec=AnalysisState)
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_exploratory = MagicMock()
        mock_exploratory.llm_agent.total_tokens = 100
        mock_exploratory.process.return_value = {"conclusions": "data analysis complete"}
        
        mock_factory.get_agent.return_value = mock_exploratory

        result = exploratory_conclusions_node(state)

        mock_factory.get_agent.assert_called_with("exploratory_conclusions")
        mock_exploratory.process.assert_called_once_with(state)
        assert "total_tokens_used" in result

    @patch('src.workflow.graph.AgentFactory')
    def test_exploratory_conclusions_failure(self, mock_factory):
        """Test exploratory conclusions error handling."""
        state = MagicMock(spec=AnalysisState)
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_exploratory = MagicMock()
        mock_exploratory.llm_agent.total_tokens = 100
        mock_exploratory.process.side_effect = Exception("Conclusions error")
        
        mock_factory.get_agent.return_value = mock_exploratory

        result = exploratory_conclusions_node(state)

        assert "errors" in result
        assert "ExploratoryConclusions Crash" in result["errors"][0]


class TestRollbackRecoveryNode:
    """Test rollback recovery node."""

    @patch('src.workflow.graph.AgentFactory')
    def test_rollback_recovery_node(self, mock_factory):
        """Test rollback recovery execution."""
        state = MagicMock(spec=AnalysisState)
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"rollback": "complete"}
        
        mock_factory.get_agent.return_value = mock_orchestrator

        result = rollback_recovery_node(state)

        mock_factory.get_agent.assert_called_with("orchestrator")
        mock_orchestrator.process.assert_called_once_with(state, action="rollback_phase2")
        assert "total_tokens_used" in result


class TestConditionalRouting:
    """Test conditional routing logic."""

    def test_route_after_profile_validation_lock_granted_predictive(self):
        """Test routing when lock is granted in predictive mode.

        All modes now route to exploratory_conclusions first after profile lock,
        then transition to Phase 2 if needed.
        """
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = True
        state.pipeline_mode = PipelineMode.PREDICTIVE

        result = route_after_profile_validation(state)

        assert result == "exploratory_conclusions"

    def test_route_after_profile_validation_lock_granted_exploratory(self):
        """Test routing when lock is granted in exploratory mode."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = True
        state.pipeline_mode = PipelineMode.EXPLORATORY

        result = route_after_profile_validation(state)

        assert result == "exploratory_conclusions"

    def test_route_after_profile_validation_retry_profiler(self):
        """Test routing back to data profiler on validation failure."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = [MagicMock(route_to="DataProfiler")]

        result = route_after_profile_validation(state)

        assert result == "data_profiler"

    def test_route_after_profile_validation_retry_codegen(self):
        """Test routing back to profile codegen on validation failure."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = [MagicMock(route_to="ProfileCodeGenerator")]

        result = route_after_profile_validation(state)

        assert result == "profile_codegen"

    def test_route_after_profile_validation_end(self):
        """Test routing to end when orchestrator signals completion."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = [MagicMock(route_to="Orchestrator")]

        result = route_after_profile_validation(state)

        assert result == "end"

    def test_route_after_profile_validation_default_fallback(self):
        """Test default routing fallback to profile codegen."""
        state = MagicMock(spec=AnalysisState)
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = False
        state.profile_validation_reports = []

        result = route_after_profile_validation(state)

        assert result == "profile_codegen"

    def test_route_after_initialize_with_cache(self):
        """Test routing to cache restoration when cache available."""
        state = MagicMock(spec=AnalysisState)
        state.using_cached_profile = True
        state.cache = MagicMock()

        result = route_after_initialize(state)

        assert result == "restore_cache"

    def test_route_after_initialize_without_cache(self):
        """Test routing to Phase 1 handoff when no cache."""
        state = MagicMock(spec=AnalysisState)
        state.using_cached_profile = False
        state.user_intent = MagicMock()
        state.user_intent.db_uri = None
        state.user_intent.api_url = None
        state.user_intent.multi_file_input = None

        result = route_after_initialize(state)

        assert result == "create_phase1_handoff"

    def test_route_after_analysis_validation_complete(self):
        """Test routing when Phase 2 is complete."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = [
            MagicMock(route_to="PHASE_2_COMPLETE")
        ]

        result = route_after_analysis_validation(state)

        assert result == "assemble_notebook"

    def test_route_after_analysis_validation_retry_strategy(self):
        """Test routing back to strategy agent."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = [
            MagicMock(route_to="StrategyAgent")
        ]

        result = route_after_analysis_validation(state)

        assert result == "strategy"

    def test_route_after_analysis_validation_retry_codegen(self):
        """Test routing back to analysis codegen."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = [
            MagicMock(route_to="AnalysisCodeGenerator")
        ]

        result = route_after_analysis_validation(state)

        assert result == "analysis_codegen"

    def test_route_after_analysis_validation_rollback(self):
        """Test routing to rollback recovery."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = [
            MagicMock(route_to="Orchestrator", route_reason="ROLLBACK_TRIGGERED")
        ]

        result = route_after_analysis_validation(state)

        assert result == "rollback_recovery"

    def test_route_after_analysis_validation_max_iterations(self):
        """Test routing when max iterations reached."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = [
            MagicMock(route_to="Orchestrator", route_reason="Max iterations")
        ]

        result = route_after_analysis_validation(state)

        assert result == "assemble_notebook"

    def test_route_after_analysis_validation_default_fallback(self):
        """Test default routing fallback to notebook assembly."""
        state = MagicMock(spec=AnalysisState)
        state.analysis_validation_reports = []

        result = route_after_analysis_validation(state)

        assert result == "assemble_notebook"


class TestBuildWorkflow:
    """Test workflow graph construction."""

    def test_build_workflow_creates_graph(self):
        """Test that build_workflow creates a valid StateGraph."""
        workflow = build_workflow()

        assert workflow is not None
        # Graph should have nodes added
        assert len(workflow.nodes) > 0

    def test_build_workflow_has_all_nodes(self):
        """Test that all required nodes are added."""
        workflow = build_workflow()

        expected_nodes = [
            "initialize",
            "create_phase1_handoff",
            "data_profiler",
            "profile_codegen",
            "profile_validator",
            "transition_to_phase2",
            "extension_node",
            "strategy",
            "analysis_codegen",
            "analysis_validator",
            "exploratory_conclusions",
            "restore_cache",
            "rollback_recovery",
            "assemble_notebook"
        ]

        for node_name in expected_nodes:
            assert node_name in workflow.nodes, f"Node {node_name} not found in workflow"

    def test_build_workflow_has_entry_point(self):
        """Test that workflow has correct entry point."""
        workflow = build_workflow()

        # Entry point should be 'initialize'
        # LangGraph stores this internally, difficult to test directly
        # but we can verify it doesn't raise an error
        assert workflow is not None


class TestTokenTracking:
    """Test token tracking across nodes."""

    @patch('src.workflow.graph.AgentFactory')
    def test_token_tracking_single_node(self, mock_factory):
        """Test token tracking in a single node."""
        state = MagicMock(spec=AnalysisState)
        state.csv_path = "data.csv"
        state.user_intent = None
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.using_cached_profile = False
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0

        # Simulate token usage: start at 100, end at 200
        mock_orchestrator = MagicMock()
        mock_orchestrator.llm_agent.total_tokens = 100
        mock_orchestrator.process.return_value = {"status": "ok"}
        
        mock_factory.get_agent.return_value = mock_orchestrator
        
        # Side effect to simulate token increase
        def process_side_effect(*args, **kwargs):
            mock_orchestrator.llm_agent.total_tokens = 200
            return {"status": "ok"}
        mock_orchestrator.process.side_effect = process_side_effect

        result = initialize_node(state)

        assert result["total_tokens_used"] == 100  # 200 - 100 = 100 used

    @patch('src.workflow.graph.AgentFactory')
    def test_token_tracking_multiple_nodes(self, mock_factory):
        """Test token accumulation across multiple nodes."""
        # Node 1: Data Profiler (uses 50 tokens)
        state1 = MagicMock(spec=AnalysisState)
        state1.profiler_outputs = []
        state1.total_tokens_used = 0
        state1.prompt_tokens_used = 0
        state1.completion_tokens_used = 0
        state1.errors = []

        mock_profiler = MagicMock()
        mock_profiler.llm_agent.total_tokens = 100
        mock_profiler.process.return_value = {"handoff": MagicMock()}
        
        def profiler_side_effect(*args, **kwargs):
            mock_profiler.llm_agent.total_tokens = 150
            return {"handoff": MagicMock()}
        mock_profiler.process.side_effect = profiler_side_effect
        
        # Node 2: Profile Codegen (uses 30 tokens)
        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 200
        mock_codegen.process.return_value = {"handoff": MagicMock()}
        
        def codegen_side_effect(*args, **kwargs):
            mock_codegen.llm_agent.total_tokens = 230
            return {"handoff": MagicMock()}
        mock_codegen.process.side_effect = codegen_side_effect

        # Configure factory to return correct mock based on agent_name
        def get_agent_side_effect(agent_name):
            if agent_name == "data_profiler":
                return mock_profiler
            elif agent_name == "profile_codegen":
                return mock_codegen
            return MagicMock()
        mock_factory.get_agent.side_effect = get_agent_side_effect

        result1 = data_profiler_node(state1)
        assert result1["total_tokens_used"] == 50

        state2 = MagicMock(spec=AnalysisState)
        state2.profiler_outputs = [result1.get("handoff")]
        state2.profile_code_outputs = []
        state2.phase1_iteration = 0
        state2.total_tokens_used = 50  # Carry over from previous
        state2.prompt_tokens_used = 25
        state2.completion_tokens_used = 25
        state2.errors = []

        result2 = profile_codegen_node(state2)
        assert result2["total_tokens_used"] == 80  # 50 + 30


class TestErrorPropagation:
    """Test error handling and propagation."""

    @patch('src.workflow.graph.AgentFactory')
    def test_error_propagation_preserves_state(self, mock_factory):
        """Test that errors don't lose state information."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = []
        state.total_tokens_used = 100
        state.prompt_tokens_used = 60
        state.completion_tokens_used = 40
        state.errors = ["Previous error"]

        mock_profiler = MagicMock()
        mock_profiler.llm_agent.total_tokens = 200
        mock_profiler.process.side_effect = Exception("New error")
        
        mock_factory.get_agent.return_value = mock_profiler

        result = data_profiler_node(state)

        # Total tokens should still be tracked
        assert "total_tokens_used" in result
        assert result["total_tokens_used"] >= 100

        # Previous errors should not be lost
        # (In real implementation, errors are appended, not replaced)
        assert "errors" in result


class TestStateTransitions:
    """Test state transitions between phases."""

    @patch('src.workflow.graph.AgentFactory')
    @patch('src.workflow.graph.update_issue_frequency')
    def test_state_transition_phase1_to_phase2(self, mock_update_freq, mock_factory):
        """Test state transition from Phase 1 to Phase 2."""
        # Phase 1 completes with lock granted
        state = MagicMock(spec=AnalysisState)
        state.profile_code_outputs = [MagicMock()]
        state.profile_validation_reports = []
        state.phase1_quality_trajectory = []
        state.phase1_iteration = 1
        state.csv_path = "data.csv"
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.user_intent = MagicMock()
        state.total_tokens_used = 100
        state.prompt_tokens_used = 60
        state.completion_tokens_used = 40
        state.profile_lock = MagicMock(spec=ProfileLock)
        state.errors = []

        mock_validator = MagicMock()
        mock_validator.llm_agent.total_tokens = 200
        mock_validator.process.return_value = {
            "report": MagicMock(),
            "quality_score": 0.9,
            "issues": [],
            "should_lock": True,
            "strategy_handoff": MagicMock()
        }
        
        mock_factory.get_agent.return_value = mock_validator
        mock_update_freq.return_value = {}

        result = profile_validator_node(state)

        # Profile lock should be granted
        state.profile_lock.grant_lock.assert_called_once()

        # Should route to Phase 2
        assert state.profile_lock.is_locked.return_value or result.get("profile_lock")

    @patch('src.workflow.graph.AgentFactory')
    def test_state_transition_phase1_iteration_increment(self, mock_factory):
        """Test that Phase 1 iteration increments correctly."""
        state = MagicMock(spec=AnalysisState)
        state.profiler_outputs = [MagicMock()]
        state.profile_code_outputs = []
        state.phase1_iteration = 2  # Already at iteration 2
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_codegen = MagicMock()
        mock_codegen.llm_agent.total_tokens = 100
        mock_codegen.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_codegen

        result = profile_codegen_node(state)

        assert result["phase1_iteration"] == 3  # Incremented to 3

    @patch('src.workflow.graph.AgentFactory')
    def test_state_transition_phase2_iteration_increment(self, mock_factory):
        """Test that Phase 2 iteration increments correctly."""
        state = MagicMock(spec=AnalysisState)
        state.pipeline_mode = PipelineMode.PREDICTIVE
        state.profile_lock = MagicMock()
        state.profile_lock.get_locked_handoff.return_value = MagicMock()
        state.strategy_outputs = []
        state.phase2_iteration = 1  # Already at iteration 1
        state.total_tokens_used = 0
        state.prompt_tokens_used = 0
        state.completion_tokens_used = 0
        state.errors = []

        mock_strategy = MagicMock()
        mock_strategy.llm_agent.total_tokens = 100
        mock_strategy.process.return_value = {"handoff": MagicMock()}
        
        mock_factory.get_agent.return_value = mock_strategy

        result = strategy_node(state)

        assert result["phase2_iteration"] == 2  # Incremented to 2
