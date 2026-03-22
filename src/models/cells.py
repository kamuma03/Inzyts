"""
Notebook cell models for the Multi-Agent Data Analysis System.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class NotebookCell(BaseModel):
    """
    Represents a single Jupyter notebook cell.

    This is an intermediate representation that is easier to work with
    than raw JSON. It allows for agent-friendly manipulation before
    final conversion to .ipynb format.
    """

    cell_type: str  # "code" or "markdown"
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_nbformat(self) -> Dict[str, Any]:
        """Convert to nbformat cell dictionary."""
        if self.cell_type == "code":
            return {
                "cell_type": "code",
                "execution_count": None,
                "metadata": self.metadata,
                "outputs": [],
                "source": self.source.split("\n"),
            }
        else:
            return {
                "cell_type": "markdown",
                "metadata": self.metadata,
                "source": self.source.split("\n"),
            }


class CellManifest(BaseModel):
    """Describes a cell's purpose and dependencies."""

    index: int
    cell_type: str
    purpose: str
    dependencies: List[int] = []  # Indices of cells this depends on
    outputs_variables: List[str] = []
