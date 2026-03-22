"""
Unit tests for Exploratory Conclusions Agent.

Tests the LLM-powered insight synthesis, question answering,
findings generation, and confidence scoring functionality.
"""

import pytest
from unittest.mock import patch
import pandas as pd

from src.agents.phase1.exploratory_conclusions import ExploratoryConclusionsAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent
from src.models.handoffs import (
    ProfileToStrategyHandoff,
    ColumnProfile,
    DataType
)


@pytest.fixture(autouse=True)
def disable_cache():
    """Disable caching for all tests by patching CacheManager load and save."""
    with patch('src.utils.cache_manager.CacheManager.load_artifact', return_value=None), \
         patch('src.utils.cache_manager.CacheManager.save_artifact', return_value=None):
        yield


class TestExploratoryConclusionsAgent:
    """Test suite for Exploratory Conclusions Agent."""

    @pytest.fixture
    def mock_state_with_profile(self, tmp_path):
        """Create a mock analysis state with locked profile."""
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame({
            'age': [25, 30, 35, 40, 45, 50, 55, 60],
            'salary': [50000, 60000, 70000, 80000, 90000, 100000, 110000, 120000],
            'department': ['HR', 'IT', 'IT', 'Sales', 'HR', 'IT', 'Sales', 'HR']
        })
        df.to_csv(csv_path, index=False)

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(
                csv_path=str(csv_path),
                analysis_question='What is the relationship between age and salary?',
                target_column=None
            ),
            current_phase=Phase.EXPLORATORY_CONCLUSIONS
        )

        # Mock locked profile with ProfileToStrategyHandoff
        profile_handoff = ProfileToStrategyHandoff(
            phase1_quality_score=0.92,
            row_count=8,
            column_count=3,
            column_profiles=(
                ColumnProfile(
                    name='age',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.95,
                    unique_count=8,
                    null_percentage=0.0,
                    sample_values=['25', '30', '35', '40', '45']
                ),
                ColumnProfile(
                    name='salary',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.95,
                    unique_count=8,
                    null_percentage=0.0,
                    sample_values=['50000', '60000', '70000']
                ),
                ColumnProfile(
                    name='department',
                    detected_type=DataType.CATEGORICAL,
                    detection_confidence=0.90,
                    unique_count=3,
                    null_percentage=0.0,
                    sample_values=['HR', 'IT', 'Sales']
                )
            ),
            overall_quality_score=0.92,
            missing_value_summary={'total': 0.0},
            correlation_matrix={'age': {'salary': 0.95}},
            detected_patterns=('strong_positive_correlation',)
        )

        state.profile_lock.grant_lock(
            cells=[],
            handoff=profile_handoff,
            quality_score=0.92,
            report=None,
            iteration=1
        )

        return state

    @pytest.fixture
    def conclusions_agent(self):
        """Create an Exploratory Conclusions agent instance."""
        return ExploratoryConclusionsAgent()

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        return {
            "original_question": "What is the relationship between age and salary?",
            "direct_answer": "There is a strong positive correlation (0.95) between age and salary, indicating that salary increases consistently with age.",
            "key_findings": [
                "Strong positive correlation of 0.95 between age and salary",
                "Salary ranges from $50,000 to $120,000 across the dataset",
                "Age ranges from 25 to 60 years old"
            ],
            "statistical_insights": [
                "Mean age: 42.5 years",
                "Mean salary: $85,000",
                "All columns have 100% completeness (no missing values)"
            ],
            "data_quality_notes": [
                "High data quality score of 0.92",
                "No missing values detected",
                "All data types correctly identified"
            ],
            "recommendations": [
                "Consider adding more features to understand salary drivers beyond age",
                "Investigate if department affects salary for similar age groups"
            ],
            "limitations": [
                "Small sample size (8 records) limits generalizability",
                "Correlation does not imply causation"
            ],
            "confidence_score": 0.85,
            "conclusions_cells": [
                {
                    "cell_type": "markdown",
                    "source": "## Key Finding: Strong Age-Salary Correlation\n\nThe data shows a strong positive correlation..."
                }
            ],
            "visualization_cells": [
                {
                    "cell_type": "code",
                    "source": "import matplotlib.pyplot as plt\ndf.plot.scatter(x='age', y='salary')\nplt.title('Age vs Salary')\nplt.show()"
                }
            ]
        }

    def test_profile_lock_requirement(self, conclusions_agent, tmp_path):
        """Test that conclusions require locked profile."""
        # State without locked profile
        unlocked_state = AnalysisState(
            csv_path=str(tmp_path / "test.csv"),
            user_intent=UserIntent(csv_path=str(tmp_path / 'test.csv')),
            current_phase=Phase.EXPLORATORY_CONCLUSIONS
        )

        result = conclusions_agent.process(unlocked_state)

        assert 'error' in result
        assert 'not locked' in result['error'].lower()

    def test_minimum_findings_requirement(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that at least 3 key findings are required."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            assert 'exploratory_conclusions' in result
            output = result['exploratory_conclusions']
            assert len(output.key_findings) >= 3

    def test_minimum_recommendations_requirement(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that at least 2 recommendations are required."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            assert len(output.recommendations) >= 2

    def test_direct_answer_addresses_question(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that direct answer addresses the user's question."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            assert output.direct_answer is not None
            assert len(output.direct_answer) > 20  # Meaningful answer
            # Should mention key concepts from question
            assert 'correlation' in output.direct_answer.lower() or 'relationship' in output.direct_answer.lower()

    def test_confidence_threshold_warning(self, conclusions_agent, mock_state_with_profile):
        """Test warning when confidence < 0.70."""
        low_confidence_response = {
            "original_question": "Test",
            "direct_answer": "Unclear pattern",
            "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
            "statistical_insights": ["Insight"],
            "data_quality_notes": ["Note"],
            "recommendations": ["Rec 1", "Rec 2"],
            "limitations": ["Limited data"],
            "confidence_score": 0.55,
            "conclusions_cells": [],
            "visualization_cells": []
        }

        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = low_confidence_response

            result = conclusions_agent.process(mock_state_with_profile)

            assert result['confidence'] < 0.70
            # Should still return results but with warning

    def test_prompt_structure_includes_required_sections(self, conclusions_agent, mock_state_with_profile):
        """Test that prompt includes all required data sections."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = {
                "original_question": "Test",
                "direct_answer": "Answer",
                "key_findings": ["F1", "F2", "F3"],
                "statistical_insights": ["I1"],
                "data_quality_notes": ["Q1"],
                "recommendations": ["R1", "R2"],
                "limitations": ["L1"],
                "confidence_score": 0.80,
                "conclusions_cells": [],
                "visualization_cells": []
            }

            conclusions_agent.process(mock_state_with_profile)

            # Check that prompt was constructed with key sections
            call_args = mock_llm.call_args[0][0]
            assert 'user_question' in call_args or 'question' in call_args.lower()
            assert 'profile' in call_args.lower() or 'data' in call_args.lower()

    def test_findings_grounded_in_data(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that findings reference actual data values."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            # At least one finding should mention actual numbers
            has_data_reference = any(
                any(char.isdigit() for char in finding)
                for finding in output.key_findings
            )
            assert has_data_reference


    def test_retry_logic_on_llm_failure(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test retry logic when LLM fails."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            # First two calls fail, third succeeds
            mock_llm.side_effect = [
                Exception("LLM timeout"),
                Exception("LLM rate limit"),
                mock_llm_response
            ]

            result = conclusions_agent.process(mock_state_with_profile)

            # Should eventually succeed after retries
            assert 'exploratory_conclusions' in result
            assert mock_llm.call_count == 3

    def test_fallback_on_max_retries_exceeded(self, conclusions_agent, mock_state_with_profile):
        """Test fallback output when max retries exceeded."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            # All calls fail
            mock_llm.side_effect = Exception("Persistent LLM failure")

            result = conclusions_agent.process(mock_state_with_profile)

            # Should return fallback output with 0 confidence
            assert 'exploratory_conclusions' in result
            assert result['confidence'] == 0.0
            output = result['exploratory_conclusions']
            assert 'failed' in output.direct_answer.lower() or 'error' in output.direct_answer.lower()

    def test_visualization_cells_generation(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test optional visualization cells are included."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            # Should have visualization cells
            assert len(output.visualization_cells) > 0

    def test_markdown_cells_formatting(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that markdown cells are properly formatted."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            # Check for markdown cells
            markdown_cells = [cell for cell in output.conclusions_cells if cell.cell_type == 'markdown']
            assert len(markdown_cells) > 0
            # Should have markdown formatting
            assert any('#' in cell.source for cell in markdown_cells)

    def test_assembly_handoff_creation(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test creation of assembly handoff for notebook generation."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            assert 'assembly_handoff' in result
            handoff = result['assembly_handoff']
            assert handoff.conclusions_cells is not None
            assert handoff.direct_answer_summary is not None
            assert handoff.key_findings_count >= 3
            assert handoff.confidence_score >= 0.0

    def test_different_question_types(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test handling of different question types."""
        question_types = [
            "What is the distribution of age?",
            "Are there any correlations?",
            "What are the data quality issues?",
            "Summarize the dataset"
        ]

        for question in question_types:
            state = mock_state_with_profile
            state.user_intent.analysis_question = question

            with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
                mock_llm.return_value = mock_llm_response

                result = conclusions_agent.process(state)

                assert 'exploratory_conclusions' in result
                assert result['confidence'] > 0.0

    def test_empty_question_handling(self, conclusions_agent, mock_state_with_profile):
        """Test handling when no specific question is provided."""
        state = mock_state_with_profile
        state.user_intent.analysis_question = None

        # Create a response with the default question text
        empty_question_response = {
            "original_question": "General Exploratory Analysis",
            "direct_answer": "This dataset contains employee information with age, salary, and department data.",
            "key_findings": ["F1", "F2", "F3"],
            "statistical_insights": ["I1"],
            "data_quality_notes": ["Q1"],
            "recommendations": ["R1", "R2"],
            "limitations": ["L1"],
            "confidence_score": 0.80,
            "conclusions_cells": [],
            "visualization_cells": []
        }

        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = empty_question_response

            result = conclusions_agent.process(state)

            # Should default to general exploratory analysis
            assert 'exploratory_conclusions' in result
            output = result['exploratory_conclusions']
            assert 'General' in output.original_question or 'Exploratory' in output.original_question

    def test_limitations_acknowledgment(self, conclusions_agent, mock_state_with_profile, mock_llm_response):
        """Test that limitations are acknowledged."""
        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = conclusions_agent.process(mock_state_with_profile)

            output = result['exploratory_conclusions']
            assert len(output.limitations) > 0
            # Limitations should be meaningful
            assert any(len(lim) > 10 for lim in output.limitations)

    def test_data_quality_integration(self, conclusions_agent, tmp_path):
        """Test integration of data quality issues into conclusions."""
        csv_path = tmp_path / "poor_quality.csv"
        df = pd.DataFrame({
            'col1': [1, None, 3, None, 5],
            'col2': [None, None, None, None, 1]
        })
        df.to_csv(csv_path, index=False)

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(csv_path=str(csv_path), analysis_question='Analyze this data'),
            current_phase=Phase.EXPLORATORY_CONCLUSIONS
        )

        # Mock profile with quality issues
        profile = ProfileToStrategyHandoff(
            phase1_quality_score=0.45,
            row_count=5,
            column_count=2,
            column_profiles=(
                ColumnProfile(
                    name='col1',
                    detected_type=DataType.NUMERIC_CONTINUOUS,
                    detection_confidence=0.85,
                    unique_count=3,
                    null_percentage=40.0,
                    sample_values=['1', '3', '5']
                ),
            ),
            overall_quality_score=0.45,
            missing_value_summary={'col1': 40.0, 'col2': 80.0, 'total': 60.0},
            data_quality_warnings=('High missing values in col2: 80%',),
            detected_patterns=()
        )

        state.profile_lock.grant_lock(
            cells=[],
            handoff=profile,
            quality_score=0.92,
            report=None,
            iteration=1
        )

        with patch.object(conclusions_agent.llm_agent, 'invoke_with_json') as mock_llm:
            mock_llm.return_value = {
                "original_question": "Analyze this data",
                "direct_answer": "Data has significant quality issues",
                "key_findings": ["F1", "F2", "F3"],
                "statistical_insights": ["I1"],
                "data_quality_notes": ["80% missing in col2"],
                "recommendations": ["R1", "R2"],
                "limitations": ["High missingness limits analysis"],
                "confidence_score": 0.50,
                "conclusions_cells": [],
                "visualization_cells": []
            }

            result = conclusions_agent.process(state)

            output = result['exploratory_conclusions']
            # Should mention data quality issues
            assert len(output.data_quality_notes) > 0
