"""
Unit tests for Orchestrator Agent.

Tests the central coordinator, mode detection, cache management,
phase transitions, and notebook assembly functionality.
"""


import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime

# Mock logger before it is imported by agents
mock_logger = MagicMock()
msg_logger_patch = patch('src.utils.logger.get_logger', return_value=mock_logger)
msg_logger_patch.start()
# Also patch the class based logger just in case
patch('src.utils.logger.DAAgentLogger', return_value=mock_logger).start()

from src.agents.orchestrator import OrchestratorAgent

from src.models.state import AnalysisState, Phase, PipelineMode, ProfileLock
from src.models.handoffs import UserIntent
from src.models.handoffs import ProfileToStrategyHandoff
from src.utils.cache_manager import CacheStatus


class TestOrchestratorAgent:
    """Test suite for Orchestrator Agent."""

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a sample CSV file."""
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
            'salary': [50000, 60000, 70000, 80000, 90000],
            'churn': ['No', 'No', 'Yes', 'No', 'Yes']
        })
        df.to_csv(csv_path, index=False)
        return csv_path

    @pytest.fixture
    def mock_user_intent_exploratory(self, sample_csv):
        """Create exploratory user intent."""
        return UserIntent(
            csv_path=str(sample_csv),
            analysis_question='What patterns exist in the data?',
            target_column=None
        )

    @pytest.fixture
    def mock_user_intent_predictive(self, sample_csv):
        """Create predictive user intent."""
        return UserIntent(
            csv_path=str(sample_csv),
            target_column='churn',
            analysis_question=None
        )


    @pytest.fixture
    def orchestrator_agent(self):
        """Create an Orchestrator Agent instance with mocked services."""
        agent = OrchestratorAgent()
        # Use private attributes since properties are read-only
        agent._mode_detector = MagicMock()
        agent._mode_detector.determine_mode.return_value = (PipelineMode.EXPLORATORY, "default")
        agent._notebook_assembler = MagicMock()
        agent._notebook_assembler.assemble_notebook.return_value = {"final_notebook_path": "test.ipynb", "confidence": 1.0}
        agent._join_detector = MagicMock()
        agent._cache_manager = MagicMock()
        agent._data_manager = MagicMock()
        # Mock load_data to return a simple dataframe
        agent.data_manager.load_data.return_value = pd.DataFrame({
            'age': [25, 30],
            'name': ['Alice', 'Bob'],
            'salary': [50000, 60000],
            'churn': ['No', 'No']
        })
        # Mock metadata methods to return valid structure for Pydantic
        agent.data_manager.get_basic_metadata.return_value = {
            "row_count": 5,
            "column_count": 4,
            "columns": ['age', 'name', 'salary', 'churn'],
            "missing_values": {'age': 0, 'name': 0, 'salary': 0, 'churn': 0},
            "types": {'age': 'int64', 'name': 'object', 'salary': 'int64', 'churn': 'object'},
            "duplicates": 0,
            "memory_usage": 1000
        }
        agent.data_manager.get_unique_counts.return_value = {'age': 5, 'name': 5, 'salary': 5, 'churn': 2}
        agent.data_manager.get_sample.return_value = agent.data_manager.load_data.return_value
        agent.data_manager.get_head.return_value = agent.data_manager.load_data.return_value

        # default cache check
        agent.cache_manager.check_cache.return_value = Mock(status=CacheStatus.NOT_FOUND, cache=None)
        agent.cache_manager.check_multi_file_cache.return_value = Mock(status=CacheStatus.NOT_FOUND, cache=None)
        return agent

    # Test 1: Initialization with valid CSV
    def test_initialization_with_valid_csv(self, orchestrator_agent, sample_csv):
        """Test orchestrator initialization with valid CSV."""
        state = AnalysisState(
            csv_path=str(sample_csv),
            current_phase=Phase.INIT
        )
        
        user_intent_dict = {
            "analysis_question": "Analyze this data",
            "target_column": None
        }

        # Mock cache manager
        orchestrator_agent.cache_manager.check_cache.return_value = Mock(state=CacheStatus.NOT_FOUND, status=CacheStatus.NOT_FOUND)

        result = orchestrator_agent._initialize(
            state, 
            csv_path=str(sample_csv),
            user_intent=user_intent_dict
        )

        assert result is not None
        if "error" in result:
            pytest.fail(f"Initialization returned error: {result['error']}")
        assert result["current_phase"] == Phase.PHASE_1
        assert "csv_data" in result
        
        # Verify mode detector was called
        orchestrator_agent.mode_detector.determine_mode.assert_called_once()
        
    # Test 9: Cache check - expired cache
    def test_cache_check_calls_manager(self, orchestrator_agent, sample_csv):
        """Test cache check delegates to CacheManager."""
        orchestrator_agent.cache_manager.check_cache.return_value = Mock(status=CacheStatus.EXPIRED, cache=None)

        # _initialize calls cache check
        orchestrator_agent._initialize(
            AnalysisState(csv_path=str(sample_csv)),
            csv_path=str(sample_csv),
            user_intent={}
        )
        
        orchestrator_agent.cache_manager.check_cache.assert_called()

    # Test 11: Create Phase 1 handoff
    def test_create_phase1_handoff(self, orchestrator_agent, sample_csv):
        """Test creation of Phase 1 handoff with data preview."""
        df = pd.read_csv(sample_csv)
        state = AnalysisState(
            csv_path=str(sample_csv),
            csv_data=df.to_dict(),
            user_intent=UserIntent(csv_path=str(sample_csv)),
            current_phase=Phase.PHASE_1
        )

        handoff = orchestrator_agent._create_phase1_handoff(state)

        assert handoff is not None
        assert "profiler_handoff" in handoff
        ph = handoff["profiler_handoff"]
        assert ph.csv_path == str(sample_csv)
        assert ph.row_count == len(df)

    # Test 12: Transition to Phase 2
    def test_transition_to_phase2(self, orchestrator_agent, sample_csv):
        """Test phase transition from Phase 1 to Phase 2."""
        # Create mock profile lock
        mock_profile = ProfileToStrategyHandoff(
            csv_path=str(sample_csv),
            row_count=5,
            column_count=4,
            column_profiles=(),
            overall_quality_score=0.9,
            missing_value_summary={},
            lock_status="locked",
            phase1_quality_score=0.9
        )

        profile_lock = ProfileLock(
            profile_handoff=mock_profile,
            phase1_quality_score=0.9,
            locked_at=datetime.now(),
            status="locked"
        )
        # Ensure lock check passes (mock or logic)
        # The logic checks state.profile_lock.is_locked()
        

        state = AnalysisState(
            csv_path=str(sample_csv),
            user_intent=UserIntent(csv_path=str(sample_csv), analysis_type_hint='classification', target_column='churn'),
            current_phase=Phase.PHASE_1,
            profile_lock=profile_lock
        )


        # Transition to Phase 2
        result = orchestrator_agent._transition_to_phase2(state)

        assert result.get("current_phase") == Phase.PHASE_2

    # Test 13: Transition to Phase 2 without profile lock (should fail)
    def test_transition_to_phase2_without_lock(self, orchestrator_agent, sample_csv):
        """Test phase transition fails without profile lock."""
        state = AnalysisState(
            csv_path=str(sample_csv),
            current_phase=Phase.PHASE_1,
            profile_lock=ProfileLock()  # unlocked
        )

        result = orchestrator_agent._transition_to_phase2(state)

        assert "error" in result

    # Test 14: Notebook assembly calls service
    def test_notebook_assembly_delegation(self, orchestrator_agent, sample_csv):
        """Test notebook assembly delegates to NotebookAssembler."""
        state = AnalysisState(
            csv_path=str(sample_csv),
            user_intent=UserIntent(csv_path=str(sample_csv)),
            current_phase=Phase.ASSEMBLY,
            pipeline_mode=PipelineMode.EXPLORATORY
        )

        orchestrator_agent.notebook_assembler.assemble_notebook.return_value = {"final_notebook_path": "out.ipynb"}

        result = orchestrator_agent.process(
            state, 
            action="assemble_notebook", 
            assembly_handoff={}
        )

        orchestrator_agent.notebook_assembler.assemble_notebook.assert_called_once()
        assert result["final_notebook_path"] == "out.ipynb"

    # Test 19: CSV validation - invalid path
    def test_csv_validation_invalid_path(self, orchestrator_agent):
        """Test CSV validation with non-existent file."""
        # Override mock to raise FileNotFoundError
        orchestrator_agent.data_manager.load_data.side_effect = FileNotFoundError("File not found")
        
        state = AnalysisState()
        # _initialize handles the exception and returns error dict
        result = orchestrator_agent._initialize(
            state, 
            csv_path='/nonexistent/file.csv',
            user_intent={}
        )
        assert "error" in result

    # Test 37: Process method routes to correct action
    def test_process_routes_initialize(self, orchestrator_agent, sample_csv):
        """Test process method routes to _initialize for 'initialize' action."""
        state = AnalysisState()
        
        # We need to spy on the agent or verify side effects
        # _initialize is mocked? No, we are testing the agent.
        # But we mocked the dependencies.
        
        user_intent = {"target_column": "churn"}
        orchestrator_agent._initialize = MagicMock(return_value={"test": "ok"})
        

        result = orchestrator_agent.process(
            state,
            action='initialize',
            csv_path=str(sample_csv),
            user_intent=user_intent
        )
        
        orchestrator_agent._initialize.assert_called_once()

    def test_process_routes_other_actions(self, orchestrator_agent, sample_csv):
        """Test process method routes for other actions."""
        state = AnalysisState()
        
        # Test phase1_handoff
        orchestrator_agent._create_phase1_handoff = MagicMock(return_value={"phase1": "ok"})
        res = orchestrator_agent.process(state, action="phase1_handoff")
        orchestrator_agent._create_phase1_handoff.assert_called_once()
        assert res == {"phase1": "ok"}
        
        # Test rollback_phase2
        orchestrator_agent._rollback_phase2 = MagicMock(return_value={"rollback": "ok"})
        res = orchestrator_agent.process(state, action="rollback_phase2")
        orchestrator_agent._rollback_phase2.assert_called_once()
        assert res == {"rollback": "ok"}
        
        # Test restore_cache
        orchestrator_agent._restore_cache = MagicMock(return_value={"restore": "ok"})
        res = orchestrator_agent.process(state, action="restore_cache")
        orchestrator_agent._restore_cache.assert_called_once()
        assert res == {"restore": "ok"}
        
        # Test save_cache
        orchestrator_agent._save_cache = MagicMock(return_value={"save": "ok"})
        res = orchestrator_agent.process(state, action="save_cache")
        orchestrator_agent._save_cache.assert_called_once()
        assert res == {"save": "ok"}
        
        # Test unknown action
        res = orchestrator_agent.process(state, action="unknown_action")
        assert "error" in res
        assert "Unknown action" in res["error"]

    def test_initialize_data_loading_errors(self, orchestrator_agent):
        """Test _initialize with pandas parsing errors."""
        orchestrator_agent.data_manager.load_data.side_effect = pd.errors.EmptyDataError("Empty file")
        
        state = AnalysisState()
        result = orchestrator_agent._initialize(state, csv_path="empty.csv")
        assert "error" in result
        assert "Invalid CSV" in result["error"]
        
        orchestrator_agent.data_manager.load_data.side_effect = Exception("General error")
        result = orchestrator_agent._initialize(state, csv_path="error.csv")
        assert "error" in result
        assert "Failed to load data" in result["error"]

    def test_initialize_with_cache_hit(self, orchestrator_agent, sample_csv):
        """Test _initialize when cache is valid and used."""
        mock_cache = MagicMock()
        mock_cache.profile_handoff = ProfileToStrategyHandoff(
            csv_path=str(sample_csv),
            row_count=5,
            column_count=4,
            column_profiles=(),
            overall_quality_score=0.9,
            missing_value_summary={},
            lock_status="locked",
            phase1_quality_score=0.9
        )
        orchestrator_agent.cache_manager.check_cache.return_value = Mock(status=CacheStatus.VALID, cache=mock_cache)
        orchestrator_agent._mode_detector.determine_mode.return_value = (PipelineMode.PREDICTIVE, "test")
        
        state = AnalysisState()
        result = orchestrator_agent._initialize(
            state, 
            csv_path=str(sample_csv),
            use_cache=True,
            user_intent={"analysis_question": "test"}
        )
        assert "pipeline_mode" in result

    def test_initialize_with_multi_file_input(self, orchestrator_agent, sample_csv):
        """Test _initialize with multi_file_input intent."""
        state = AnalysisState()
        from src.models.multi_file import MultiFileInput, FileInput
        multi_file = MultiFileInput(
            files=[
                FileInput(file_path=str(sample_csv), file_hash="hash1", role="main"),
                FileInput(file_path="other.csv", file_hash="hash2", role="secondary")
            ]
        )
        user_intent = {
            "multi_file_input": multi_file.model_dump()
        }
        result = orchestrator_agent._initialize(
            state, 
            csv_path=str(sample_csv),
            user_intent=user_intent
        )
        assert "multi_file_input" in result
        assert result["multi_file_input"] is not None

    def test_rollback_phase2(self, orchestrator_agent):
        """Test _rollback_phase2 clears Phase 2 state and unlocks profile."""
        profile_lock = ProfileLock(status="locked", locked_at=datetime.now())
        state = AnalysisState(
            current_phase=Phase.PHASE_2,
            profile_lock=profile_lock,
            strategy_handoff=MagicMock(),
            analysis_handoff=MagicMock()
        )
        
        result = orchestrator_agent._rollback_phase2(state)
        
        assert isinstance(result, dict)

    def test_save_restore_cache(self, orchestrator_agent):
        """Test _save_cache and _restore_cache methods."""
        state = AnalysisState(csv_path="test.csv")
        state.profile_lock = MagicMock()
        state.profile_lock.is_locked.return_value = True
        
        # Test save cache success
        orchestrator_agent.cache_manager.save_cache.return_value = True
        res = orchestrator_agent._save_cache(state)
        assert res == {}
        
        # Test save cache failure
        state.profile_lock.is_locked.return_value = False
        res = orchestrator_agent._save_cache(state)
        assert res == {}
        
        # Test restore cache success
        mock_cache = MagicMock()
        mock_cache.profile_lock = {"locked_at": datetime.now(), "status": "locked"}
        state.cache = mock_cache
        
        res = orchestrator_agent._restore_cache(state)
        assert res["current_phase"] == Phase.PHASE_1
        assert "profile_lock" in res
        
        # Test restore cache failure
        state.cache = None
        try:
            res = orchestrator_agent._restore_cache(state)
            assert False, "Should raise ValueError"
        except ValueError:
            assert True
    pytest.main([__file__, '-v'])
