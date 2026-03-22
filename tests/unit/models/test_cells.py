"""
Unit tests for notebook cell models.

Tests NotebookCell and CellManifest models used for representing
and manipulating Jupyter notebook cells.

Coverage includes:
- Cell creation
- to_nbformat() conversion
- Cell manifest model
- Different cell types
- Metadata handling
"""


from src.models.cells import NotebookCell, CellManifest


class TestNotebookCellCreation:
    """Test NotebookCell creation."""

    def test_create_markdown_cell_basic(self):
        """Test creating a basic markdown cell."""
        cell = NotebookCell(
            cell_type="markdown",
            source="# This is a title"
        )

        assert cell.cell_type == "markdown"
        assert cell.source == "# This is a title"
        assert cell.metadata == {}

    def test_create_code_cell_basic(self):
        """Test creating a basic code cell."""
        cell = NotebookCell(
            cell_type="code",
            source="import pandas as pd\ndf = pd.read_csv('test.csv')"
        )

        assert cell.cell_type == "code"
        assert "import pandas" in cell.source
        assert cell.metadata == {}

    def test_create_cell_with_metadata(self):
        """Test creating a cell with metadata."""
        metadata = {
            "tags": ["data-loading"],
            "collapsed": False
        }

        cell = NotebookCell(
            cell_type="code",
            source="print('Hello')",
            metadata=metadata
        )

        assert cell.metadata["tags"] == ["data-loading"]
        assert cell.metadata["collapsed"] is False

    def test_create_empty_markdown_cell(self):
        """Test creating an empty markdown cell."""
        cell = NotebookCell(
            cell_type="markdown",
            source=""
        )

        assert cell.cell_type == "markdown"
        assert cell.source == ""

    def test_create_empty_code_cell(self):
        """Test creating an empty code cell."""
        cell = NotebookCell(
            cell_type="code",
            source=""
        )

        assert cell.cell_type == "code"
        assert cell.source == ""

    def test_create_multiline_markdown_cell(self):
        """Test creating a multiline markdown cell."""
        source = """# Title

This is a paragraph.

- Bullet 1
- Bullet 2

## Subsection"""

        cell = NotebookCell(
            cell_type="markdown",
            source=source
        )

        assert "# Title" in cell.source
        assert "Bullet 1" in cell.source
        assert "## Subsection" in cell.source

    def test_create_multiline_code_cell(self):
        """Test creating a multiline code cell."""
        source = """import pandas as pd
import numpy as np

df = pd.read_csv('data.csv')
print(df.head())"""

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        assert "import pandas" in cell.source
        assert "print(df.head())" in cell.source


class TestNotebookCellToNbformat:
    """Test NotebookCell.to_nbformat() conversion."""

    def test_code_cell_to_nbformat_basic(self):
        """Test converting a basic code cell to nbformat."""
        cell = NotebookCell(
            cell_type="code",
            source="print('Hello, World!')"
        )

        nb_cell = cell.to_nbformat()

        assert nb_cell["cell_type"] == "code"
        assert nb_cell["execution_count"] is None
        assert nb_cell["metadata"] == {}
        assert nb_cell["outputs"] == []
        assert isinstance(nb_cell["source"], list)
        assert "print('Hello, World!')" in nb_cell["source"][0]

    def test_markdown_cell_to_nbformat_basic(self):
        """Test converting a basic markdown cell to nbformat."""
        cell = NotebookCell(
            cell_type="markdown",
            source="# Heading"
        )

        nb_cell = cell.to_nbformat()

        assert nb_cell["cell_type"] == "markdown"
        assert nb_cell["metadata"] == {}
        assert isinstance(nb_cell["source"], list)
        assert "# Heading" in nb_cell["source"][0]
        assert "outputs" not in nb_cell
        assert "execution_count" not in nb_cell

    def test_code_cell_to_nbformat_with_metadata(self):
        """Test converting a code cell with metadata."""
        metadata = {"tags": ["test"], "collapsed": True}

        cell = NotebookCell(
            cell_type="code",
            source="x = 1",
            metadata=metadata
        )

        nb_cell = cell.to_nbformat()

        assert nb_cell["metadata"] == metadata
        assert nb_cell["metadata"]["tags"] == ["test"]

    def test_markdown_cell_to_nbformat_with_metadata(self):
        """Test converting a markdown cell with metadata."""
        metadata = {"tags": ["documentation"]}

        cell = NotebookCell(
            cell_type="markdown",
            source="## Documentation",
            metadata=metadata
        )

        nb_cell = cell.to_nbformat()

        assert nb_cell["metadata"] == metadata

    def test_code_cell_to_nbformat_multiline(self):
        """Test converting a multiline code cell."""
        source = """import pandas as pd
df = pd.read_csv('test.csv')
print(df.head())"""

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        nb_cell = cell.to_nbformat()

        assert isinstance(nb_cell["source"], list)
        assert len(nb_cell["source"]) == 3
        assert "import pandas as pd" in nb_cell["source"][0]
        assert "df = pd.read_csv('test.csv')" in nb_cell["source"][1]
        assert "print(df.head())" in nb_cell["source"][2]

    def test_markdown_cell_to_nbformat_multiline(self):
        """Test converting a multiline markdown cell."""
        source = """# Title
Paragraph 1
Paragraph 2"""

        cell = NotebookCell(
            cell_type="markdown",
            source=source
        )

        nb_cell = cell.to_nbformat()

        assert isinstance(nb_cell["source"], list)
        assert len(nb_cell["source"]) == 3

    def test_empty_cell_to_nbformat(self):
        """Test converting an empty cell."""
        cell = NotebookCell(
            cell_type="code",
            source=""
        )

        nb_cell = cell.to_nbformat()

        assert isinstance(nb_cell["source"], list)
        assert len(nb_cell["source"]) == 1
        assert nb_cell["source"][0] == ""

    def test_code_cell_has_required_nbformat_fields(self):
        """Test that code cell has all required nbformat fields."""
        cell = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        nb_cell = cell.to_nbformat()

        # Required fields for code cells in nbformat
        assert "cell_type" in nb_cell
        assert "execution_count" in nb_cell
        assert "metadata" in nb_cell
        assert "outputs" in nb_cell
        assert "source" in nb_cell

    def test_markdown_cell_has_required_nbformat_fields(self):
        """Test that markdown cell has all required nbformat fields."""
        cell = NotebookCell(
            cell_type="markdown",
            source="# Title"
        )

        nb_cell = cell.to_nbformat()

        # Required fields for markdown cells in nbformat
        assert "cell_type" in nb_cell
        assert "metadata" in nb_cell
        assert "source" in nb_cell
        # Markdown cells should not have these
        assert "execution_count" not in nb_cell
        assert "outputs" not in nb_cell


class TestNotebookCellEdgeCases:
    """Test edge cases for NotebookCell."""

    def test_cell_with_special_characters(self):
        """Test cell with special characters."""
        source = "print('Hello \"World\"')\nprint('Line with \\n newline')"

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        nb_cell = cell.to_nbformat()
        assert isinstance(nb_cell["source"], list)

    def test_cell_with_unicode(self):
        """Test cell with unicode characters."""
        source = "# 日本語のタイトル\nprint('Émojis: 😀🎉')"

        cell = NotebookCell(
            cell_type="markdown",
            source=source
        )

        nb_cell = cell.to_nbformat()
        assert "日本語" in cell.source

    def test_cell_with_long_code(self):
        """Test cell with very long code."""
        source = "x = " + "1 + " * 100 + "1"

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        nb_cell = cell.to_nbformat()
        assert len(nb_cell["source"]) >= 1

    def test_cell_with_tabs_and_spaces(self):
        """Test cell with mixed tabs and spaces."""
        source = "\tdef function():\n\t    return True"

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        assert "\t" in cell.source

    def test_cell_source_split_preserves_content(self):
        """Test that splitting source by newline preserves all content."""
        source = "line1\nline2\nline3"

        cell = NotebookCell(
            cell_type="code",
            source=source
        )

        nb_cell = cell.to_nbformat()
        reconstructed = "\n".join(nb_cell["source"])

        assert reconstructed == source


class TestCellManifestCreation:
    """Test CellManifest creation."""

    def test_create_cell_manifest_basic(self):
        """Test creating a basic cell manifest."""
        manifest = CellManifest(
            index=0,
            cell_type="code",
            purpose="Import libraries"
        )

        assert manifest.index == 0
        assert manifest.cell_type == "code"
        assert manifest.purpose == "Import libraries"
        assert manifest.dependencies == []
        assert manifest.outputs_variables == []

    def test_create_cell_manifest_with_dependencies(self):
        """Test creating a manifest with dependencies."""
        manifest = CellManifest(
            index=3,
            cell_type="code",
            purpose="Train model",
            dependencies=[0, 1, 2],
            outputs_variables=["model", "accuracy"]
        )

        assert manifest.index == 3
        assert len(manifest.dependencies) == 3
        assert 0 in manifest.dependencies
        assert len(manifest.outputs_variables) == 2
        assert "model" in manifest.outputs_variables

    def test_create_markdown_manifest(self):
        """Test creating a manifest for markdown cell."""
        manifest = CellManifest(
            index=0,
            cell_type="markdown",
            purpose="Title section"
        )

        assert manifest.cell_type == "markdown"
        assert manifest.purpose == "Title section"

    def test_create_manifest_with_multiple_outputs(self):
        """Test manifest with multiple output variables."""
        manifest = CellManifest(
            index=5,
            cell_type="code",
            purpose="Data preprocessing",
            outputs_variables=["X_train", "X_test", "y_train", "y_test"]
        )

        assert len(manifest.outputs_variables) == 4
        assert "X_train" in manifest.outputs_variables
        assert "y_test" in manifest.outputs_variables

    def test_create_manifest_with_complex_dependencies(self):
        """Test manifest with complex dependency chain."""
        manifest = CellManifest(
            index=10,
            cell_type="code",
            purpose="Final evaluation",
            dependencies=[0, 2, 5, 8, 9],
            outputs_variables=["final_score", "report"]
        )

        assert len(manifest.dependencies) == 5
        assert max(manifest.dependencies) < manifest.index


class TestCellManifestUseCases:
    """Test CellManifest use cases."""

    def test_manifest_for_import_cell(self):
        """Test manifest for import cell."""
        manifest = CellManifest(
            index=0,
            cell_type="code",
            purpose="Import required libraries",
            dependencies=[],
            outputs_variables=[]
        )

        assert manifest.index == 0
        assert len(manifest.dependencies) == 0
        assert manifest.purpose == "Import required libraries"

    def test_manifest_for_data_loading_cell(self):
        """Test manifest for data loading cell."""
        manifest = CellManifest(
            index=1,
            cell_type="code",
            purpose="Load dataset",
            dependencies=[0],  # Depends on imports
            outputs_variables=["df"]
        )

        assert manifest.dependencies == [0]
        assert manifest.outputs_variables == ["df"]

    def test_manifest_for_visualization_cell(self):
        """Test manifest for visualization cell."""
        manifest = CellManifest(
            index=5,
            cell_type="code",
            purpose="Create distribution plots",
            dependencies=[1, 2],  # Depends on data loading and preprocessing
            outputs_variables=[]  # Visualizations typically don't output variables
        )

        assert manifest.purpose == "Create distribution plots"
        assert len(manifest.outputs_variables) == 0

    def test_manifest_for_model_training_cell(self):
        """Test manifest for model training cell."""
        manifest = CellManifest(
            index=8,
            cell_type="code",
            purpose="Train Random Forest model",
            dependencies=[0, 1, 3, 5],  # Imports, data, preprocessing, feature engineering
            outputs_variables=["rf_model", "training_time"]
        )

        assert "model" in manifest.purpose
        assert "rf_model" in manifest.outputs_variables


class TestCellManifestSerialization:
    """Test CellManifest serialization."""

    def test_manifest_json_serialization(self):
        """Test CellManifest JSON serialization."""
        manifest = CellManifest(
            index=3,
            cell_type="code",
            purpose="Data analysis",
            dependencies=[0, 1, 2],
            outputs_variables=["result"]
        )

        if hasattr(manifest, 'model_dump_json'):
            json_str = manifest.model_dump_json()
        else:
            json_str = manifest.json()

        assert "3" in json_str
        assert "Data analysis" in json_str

    def test_manifest_deserialization(self):
        """Test CellManifest deserialization."""
        manifest = CellManifest(
            index=2,
            cell_type="markdown",
            purpose="Section header"
        )

        if hasattr(manifest, 'model_dump_json'):
            json_str = manifest.model_dump_json()
            restored = CellManifest.model_validate_json(json_str)
        else:
            json_str = manifest.json()
            restored = CellManifest.parse_raw(json_str)

        assert restored.index == manifest.index
        assert restored.cell_type == manifest.cell_type
        assert restored.purpose == manifest.purpose

    def test_manifest_dict_conversion(self):
        """Test CellManifest to dict conversion."""
        manifest = CellManifest(
            index=5,
            cell_type="code",
            purpose="Test",
            dependencies=[1, 2],
            outputs_variables=["var1"]
        )

        if hasattr(manifest, 'model_dump'):
            data = manifest.model_dump()
        else:
            data = manifest.dict()

        assert data["index"] == 5
        assert data["cell_type"] == "code"
        assert data["dependencies"] == [1, 2]


class TestCellAndManifestIntegration:
    """Test integration between NotebookCell and CellManifest."""

    def test_cell_and_manifest_together(self):
        """Test using cell and manifest together."""
        cell = NotebookCell(
            cell_type="code",
            source="df = pd.read_csv('data.csv')"
        )

        manifest = CellManifest(
            index=1,
            cell_type="code",
            purpose="Load data",
            dependencies=[0],
            outputs_variables=["df"]
        )

        # Cell and manifest should have matching cell_type
        assert cell.cell_type == manifest.cell_type

    def test_multiple_cells_with_manifests(self):
        """Test managing multiple cells with their manifests."""
        cells = [
            NotebookCell(cell_type="code", source="import pandas as pd"),
            NotebookCell(cell_type="code", source="df = pd.read_csv('data.csv')"),
            NotebookCell(cell_type="markdown", source="## Analysis"),
            NotebookCell(cell_type="code", source="df.describe()")
        ]

        manifests = [
            CellManifest(index=0, cell_type="code", purpose="Imports"),
            CellManifest(index=1, cell_type="code", purpose="Load data", dependencies=[0]),
            CellManifest(index=2, cell_type="markdown", purpose="Header"),
            CellManifest(index=3, cell_type="code", purpose="Statistics", dependencies=[1])
        ]

        assert len(cells) == len(manifests)
        for i, (cell, manifest) in enumerate(zip(cells, manifests)):
            assert manifest.index == i
            assert cell.cell_type == manifest.cell_type


class TestNotebookCellPydanticFeatures:
    """Test Pydantic-specific features of NotebookCell."""

    def test_cell_field_validation(self):
        """Test that cell validates required fields."""
        # Should work with all required fields
        cell = NotebookCell(
            cell_type="code",
            source="print('test')"
        )
        assert cell is not None

    def test_cell_dict_export(self):
        """Test exporting cell to dict."""
        cell = NotebookCell(
            cell_type="markdown",
            source="# Title",
            metadata={"tags": ["intro"]}
        )

        if hasattr(cell, 'model_dump'):
            data = cell.model_dump()
        else:
            data = cell.dict()

        assert data["cell_type"] == "markdown"
        assert data["source"] == "# Title"
        assert data["metadata"]["tags"] == ["intro"]

    def test_cell_json_export(self):
        """Test exporting cell to JSON."""
        cell = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        if hasattr(cell, 'model_dump_json'):
            json_str = cell.model_dump_json()
        else:
            json_str = cell.json()

        assert '"cell_type":"code"' in json_str or '"cell_type": "code"' in json_str
        assert "x = 1" in json_str


class TestCellManifestPydanticFeatures:
    """Test Pydantic-specific features of CellManifest."""

    def test_manifest_field_validation(self):
        """Test manifest field validation."""
        # Should work with required fields
        manifest = CellManifest(
            index=0,
            cell_type="code",
            purpose="Test"
        )
        assert manifest is not None

    def test_manifest_default_values(self):
        """Test manifest default values."""
        manifest = CellManifest(
            index=0,
            cell_type="code",
            purpose="Test"
        )

        # Should have default empty lists
        assert manifest.dependencies == []
        assert manifest.outputs_variables == []

    def test_manifest_with_empty_lists(self):
        """Test manifest explicitly with empty lists."""
        manifest = CellManifest(
            index=1,
            cell_type="markdown",
            purpose="Header",
            dependencies=[],
            outputs_variables=[]
        )

        assert len(manifest.dependencies) == 0
        assert len(manifest.outputs_variables) == 0


class TestNotebookCellComparison:
    """Test comparing NotebookCell instances."""

    def test_cells_with_same_content(self):
        """Test cells with identical content."""
        cell1 = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        cell2 = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        # Compare field by field
        assert cell1.cell_type == cell2.cell_type
        assert cell1.source == cell2.source
        assert cell1.metadata == cell2.metadata

    def test_cells_with_different_content(self):
        """Test cells with different content."""
        cell1 = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        cell2 = NotebookCell(
            cell_type="code",
            source="x = 2"
        )

        assert cell1.source != cell2.source

    def test_cells_with_different_types(self):
        """Test cells with different types."""
        cell1 = NotebookCell(
            cell_type="code",
            source="x = 1"
        )

        cell2 = NotebookCell(
            cell_type="markdown",
            source="x = 1"
        )

        assert cell1.cell_type != cell2.cell_type
