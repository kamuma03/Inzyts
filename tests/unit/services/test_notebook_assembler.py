import pytest
from unittest.mock import patch
from pathlib import Path
import nbformat
import shutil

from src.services.notebook_assembler import NotebookAssembler
from src.models.state import AnalysisState, Phase
from src.models.handoffs import FinalAssemblyHandoff, NotebookCell, PipelineMode

@pytest.fixture
def mock_state(tmp_path):
    """Fixture providing a mock AnalysisState with a temp CSV."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text("a,b\n1,2")
    return AnalysisState(
        csv_path=str(csv_file),
        pipeline_mode=PipelineMode.DIAGNOSTIC,
        messages=[]
    )

@pytest.fixture
def mock_handoff():
    """Fixture providing a mock FinalAssemblyHandoff object."""
    return FinalAssemblyHandoff(
        notebook_title="Test Notebook",
        introduction_content="This is a test introduction",
        profile_cells=[NotebookCell(cell_type="markdown", source="Profile md")],
        exploratory_cells=[NotebookCell(cell_type="code", source="print('explore')")],
        analysis_cells=[NotebookCell(cell_type="code", source="print('analysis')")],
        conclusion_content="Test conclusion.",
        total_execution_time=10.5,
        total_iterations=2,
        phase1_quality_score=9.0,
        phase2_quality_score=9.5,
        total_tokens_used=1500
    )


def test_assemble_notebook_success(mock_state, mock_handoff, tmp_path):
    """Test standard notebook assembly with all sections."""
    with patch("src.services.notebook_assembler.settings.output_dir", str(tmp_path)):
        result = NotebookAssembler.assemble_notebook(mock_state, mock_handoff)
        
        assert result["confidence"] == 1.0
        assert result["current_phase"] == Phase.COMPLETE
        assert result["final_quality_score"] == 9.25 # (9.0+9.5)/2
        
        # Verify notebook format and content
        nb_path = Path(result["final_notebook_path"])
        assert nb_path.exists()
        
        with open(nb_path, "r") as f:
            nb = nbformat.read(f, as_version=4)
        
        # Check cells are correctly populated
        cell_sources = [c.source for c in nb.cells]
        full_text = "\\n".join(cell_sources)
        assert "This is a test introduction" in full_text
        assert "print('explore')" in full_text
        assert "print('analysis')" in full_text
        assert "Test conclusion." in full_text
        assert "2. Data Profiling" in full_text
        
        # Check that CSV was copied to output dir
        copied_csv = tmp_path / "test_data.csv"
        assert copied_csv.exists()


def test_assemble_notebook_exploratory_only(mock_state, mock_handoff, tmp_path):
    """Test notebook assembly when in exploratory mode (no phase 2 analysis)."""
    mock_handoff.analysis_cells = []
    mock_handoff.exploratory_cells = [] # Let's also test empty exploratory cells fallback
    mock_state.pipeline_mode = PipelineMode.EXPLORATORY
    
    with patch("src.services.notebook_assembler.settings.output_dir", str(tmp_path)):
        result = NotebookAssembler.assemble_notebook(mock_state, mock_handoff)
        
        nb_path = Path(result["final_notebook_path"])
        assert nb_path.exists()
        
        with open(nb_path, "r") as f:
            nb = nbformat.read(f, as_version=4)
            
        cell_sources = [c.source for c in nb.cells]
        full_text = "\\n".join(cell_sources)
        
        # Summary should be section 4 instead of 5
        assert "4. Summary & Recommendations" in full_text
        
        # Should have placeholder for missing exploratory insights
        assert "No additional exploratory conclusions" in full_text


def test_assemble_notebook_none_handoff(mock_state):
    """Test passing None as handoff."""
    result = NotebookAssembler.assemble_notebook(mock_state, None)
    assert result["error"] == "No assembly handoff provided"
    assert result["confidence"] == 0.0

def test_assemble_notebook_copy_fail(mock_state, mock_handoff, tmp_path):
    """Test what happens if the CSV copy operation raises an error."""
    with patch("src.services.notebook_assembler.settings.output_dir", str(tmp_path)):
        with patch("src.services.notebook_assembler.shutil.copy2", side_effect=PermissionError("Denied")):
            # It should catch the exception and still return success for the notebook
            result = NotebookAssembler.assemble_notebook(mock_state, mock_handoff)
            
            assert result["confidence"] == 1.0
            nb_path = Path(result["final_notebook_path"])
            assert nb_path.exists()
