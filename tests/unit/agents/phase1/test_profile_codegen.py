"""
Unit tests for ProfileCodeGeneratorAgent.

Tests the agent that converts profiling specifications into executable
Jupyter notebook cells with Python code for data profiling.

Coverage includes:
- Process method with valid specification
- LLM code generation success
- Template fallback on LLM failure
- Cache hit/miss scenarios
- Cell generation for different column types
- Import generation
- Error handling
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.phase1.profile_codegen import ProfileCodeGeneratorAgent
from src.models.state import AnalysisState, Phase
from src.models.handoffs import (
    ProfilerToCodeGenHandoff,
    ProfileCodeToValidatorHandoff,
    ColumnSpec,
    DataType,
    StatisticsRequirement,
    VisualizationRequirement,
    QualityCheckRequirement,
    MarkdownSection,
)


@pytest.fixture
def mock_llm_agent():
    """Mock LLM agent for testing."""
    with patch('src.agents.phase1.profile_codegen.BaseAgent.__init__') as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager."""
    with patch('src.agents.phase1.profile_codegen.CacheManager') as mock:
        manager = MagicMock()
        manager.get_csv_hash.return_value = "test_hash_123"
        manager.load_artifact.return_value = None
        mock.return_value = manager
        yield manager


@pytest.fixture
def sample_specification():
    """Create a sample profiling specification."""
    return ProfilerToCodeGenHandoff(
        csv_path="/data/test.csv",
        row_count=1000,
        column_count=5,
        columns=[
            ColumnSpec(
                name="age",
                detected_type=DataType.NUMERIC_CONTINUOUS,
                detection_confidence=0.95,
                analysis_approach="Statistical summary and distribution",
                suggested_visualizations=["histogram", "boxplot"]
            ),
            ColumnSpec(
                name="category",
                detected_type=DataType.CATEGORICAL,
                detection_confidence=0.90,
                analysis_approach="Frequency analysis",
                suggested_visualizations=["bar_chart"]
            ),
            ColumnSpec(
                name="date",
                detected_type=DataType.DATETIME,
                detection_confidence=0.85,
                analysis_approach="Temporal analysis",
                suggested_visualizations=["line_plot"]
            )
        ],
        statistics_requirements=[
            StatisticsRequirement(
                stat_type="descriptive",
                target_columns=["age"]
            ),
            StatisticsRequirement(
                stat_type="correlation",
                target_columns=["age"]
            )
        ],
        visualization_requirements=[
            VisualizationRequirement(
                viz_type="histogram",
                target_columns=["age"],
                title="Age Distribution"
            ),
            VisualizationRequirement(
                viz_type="boxplot",
                target_columns=["age"],
                title="Age Box Plot"
            )
        ],
        quality_check_requirements=[
            QualityCheckRequirement(
                check_type="missing_values",
                target_columns=["age", "category"]
            )
        ],
        markdown_sections=[
            MarkdownSection(
                section_type="title",
                content_guidance="Create a title for the profiling report"
            )
        ]
    )


@pytest.fixture
def sample_state():
    """Create a sample analysis state."""
    return AnalysisState(
        csv_path="/data/test.csv",
        current_phase=Phase.PHASE_1
    )


class TestProfileCodeGeneratorInitialization:
    """Test ProfileCodeGeneratorAgent initialization."""

    @patch('src.agents.phase1.profile_codegen.PROFILE_CODEGEN_PROMPT', 'TEST_PROMPT')
    @patch('src.agents.phase1.profile_codegen.BaseAgent.__init__')
    def test_init_default(self, mock_base_init):
        """Test initialization with default parameters."""
        mock_base_init.return_value = None

        agent = ProfileCodeGeneratorAgent()

        mock_base_init.assert_called_once_with(
            name="ProfileCodeGenerator",
            phase=Phase.PHASE_1,
            system_prompt="TEST_PROMPT",
            provider=None,
            model=None
        )

    @patch('src.agents.phase1.profile_codegen.BaseAgent.__init__')
    def test_init_with_custom_provider(self, mock_base_init):
        """Test initialization with custom provider."""
        mock_base_init.return_value = None

        agent = ProfileCodeGeneratorAgent(provider="anthropic", model="claude-3-5-sonnet-20241022")

        mock_base_init.assert_called_once()
        call_kwargs = mock_base_init.call_args[1]
        assert call_kwargs['provider'] == "anthropic"
        assert call_kwargs['model'] == "claude-3-5-sonnet-20241022"


class TestProcessMethodWithLLM:
    """Test process method with successful LLM generation."""

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_process_with_llm_success(self, mock_cache_class, sample_state, sample_specification):
        """Test successful LLM-based code generation."""
        # Setup mocks
        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Mock LLM response
        llm_response = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": "# Data Profiling Report",
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": "import pandas as pd\nimport numpy as np",
                    "metadata": {}
                }
            ],
            "cell_purposes": {
                "0": "Title",
                "1": "Imports"
            },
            "required_imports": ["pandas", "numpy"],
            "expected_statistics": ["descriptive_stats"],
            "expected_visualizations": 2,
            "expected_markdown_sections": ["Title", "Overview"],
            "confidence": 0.9
        }
        agent.llm_agent.invoke_with_json.return_value = json.dumps(llm_response)

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert
        assert result is not None
        assert "handoff" in result
        assert isinstance(result["handoff"], ProfileCodeToValidatorHandoff)
        assert result["confidence"] == 0.9
        assert len(result["issues"]) == 0
        assert len(result["suggestions"]) == 0

        # Verify handoff contents
        handoff = result["handoff"]
        assert len(handoff.cells) == 2
        assert handoff.total_cells == 2
        assert handoff.cell_purposes[0] == "Title"
        assert "pandas" in handoff.required_imports
        assert handoff.source_specification == sample_specification

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_process_with_complex_llm_output(self, mock_cache_class, sample_state, sample_specification):
        """Test LLM generation with complex output including all cell types."""
        # Setup
        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        llm_response = {
            "cells": [
                {"cell_type": "markdown", "source": "# Report", "metadata": {}},
                {"cell_type": "code", "source": "import pandas as pd", "metadata": {}},
                {"cell_type": "code", "source": "df = pd.read_csv('/data/test.csv')", "metadata": {}},
                {"cell_type": "markdown", "source": "## Statistics", "metadata": {}},
                {"cell_type": "code", "source": "df.describe()", "metadata": {}}
            ],
            "cell_purposes": {
                "0": "Title",
                "1": "Imports",
                "2": "Load Data",
                "3": "Stats Header",
                "4": "Descriptive Stats"
            },
            "required_imports": ["pandas", "numpy", "matplotlib", "seaborn"],
            "expected_statistics": ["mean", "median", "std"],
            "expected_visualizations": 3,
            "expected_markdown_sections": ["Report", "Statistics", "Conclusions"],
            "confidence": 0.92
        }
        agent.llm_agent.invoke_with_json.return_value = json.dumps(llm_response)

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert
        handoff = result["handoff"]
        assert handoff.total_cells == 5
        assert len(handoff.required_imports) == 4
        assert "seaborn" in handoff.required_imports
        assert handoff.expected_visualizations == 3
        assert len(handoff.expected_markdown_sections) == 3


class TestProcessMethodWithTemplateFallback:
    """Test process method falling back to templates."""

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    @patch('src.config.settings')
    def test_process_template_fallback_on_json_error(self, mock_settings, mock_cache_class,
                                                     sample_state, sample_specification):
        """Test template fallback when LLM returns invalid JSON."""
        # Setup
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Mock LLM returning invalid JSON
        agent.llm_agent.invoke_with_json.return_value = "This is not valid JSON"

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert - should use template fallback
        assert result is not None
        assert "handoff" in result
        handoff = result["handoff"]

        # Template generates multiple cells
        assert handoff.total_cells > 5
        assert len(handoff.cells) > 5

        # Check for expected sections in template
        cell_sources = [cell.source for cell in handoff.cells]
        markdown_cells = [cell.source for cell in handoff.cells if cell.cell_type == "markdown"]

        # Should have title with Inzyts version
        assert any("Data Overview" in source for source in markdown_cells)

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    @patch('src.config.settings')
    def test_process_template_fallback_on_exception(self, mock_settings, mock_cache_class,
                                                   sample_state, sample_specification):
        """Test template fallback when LLM raises exception."""
        # Setup
        mock_settings.llm.default_provider = "anthropic"
        mock_settings.llm.anthropic_model = "claude-3-5-sonnet-20241022"

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Mock LLM raising exception
        agent.llm_agent.invoke_with_json.side_effect = Exception("API Error")

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert
        assert result is not None
        handoff = result["handoff"]
        assert handoff.total_cells > 0

        # Verify imports are present
        assert len(handoff.required_imports) > 0

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    @patch('src.config.settings')
    def test_template_includes_all_sections(self, mock_settings, mock_cache_class,
                                           sample_state, sample_specification):
        """Test that template generation includes all required sections."""
        # Setup
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()
        agent.llm_agent.invoke_with_json.side_effect = json.JSONDecodeError("", "", 0)

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert
        handoff = result["handoff"]
        cell_sources = " ".join([cell.source for cell in handoff.cells])

        # Check for key sections
        assert "import pandas" in cell_sources
        assert "import numpy" in cell_sources
        assert "import matplotlib" in cell_sources
        assert "read_csv" in cell_sources
        assert "describe" in cell_sources
        assert "Missing Values" in cell_sources or "missing" in cell_sources.lower()


class TestCacheOperations:
    """Test cache hit and miss scenarios."""

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_cache_hit_reconstructs_handoff(self, mock_cache_class, sample_state, sample_specification):
        """Test that cache hit properly reconstructs the handoff."""
        # Setup cached data
        cached_data = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": "# Cached Report",
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": "import pandas as pd",
                    "metadata": {}
                }
            ],
            "result": {
                "cell_purposes": {"0": "Title", "1": "Imports"},
                "required_imports": ["pandas"],
                "expected_statistics": ["mean"],
                "expected_visualizations": 1,
                "expected_markdown_sections": ["Title"],
                "confidence": 0.85
            }
        }

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = cached_data
        mock_cache_class.return_value = mock_cache

        sample_state.using_cached_profile = True
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert - should use cached data, not call LLM
        agent.llm_agent.invoke_with_json.assert_not_called()

        assert result is not None
        handoff = result["handoff"]
        assert handoff.total_cells == 2
        assert handoff.cells[0].source == "# Cached Report"
        assert result["confidence"] == 0.85

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_cache_miss_calls_llm(self, mock_cache_class, sample_state, sample_specification):
        """Test that cache miss triggers LLM generation."""
        # Setup
        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        sample_state.using_cached_profile = True
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        llm_response = {
            "cells": [{"cell_type": "code", "source": "test", "metadata": {}}],
            "cell_purposes": {"0": "Test"},
            "required_imports": [],
            "expected_statistics": [],
            "expected_visualizations": 0,
            "expected_markdown_sections": [],
            "confidence": 0.8
        }
        agent.llm_agent.invoke_with_json.return_value = json.dumps(llm_response)

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert - should call LLM
        agent.llm_agent.invoke_with_json.assert_called_once()

        # Should save to cache
        mock_cache.save_artifact.assert_called_once()

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_cache_reconstruction_failure_falls_back_to_generation(self, mock_cache_class,
                                                                   sample_state, sample_specification):
        """Test that corrupt cache falls back to generation."""
        # Setup - corrupted cache data
        cached_data = {
            "cells": "invalid_format",  # Should be a list
            "result": {}
        }

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = cached_data
        mock_cache_class.return_value = mock_cache

        sample_state.using_cached_profile = True
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        llm_response = {
            "cells": [{"cell_type": "code", "source": "recovered", "metadata": {}}],
            "cell_purposes": {},
            "required_imports": [],
            "expected_statistics": [],
            "expected_visualizations": 0,
            "expected_markdown_sections": [],
            "confidence": 0.75
        }
        agent.llm_agent.invoke_with_json.return_value = json.dumps(llm_response)

        # Execute - should recover from bad cache
        result = agent.process(sample_state, specification=sample_specification)

        # Assert - should have called LLM for recovery
        agent.llm_agent.invoke_with_json.assert_called_once()
        assert result["handoff"].cells[0].source == "recovered"


class TestBuildGenerationPrompt:
    """Test prompt building logic."""

    def test_build_prompt_groups_columns_by_type(self, sample_specification):
        """Test that prompt groups columns by data type."""
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        prompt = agent._build_generation_prompt(sample_specification)

        assert "test.csv" in prompt
        assert "ROWS: 1000" in prompt
        assert "COLUMNS: 5" in prompt

        # Should group columns by type
        assert "numeric_continuous" in prompt
        assert "categorical" in prompt
        assert "datetime" in prompt

    def test_build_prompt_includes_statistics_requirements(self, sample_specification):
        """Test that prompt includes statistics requirements."""
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        prompt = agent._build_generation_prompt(sample_specification)

        assert "STATISTICS REQUIREMENTS" in prompt
        assert "descriptive" in prompt
        assert "correlation" in prompt

    def test_build_prompt_includes_visualization_requirements(self, sample_specification):
        """Test that prompt includes visualization requirements."""
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        prompt = agent._build_generation_prompt(sample_specification)

        assert "VISUALIZATION REQUIREMENTS" in prompt
        assert "histogram" in prompt
        assert "Age Distribution" in prompt

    def test_build_prompt_includes_quality_checks(self, sample_specification):
        """Test that prompt includes quality check requirements."""
        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        prompt = agent._build_generation_prompt(sample_specification)

        assert "QUALITY CHECK REQUIREMENTS" in prompt
        assert "missing_values" in prompt


class TestGenerateTemplateCells:
    """Test template-based cell generation."""

    @patch('src.config.settings')
    def test_generate_template_basic_structure(self, mock_settings, sample_specification):
        """Test that template generates basic structure."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)

        assert len(cells) > 5

        # Check cell types
        markdown_cells = [c for c in cells if c.cell_type == "markdown"]
        code_cells = [c for c in cells if c.cell_type == "code"]

        assert len(markdown_cells) > 0
        assert len(code_cells) > 0



    @patch('src.config.settings')
    def test_generate_template_includes_imports(self, mock_settings, sample_specification):
        """Test that template includes necessary imports."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)

        # Find import cell
        import_cells = [c for c in cells if c.cell_type == "code" and "import" in c.source]
        assert len(import_cells) > 0

        import_code = import_cells[0].source
        assert "import pandas as pd" in import_code
        assert "import numpy as np" in import_code
        assert "import matplotlib.pyplot as plt" in import_code
        assert "import seaborn as sns" in import_code

    @patch('src.config.settings')
    def test_generate_template_includes_data_loading(self, mock_settings, sample_specification):
        """Test that template includes data loading code."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)

        # Find data loading cell
        load_cells = [c for c in cells if c.cell_type == "code" and "read_csv" in c.source]
        assert len(load_cells) > 0

        load_code = load_cells[0].source
        assert sample_specification.csv_path in load_code

    @patch('src.config.settings')
    def test_generate_template_with_numeric_columns(self, mock_settings, sample_specification):
        """Test template generation with numeric columns includes correlation."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Add another numeric column to satisfy len(numeric_cols) > 1 condition
        sample_specification.columns.append(
            ColumnSpec(
                name="salary",
                detected_type=DataType.NUMERIC_CONTINUOUS,
                detection_confidence=0.9,
                analysis_approach="Numeric"
            )
        )

        cells = agent._generate_template_cells(sample_specification)

        # Should include correlation analysis for numeric columns
        all_source = " ".join([c.source for c in cells])
        assert "correlation" in all_source.lower() or "corr" in all_source.lower()

    @patch('src.config.settings')
    def test_generate_template_includes_quality_checks(self, mock_settings, sample_specification):
        """Test that template includes data quality checks."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)

        all_source = " ".join([c.source for c in cells])
        assert "missing" in all_source.lower() or "isnull" in all_source
        assert "duplicate" in all_source.lower()


class TestBuildTemplateResult:
    """Test template result dictionary building."""

    @patch('src.config.settings')
    def test_build_template_result_creates_cell_purposes(self, mock_settings, sample_specification):
        """Test that template result includes cell purposes."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)
        result = agent._build_template_result(cells, sample_specification)

        assert "expected_markdown_sections" in result
        assert len(result["expected_markdown_sections"]) > 0
        assert "confidence" in result
        assert result["confidence"] > 0

    @patch('src.config.settings')
    def test_build_template_result_extracts_markdown_titles(self, mock_settings, sample_specification):
        """Test that template result extracts markdown section titles."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        cells = agent._generate_template_cells(sample_specification)
        result = agent._build_template_result(cells, sample_specification)

        # Should include standard sections
        sections = result["expected_markdown_sections"]
        assert "Data Profiling Report" in sections
        assert "Data Overview" in sections
        assert "Summary" in sections


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_process_without_specification(self, mock_cache_class, sample_state):
        """Test process method without specification returns error."""
        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Execute without specification
        result = agent.process(sample_state)

        # Assert
        assert result["handoff"] is None
        assert result["confidence"] == 0.0
        assert len(result["issues"]) > 0
        assert result["issues"][0].type == "missing_input"
        assert "specification" in result["issues"][0].message.lower()

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    def test_process_with_none_specification(self, mock_cache_class, sample_state):
        """Test process method with None specification."""
        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()

        # Execute with None
        result = agent.process(sample_state, specification=None)

        # Assert
        assert result["handoff"] is None
        assert len(result["suggestions"]) > 0
        assert any("Data Profiler" in s for s in result["suggestions"])


class TestCellGeneration:
    """Test cell generation for different scenarios."""

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    @patch('src.config.settings')
    def test_cells_have_correct_structure(self, mock_settings, mock_cache_class,
                                         sample_state, sample_specification):
        """Test that generated cells have correct structure."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()
        agent.llm_agent.invoke_with_json.side_effect = Exception("Force template")

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert
        handoff = result["handoff"]
        for cell in handoff.cells:
            assert hasattr(cell, "cell_type")
            assert hasattr(cell, "source")
            assert cell.cell_type in ["code", "markdown"]
            assert isinstance(cell.source, str)

    @patch('src.agents.phase1.profile_codegen.CacheManager')
    @patch('src.config.settings')
    def test_code_cells_are_valid_python_syntax(self, mock_settings, mock_cache_class,
                                                 sample_state, sample_specification):
        """Test that code cells contain valid Python (basic check)."""
        mock_settings.llm.default_provider = "openai"
        mock_settings.llm.openai_model = "gpt-4"

        mock_cache = MagicMock()
        mock_cache.get_csv_hash.return_value = "test_hash"
        mock_cache.load_artifact.return_value = None
        mock_cache_class.return_value = mock_cache

        agent = ProfileCodeGeneratorAgent()
        agent.llm_agent = MagicMock()
        agent.llm_agent.invoke_with_json.side_effect = Exception("Force template")

        # Execute
        result = agent.process(sample_state, specification=sample_specification)

        # Assert - basic syntax check
        handoff = result["handoff"]
        code_cells = [c for c in handoff.cells if c.cell_type == "code"]

        for cell in code_cells:
            # Should not have obvious syntax errors
            assert cell.source.count("(") == cell.source.count(")") or "..." in cell.source
            # Should not be empty
            assert len(cell.source.strip()) > 0
