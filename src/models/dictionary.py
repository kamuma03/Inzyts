from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class DictionaryEntry(BaseModel):
    """Metadata for a single column."""

    column_name: str
    description: str
    data_type: Optional[str] = None
    constraints: Optional[str] = None  # e.g. "min=0, max=100" or "unique"
    example_values: List[Any] = Field(default_factory=list)


class DataDictionary(BaseModel):
    """Container for the full dataset dictionary."""

    entries: List[DictionaryEntry] = []

    def to_simple_dict(self) -> Dict[str, str]:
        """Convert to simple column->description mapping for agents."""
        return {e.column_name: e.description for e in self.entries}

    def get_entry(self, column_name: str) -> Optional[DictionaryEntry]:
        """Get entry by column name."""
        for entry in self.entries:
            if entry.column_name == column_name:
                return entry
        return None
