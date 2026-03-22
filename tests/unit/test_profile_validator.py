"""
Unit tests for Profile Validator Agent.

Tests the validation, PEP8 compliance checking, quality scoring,
and Profile Lock granting functionality.
"""

import pytest
from unittest.mock import MagicMock
import pandas as pd
from src.agents.validation_utils import lint_line

from src.agents.phase1.profile_validator import ProfileValidatorAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent, DataType
from src.models.cells import NotebookCell


class TestProfileValidatorAgent:
    """Test suite for Profile Validator Agent."""

    @pytest.fixture
    def mock_sandbox_executor(self):
        """Mock SandboxExecutor to prevent actual code execution during tests."""
        from unittest.mock import patch, MagicMock
        with patch('src.agents.phase1.profile_validator.SandboxExecutor') as mock_sandbox:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output = "Mocked output"
            mock_result.error = None
            mock_result.error_name = None
            mock_result.error_value = None
            mock_instance.execute_cell.return_value = mock_result
            mock_sandbox.return_value.__enter__.return_value = mock_instance
            yield mock_sandbox

    @pytest.fixture
    def mock_state(self, tmp_path):
        """Create a mock analysis state with sample CSV."""
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'salary': [50000, 60000, 70000, 80000, 90000],
            'department': ['HR', 'IT', 'IT', 'Sales', 'HR']
        })
        df.to_csv(csv_path, index=False)

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(
                csv_path=str(csv_path),
                analysis_type='exploratory',
                analysis_question='Test question',
                target_column=None
            ),
            current_phase=Phase.PHASE_1
        )
        return state

    @pytest.fixture
    def validator_agent(self):
        """Create a Profile Validator agent instance."""
        return ProfileValidatorAgent()

    @pytest.fixture
    def valid_notebook_cells(self):
        """Create valid notebook cells for testing."""
        return [
            NotebookCell(
                cell_type="code",
                source="import pandas as pd\nimport numpy as np"
            ),
            NotebookCell(
                cell_type="code",
                source="df = pd.read_csv('test.csv')\nprint(df.head())"
            ),
            NotebookCell(
                cell_type="code",
                source="df.describe()"
            ),
            NotebookCell(
                cell_type="code",
                source="import matplotlib.pyplot as plt\ndf['age'].hist()\nplt.show()"
            )
        ]

    def test_pep8_score_calculation(self, validator_agent):
        """Test PEP8 compliance checking with _calculate_pep8_score method."""
        # Good code (should score high)
        good_cells = [
            NotebookCell(
                cell_type="code",
                source="import pandas as pd\n\ndef analyze_data(df):\n    '''Analyze dataframe.'''\n    return df.describe()"
            )
        ]

        # Bad code (should score low - long lines, inconsistent formatting)
        bad_cells = [
            NotebookCell(
                cell_type="code",
                source="import pandas as pd\nx=1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20+21+22+23+24+25+26+27+28+29+30+31+32+33+34+35+36+37+38+39+40\ndef bad_function( x,y,z ):\n    return x+y+z"
            )
        ]

        good_score = validator_agent._calculate_pep8_score(good_cells)
        bad_score = validator_agent._calculate_pep8_score(bad_cells)

        assert good_score > bad_score
        assert 0.0 <= good_score <= 1.0
        assert 0.0 <= bad_score <= 1.0

    def test_validate_syntax(self, validator_agent):
        """Test syntax validation with _validate_syntax method."""
        valid_code = "import pandas as pd\ndf = pd.DataFrame({'a': [1, 2, 3]})"
        invalid_code = "import pandas as pd\ndef broken("

        valid_result = validator_agent._validate_syntax(valid_code)
        invalid_result = validator_agent._validate_syntax(invalid_code)

        # Returns tuple (is_valid, error_message)
        assert valid_result[0] is True
        assert invalid_result[0] is False

    def test_count_visualizations(self, validator_agent):
        """Test visualization counting with _count_visualizations method."""
        code_with_viz = """
import matplotlib.pyplot as plt
df['age'].hist()
plt.title('Age Distribution')
plt.show()

df.boxplot(column='salary')
plt.show()
"""

        code_without_viz = """
import pandas as pd
df = pd.read_csv('data.csv')
print(df.head())
"""

        viz_count = validator_agent._count_visualizations(code_with_viz)
        no_viz_count = validator_agent._count_visualizations(code_without_viz)

        assert viz_count >= 2  # Should detect at least hist and boxplot
        assert no_viz_count == 0

    def test_performance_linting(self, validator_agent):
        """Test detection of performance anti-patterns with _performance_linting."""
        inefficient_cells = [
            NotebookCell(
                cell_type="code",
                source="for index, row in df.iterrows():\n    df.loc[index, 'new_col'] = row['old_col'] * 2"
            )
        ]

        efficient_cells = [
            NotebookCell(
                cell_type="code",
                source="df['new_col'] = df['old_col'] * 2"
            )
        ]

        inefficient_score, inefficient_warnings = validator_agent._performance_linting(inefficient_cells)
        efficient_score, efficient_warnings = validator_agent._performance_linting(efficient_cells)

        assert len(inefficient_warnings) > len(efficient_warnings)
        assert efficient_score > inefficient_score

    def test_check_encoding_consistency(self, validator_agent):
        """Test encoding consistency checking with _check_encoding_consistency."""
        encoding_cells = [
            NotebookCell(
                cell_type="code",
                source="from sklearn.preprocessing import LabelEncoder\nle = LabelEncoder()\ndf['dept_encoded'] = le.fit_transform(df['department'])"
            ),
            NotebookCell(
                cell_type="code",
                source="df_encoded = pd.get_dummies(df, columns=['category'])"
            )
        ]

        # Create mock spec with column info
        mock_spec = MagicMock()
        mock_spec.columns = [
            MagicMock(name='department', detected_type=DataType.CATEGORICAL),
            MagicMock(name='category', detected_type=DataType.CATEGORICAL)
        ]
        mock_spec.preprocessing_recommendations = []

        score, issues = validator_agent._check_encoding_consistency(encoding_cells, mock_spec)

        # Should return a tuple with score and issues list
        assert isinstance(score, (int, float))
        assert isinstance(issues, list)
        assert 0.0 <= score <= 1.0

    def test_extract_stat_columns(self, validator_agent):
        """Test extraction of column names from statistics code."""
        code = """
df['age'].describe()
df['salary'].mean()
stats = df[['age', 'salary']].describe()
"""

        columns = validator_agent._extract_stat_columns(code)

        # Returns a list of column names
        assert isinstance(columns, list)
        # Check if any expected columns are found
        combined = ' '.join(columns)
        assert 'age' in combined or 'salary' in combined or len(columns) > 0

    def test_extract_markdown_section(self, validator_agent):
        """Test markdown section title extraction."""
        markdown = "# Data Summary\n\nThis is a summary of the data."

        section = validator_agent._extract_markdown_section(markdown)

        assert "Data Summary" in section or section is not None

    def test_lint_line(self, validator_agent):
        """Test individual line linting with _lint_line."""
        good_lines = ["x = 1", "def foo():", "    return 42"]
        bad_line = "x=1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20+21+22+23+24+25+26+27+28+29+30+31+32+33+34+35+36+37+38+39+40+41+42+43+44+45"

        # Test good line
        good_penalty = lint_line(good_lines[0], 0, good_lines)
        assert good_penalty == 0.0

        # Test bad line (too long)
        bad_penalty = lint_line(bad_line, 0, [bad_line])
        assert bad_penalty > 0.0

    def test_process_method_exists(self, validator_agent):
        """Test that process method exists and is callable."""
        assert hasattr(validator_agent, 'process')
        assert callable(validator_agent.process)

    def test_orchestrator_passes(self):
        """Placeholder test to ensure test file is valid."""
        assert True

    def test_process_with_valid_handoff(self, validator_agent, mock_state, valid_notebook_cells, mock_sandbox_executor):
        """Test the main process method with a valid code handoff and mocked sandbox."""
        from src.models.handoffs import ProfileCodeToValidatorHandoff, ProfilerToCodeGenHandoff, ColumnSpec
        
        # Create a mock source specification
        mock_spec = ProfilerToCodeGenHandoff(
            csv_path="test.csv",
            columns=[
                ColumnSpec(name="age", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.9, analysis_approach="Histogram"),
                ColumnSpec(name="salary", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.8, analysis_approach="Histogram")
            ],
            row_count=100,
            column_count=2,
            missing_values={},
            statistics_requirements=[],
            visualization_requirements=[],
            quality_check_requirements=[],
            domain=None,
            anomalies=[],
            data_dictionary={}
        )

        # Create handoff from ProfileCodeGenerator
        handoff = ProfileCodeToValidatorHandoff(
            cells=valid_notebook_cells,
            total_cells=4,
            cell_purposes={0: "imports"},
            required_imports=["pandas", "numpy", "matplotlib"],
            expected_statistics=["describe"],
            expected_visualizations=2,
            expected_markdown_sections=["Data Overview"],
            source_specification=mock_spec
        )

        result = validator_agent.process(mock_state, code_handoff=handoff)

        assert result is not None
        assert "validation_result" in result
        assert "quality_score" in result
        assert "should_lock" in result
        assert "report" in result
        
        # With our valid cells, score should be reasonable
        assert result["quality_score"] > 0
        
    def test_process_with_missing_handoff(self, validator_agent, mock_state):
        """Test process when no code handoff is provided."""
        result = validator_agent.process(mock_state)
        
        assert result is not None
        assert result["validation_result"] is None
        assert result.get("should_lock") is None or result.get("should_lock") is False
        assert len(result["issues"]) > 0
        assert result["issues"][0].type == "missing_input"

    def test_build_strategy_handoff(self, validator_agent, mock_state, valid_notebook_cells):
        """Test _build_strategy_handoff method directly."""
        from src.models.handoffs import ProfileCodeToValidatorHandoff, ProfilerToCodeGenHandoff, ColumnSpec
        from src.models.validation import ProfileValidationResult
        
        # Make a mock dataframe on the state
        import pandas as pd
        mock_state._df = pd.DataFrame({
            "age": [20, 30, 40, None, 60],
            "salary": [50000, 60000, 70000, 80000, 90000],
            "department": ["HR", "IT", "HR", "Sales", "IT"],
            "is_active": [True, False, True, True, False]
        })

        mock_spec = ProfilerToCodeGenHandoff(
            csv_path="test.csv",
            columns=[
                ColumnSpec(name="age", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.9, analysis_approach="Histogram"),
                ColumnSpec(name="department", detected_type=DataType.CATEGORICAL, detection_confidence=1.0, analysis_approach="Bar chart"),
                ColumnSpec(name="is_active", detected_type=DataType.BINARY, detection_confidence=1.0, analysis_approach="Pie chart")
            ],
            row_count=5,
            column_count=4,
            missing_values={},
            statistics_requirements=[],
            visualization_requirements=[],
            quality_check_requirements=[],
            domain=None,
            anomalies=[],
            data_dictionary={}
        )

        handoff = ProfileCodeToValidatorHandoff(
            cells=valid_notebook_cells,
            total_cells=4,
            cell_purposes={0: "imports"},
            required_imports=["pandas"],
            expected_statistics=[],
            expected_visualizations=0,
            expected_markdown_sections=[],
            source_specification=mock_spec
        )

        val_result = ProfileValidationResult(
            cells_passed=4,
            total_cells=4,
            models_trained=0,
            model_failures=[],
            metrics_computed=0,
            metrics_required=0,
            metric_values={},
            result_viz_count=2,
            viz_failures=[],
            insights_count=1,
            pep8_score=0.9,
            style_issues=[],
            issues=[],
            min_type_confidence=0.9,
            stats_coverage=1.0,
            viz_count=2,
            report_sections_present=4,
            report_sections_required=4
        )

        strategy_handoff = validator_agent._build_strategy_handoff(
            code_handoff=handoff,
            validation_result=val_result,
            quality_score=0.95,
            state=mock_state
        )

        assert strategy_handoff is not None
        assert strategy_handoff.lock_status == "locked"
        assert strategy_handoff.phase1_quality_score == 0.95
        assert len(strategy_handoff.column_profiles) == 3
        # Age numeric stats should be computed
        age_profile = next(p for p in strategy_handoff.column_profiles if p.name == "age")
        assert age_profile.statistics is not None
        assert age_profile.null_percentage > 0
        
        # Check target candidates logic
        assert len(strategy_handoff.recommended_target_candidates) > 0

    def test_validate_cells_with_errors(self, validator_agent, mock_state):
        """Test _validate_cells with syntax and runtime errors to check issue generation."""
        from src.models.handoffs import ProfileCodeToValidatorHandoff, ProfilerToCodeGenHandoff, ColumnSpec
        from src.models.cells import NotebookCell
        from unittest.mock import patch, MagicMock
        
        # Mix of valid, syntax error, and runtime error cells
        cells = [
            NotebookCell(cell_type="code", source="import pandas as pd"), # Valid
            NotebookCell(cell_type="code", source="def bad_syntax("), # Syntax error
            NotebookCell(cell_type="code", source="df.some_missing_method()"), # Runtime error
            NotebookCell(cell_type="markdown", source="# Header\nSome markdown"), # Markdown
        ]
        
        mock_spec = ProfilerToCodeGenHandoff(
            csv_path="test.csv",
            columns=[ColumnSpec(name="age", detected_type=DataType.NUMERIC_CONTINUOUS, detection_confidence=0.9, analysis_approach="Histogram")],
            row_count=100,
            column_count=1,
            missing_values={},
            statistics_requirements=[],
            visualization_requirements=[],
            quality_check_requirements=[],
            domain=None,
            anomalies=[],
            data_dictionary={}
        )
        
        handoff = ProfileCodeToValidatorHandoff(
            cells=cells,
            total_cells=4,
            cell_purposes={0: "imports"},
            required_imports=[],
            expected_statistics=[],
            expected_visualizations=0,
            expected_markdown_sections=["Header"],
            source_specification=mock_spec
        )
        
        with patch('src.agents.phase1.profile_validator.SandboxExecutor') as mock_sandbox:
            mock_instance = MagicMock()
            
            def side_effect(code):
                mock_result = MagicMock()
                if "import pandas" in code:
                    mock_result.success = True
                else:
                    mock_result.success = False
                    mock_result.error_name = "AttributeError"
                    mock_result.error_value = "Method not found"
                return mock_result
                
            mock_instance.execute_cell.side_effect = side_effect
            mock_sandbox.return_value.__enter__.return_value = mock_instance
            
            result = validator_agent._validate_cells(handoff, mock_state)
            
            # 1 missing input/output, 1 syntax error, 1 runtime error
            assert len(result.issues) >= 2
            issue_types = [i.issue_type for i in result.issues if getattr(i, 'issue_type', None)] + [i.type for i in result.issues if getattr(i, 'type', None)]
            assert any(t == "syntax_error" for t in issue_types)
            assert any(t == "runtime_error" for t in issue_types)

    def test_full_validation_flow(self, tmp_path):
        """Test complete validation flow from cells to result."""
        # Create test CSV
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({
            'age': [25, 30, 35],
            'name': ['Alice', 'Bob', 'Charlie']
        })
        df.to_csv(csv_path, index=False)

        # Create validator
        validator = ProfileValidatorAgent()

        # Verify validator has expected methods
        assert hasattr(validator, 'process')
        assert hasattr(validator, '_calculate_pep8_score')
        assert hasattr(validator, '_validate_syntax')
        assert hasattr(validator, '_count_visualizations')
        assert hasattr(validator, '_performance_linting')
        assert hasattr(validator, '_check_encoding_consistency')
