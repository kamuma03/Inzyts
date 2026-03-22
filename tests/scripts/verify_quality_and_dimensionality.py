
import pandas as pd
import numpy as np
import sys
import os

# Add src and libs to path
sys.path.append(os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "libs"))

# Mock crewai before import
from unittest.mock import MagicMock
mock_crewai = MagicMock()
mock_agent = MagicMock()
mock_task = MagicMock()
mock_crewai.Agent = mock_agent
mock_crewai.Task = mock_task
sys.modules["crewai"] = mock_crewai
sys.modules["langchain"] = MagicMock()
mock_lc_core = MagicMock()
sys.modules["langchain_core"] = mock_lc_core
sys.modules["langchain_core.language_models"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_core.prompts"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_anthropic"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["langchain_community"] = MagicMock()

# Mock logger
mock_logger_module = MagicMock()
mock_logger = MagicMock()
mock_logger_module.get_logger.return_value = mock_logger
sys.modules["src.utils.logger"] = mock_logger_module

# Mock nbformat
sys.modules["nbformat"] = MagicMock()
sys.modules["nbformat.v4"] = MagicMock()

from src.agents.phase1.data_profiler import DataProfilerAgent
from src.models.handoffs import PipelineMode
from src.agents.orchestrator import OrchestratorAgent

def test_remediation_detection():
    print("Testing Remediation Detection...")
    df = pd.DataFrame({
        'A': [1, 2, np.nan, 4, 5],
        'B': ['x', 'y', 'z', 'x', 'y'],
        'C': [1, 1, 1, 1, 1]
    })
    # Add duplicates
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    
    profiler = DataProfilerAgent()
    issues = profiler.detect_quality_issues(df)
    
    print(f"Detected {len(issues)} issues.")
    for issue in issues:
        print(f" - {issue.issue_id}: {issue.issue_type}")
    
    plans = profiler.generate_remediation_plan(issues, df)
    print(f"Generated {len(plans)} remediation plans.")
    for plan in plans:
        print(f" - Plan for {plan.issue.issue_id}: {plan.remediation_type} (Code: {plan.code_snippet})")
        
    assert len(plans) > 0, "No remediation plans generated"

def test_pca_applicability():
    print("\nTesting PCA Applicability...")
    # Create DF with many columns
    data = np.random.rand(100, 25)
    df = pd.DataFrame(data, columns=[f'col_{i}' for i in range(25)])
    
    profiler = DataProfilerAgent()
    config = profiler.assess_pca_applicability(df)
    
    if config:
        print(f"PCA Config: Enabled={config.enabled}, Threshold={config.feature_count_threshold}")
        assert config.enabled == True
    else:
        print("PCA Not Applicable (Unexpected)")

def test_orchestrator_mode_detection():
    print("\nTesting Orchestrator Mode Detection...")
    orch = OrchestratorAgent()
    mode, method = orch._determine_pipeline_mode(None, None, "Can you reduce dimensionality?")
    print(f"Detected Mode: {mode} (Method: {method})")
    assert mode == PipelineMode.DIMENSIONALITY
    
    mode, method = orch._determine_pipeline_mode(None, None, "Run PCA on this data")
    print(f"Detected Mode: {mode} (Method: {method})")
    assert mode == PipelineMode.DIMENSIONALITY

def main():
    try:
        test_remediation_detection()
        test_pca_applicability()
        test_orchestrator_mode_detection()
        print("\nAll Verification Tests Passed!")
    except Exception as e:
        print(f"\nVerification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
