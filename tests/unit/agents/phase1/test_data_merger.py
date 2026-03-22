import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.agents.phase1.data_merger import DataMergerAgent
from src.models.state import AnalysisState, UserIntent
from src.models.multi_file import MultiFileInput, MergedDataset, JoinCandidate, FileInput, JoinType

@pytest.fixture
def merger_agent():
    return DataMergerAgent()

@pytest.fixture
def base_state():
    state = AnalysisState(
        job_id="job_123",
        messages=[]
    )
    return state

def test_process_no_user_intent(merger_agent, base_state):
    # Tests lines ~61-67
    base_state.user_intent = None
    result = merger_agent.process(base_state)
    assert result == {}

def test_process_single_file(merger_agent, base_state):
    # Tests lines ~65-67
    base_state.user_intent = UserIntent(
        csv_path="",
        analysis_question="test",
        multi_file_input=MultiFileInput(
            files=[FileInput(file_path="f1.csv", file_hash="h1", alias="f1")]
        )
    )
    result = merger_agent.process(base_state)
    assert result == {}

def test_process_load_data_failure(merger_agent, base_state):
    # Tests lines 74-90
    base_state.user_intent = UserIntent(
        csv_path="",
        analysis_question="test",
        multi_file_input=MultiFileInput(
            files=[
                FileInput(file_path="f1.csv", file_hash="h1", alias="f1"),
                FileInput(file_path="f2.csv", file_hash="h2", alias="f2")
            ]
        )
    )
    
    mock_data_manager = MagicMock()
    mock_data_manager.load_data.side_effect = Exception("Load failure")
    merger_agent._data_manager = mock_data_manager
    
    result = merger_agent.process(base_state)
    assert "error" in result
    assert "Failed to load file f1.csv" in result["error"]

@patch("src.agents.phase1.data_merger.Path")
@patch("src.agents.phase1.data_merger.datetime")
def test_process_success(mock_datetime, mock_path, merger_agent, base_state, tmp_path):
    # Tests lines 95-143
    mock_datetime.now.return_value.strftime.return_value = "20230101_120000"
    
    # Mocking Path to intercept output dir creation but still return a valid Path object
    mock_output_dir = MagicMock()
    mock_merged_path = tmp_path / "merged_20230101_120000.csv"
    mock_output_dir.__truediv__.return_value = mock_merged_path
    mock_path.return_value.__truediv__.return_value = mock_output_dir
    
    f1 = FileInput(file_path="f1.csv", file_hash="h1", alias="f1")
    f2 = FileInput(file_path="f2.csv", file_hash="h2", alias="f2")
    
    base_state.user_intent = UserIntent(
        csv_path="",
        analysis_question="test merge",
        data_dictionary={"id": "primary key"},
        multi_file_input=MultiFileInput(files=[f1, f2])
    )
    
    mock_data_manager = MagicMock()
    mock_data_manager.load_data.side_effect = lambda path: pd.DataFrame() if path == "f1.csv" else pd.DataFrame()
    merger_agent._data_manager = mock_data_manager
    
    mock_join_detector = MagicMock()
    mock_candidate = JoinCandidate(
        left_file="f1", right_file="f2",
        left_column="id", right_column="id",
        name_similarity=1.0, type_compatibility=1.0, value_overlap=1.0,
        cardinality_ratio="1:1", confidence_score=1.0,
        recommended_join_type=JoinType.INNER
    )
    mock_join_detector.detect_join_candidates.return_value = [mock_candidate]
    
    mock_merged_ds = MergedDataset(
        merged_df_path="merged.csv", merged_hash="hash",
        source_files=["f1", "f2"], join_plan_executed=[mock_candidate],
        final_row_count=100, final_column_count=5, rows_dropped=0, rows_added=0,
        warnings=[]
    )
    mock_join_detector.execute_joins.return_value = mock_merged_ds
    
    merger_agent._join_detector = mock_join_detector
    
    result = merger_agent.process(base_state)
    
    assert "merged_dataset" in result
    assert result["merged_dataset"] == mock_merged_ds
    assert "join_report" in result
    assert result["join_report"].files_analyzed == 2
    assert result["join_report"].candidate_joins_found == 1
    assert "csv_path" in result
    assert result["csv_path"] == str(mock_merged_path)
    
    mock_join_detector.detect_join_candidates.assert_called_once()
    mock_join_detector.execute_joins.assert_called_once()

def test_process_generic_exception(merger_agent, base_state):
    # Tests lines 144-147
    base_state.user_intent = UserIntent(
        csv_path="",
        analysis_question="test",
        multi_file_input=MultiFileInput(
            files=[
                FileInput(file_path="f1.csv", file_hash="h1", alias="f1"),
                FileInput(file_path="f2.csv", file_hash="h2", alias="f2")
            ]
        )
    )
    
    mock_data_manager = MagicMock()
    mock_data_manager.load_data.return_value = pd.DataFrame()
    merger_agent._data_manager = mock_data_manager
    
    mock_join_detector = MagicMock()
    mock_join_detector.detect_join_candidates.side_effect = Exception("Critical detector failure")
    merger_agent._join_detector = mock_join_detector
    
    result = merger_agent.process(base_state)
    assert "error" in result
    assert "Data merging failed: Critical detector failure" in result["error"]
