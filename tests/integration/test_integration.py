"""
Integration test for the full Multi-Agent Data Analysis System.
Runs the workflow on iris.csv and verifies the output notebook.
"""

import os
import sys
import pytest
import pandas as pd
import nbformat

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env from file if needed, but config does it automatically
# from dotenv import load_dotenv
# load_dotenv()

# Set dummy key for CrewAI (it enforces this even if using Ollama sometimes)
# Removed as we fixed provider.py
# os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-test"

from src.main import run_analysis
from src.models.state import Phase

CSV_PATH = "tests/fixtures/iris.csv"

def test_full_workflow_execution():
    """Run the full workflow and verify output."""
    print(f"\n[Test] Running analysis on {CSV_PATH}...")
    
    # Ensure fixture exists
    if not os.path.exists(CSV_PATH):
        # Create dummy iris if missing
        print("[Test] Creating dummy iris.csv fixture...")
        df = pd.DataFrame({
            'sepal_length': [5.1, 4.9, 4.7, 4.6, 5.0],
            'sepal_width': [3.5, 3.0, 3.2, 3.1, 3.6],
            'petal_length': [1.4, 1.4, 1.3, 1.5, 1.4],
            'petal_width': [0.2, 0.2, 0.2, 0.2, 0.2],
            'species': ['setosa', 'setosa', 'setosa', 'setosa', 'setosa']
        })
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        df.to_csv(CSV_PATH, index=False)
    
    # Run analysis
    # We use a mocked or real run? Real run with Ollama is slow/flaky for unit tests.
    # For this environment, we assume the user might want a real run or we mock.
    # Given the user wants "progress", let's try a run but check if we can verify without full LLM wait
    # if it's too slow.
    # Actually, let's just trigger the main entry point and capture the result.
    
    # Run analysis
    try:
        final_state = run_analysis(
            csv_path=CSV_PATH,
            analysis_question="Analyze the iris dataset and classify species",
            verbose=True
        )
    except Exception as e:
        pytest.fail(f"Workflow execution failed: {e}")
    
    # Verification
    # Ensure final_state is an object
    assert final_state.current_phase == Phase.COMPLETE
    assert final_state.final_notebook_path is not None
    assert os.path.exists(final_state.final_notebook_path)
    
    print(f"\n[Test] Notebook generated at: {final_state.final_notebook_path}")
    
    # Verify Notebook Content
    with open(final_state.final_notebook_path) as f:
        nb = nbformat.read(f, as_version=4)
        
    assert len(nb.cells) > 0
    
    # Check for sections
    sources = [c.source for c in nb.cells]
    has_profiling = any("Data Profiling" in s for s in sources)
    has_analysis = any("Analysis Phase" in s for s in sources)
    has_conclusion = any("Final Summary" in s for s in sources)
    
    assert has_profiling, "Notebook missing Profiling section"
    assert has_analysis, "Notebook missing Analysis section"
    assert has_conclusion, "Notebook missing Conclusion section"
    
    print("[Test] Notebook structure verified.")

if __name__ == "__main__":
    test_full_workflow_execution()
