"""Handoffs package — inter-agent communication schemas.

Star-imports everything defined in ``src.models._handoffs``; cells helpers
are re-exported from ``src.models.cells`` for callers that bundled both.
"""

from src.models._handoffs import *  # noqa: F401,F403
from src.models._handoffs import ModelSpec  # explicit so the alias below resolves
from src.models.cells import NotebookCell, CellManifest  # noqa: F401

# Backward compatibility — older code referenced FeatureSpec.
FeatureSpec = ModelSpec
