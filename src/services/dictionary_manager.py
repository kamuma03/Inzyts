import json
from pathlib import Path
from typing import Optional
from ..models.dictionary import DataDictionary, DictionaryEntry
from ..utils.logger import get_logger
from src.utils.file_utils import load_csv_robust

logger = get_logger()


class DictionaryParser:
    """Parses dictionary files (CSV/JSON/TXT) into DataDictionary model."""

    @staticmethod
    def parse(file_path: str) -> Optional[DataDictionary]:
        if not Path(file_path).exists():
            logger.warning(f"Dictionary file not found: {file_path}")
            return None

        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".csv":
                return DictionaryParser._parse_csv(file_path)
            elif ext == ".json":
                return DictionaryParser._parse_json(file_path)
            elif ext == ".txt":
                return DictionaryParser._parse_txt(file_path)
            else:
                logger.warning(f"Unsupported dictionary format: {ext}")
                return None
        except Exception as e:
            logger.error(f"Failed to parse dictionary {file_path}: {e}")
            return None

    @staticmethod
    def _parse_csv(path: str) -> DataDictionary:
        try:
            df = load_csv_robust(path)
        except Exception as e:
            logger.error(f"Error loading CSV dictionary {path}: {e}")
            raise e
        # Normalize columns
        df.columns = [c.lower().strip() for c in df.columns]

        entries = []
        # Optimized approach: to_dict('records')

        # Optimized approach: to_dict('records')
        records = df.to_dict("records")
        for row in records:
            col_name = (
                row.get("column")
                or row.get("field")
                or row.get("name")
                or row.get("column_name")
            )
            desc = row.get("description") or row.get("desc") or row.get("definition")

            if col_name and desc:
                entries.append(
                    DictionaryEntry(
                        column_name=f"{col_name}",
                        description=f"{desc}",
                        data_type=f"{row.get('type', '')}",
                        constraints=f"{row.get('constraints', '')}",
                    )
                )

        return DataDictionary(entries=entries)

    @staticmethod
    def _parse_json(path: str) -> DataDictionary:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = []
        # Support list of dicts or dict of dicts
        if isinstance(data, list):
            for item in data:
                entry = DictionaryEntry(
                    column_name=item.get("column_name") or item.get("name"),
                    description=item.get("description"),
                    data_type=item.get("data_type"),
                    constraints=item.get("constraints"),
                )
                entries.append(entry)
        elif isinstance(data, dict):
            # Maybe {"col1": "desc1", ...} or {"col1": {"description": "..."}}
            for k, v in data.items():
                if isinstance(v, str):
                    entries.append(DictionaryEntry(column_name=k, description=v))
                elif isinstance(v, dict):
                    entries.append(
                        DictionaryEntry(
                            column_name=k,
                            description=v.get("description", ""),
                            data_type=v.get("type"),
                            constraints=v.get("constraints"),
                        )
                    )

        return DataDictionary(entries=entries)

    @staticmethod
    def _parse_txt(path: str) -> DataDictionary:
        """Parse a text file data dictionary.

        Supports multiple formats:
        - Tab-separated: column_name\tdescription
        - Colon-separated: column_name: description
        - Equals-separated: column_name = description
        """
        entries = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                col_name = None
                desc = None

                # Try tab-separated first
                if "\t" in line:
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        col_name, desc = parts[0].strip(), parts[1].strip()
                # Try colon-separated
                elif ": " in line:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        col_name, desc = parts[0].strip(), parts[1].strip()
                # Try equals-separated
                elif " = " in line:
                    parts = line.split(" = ", 1)
                    if len(parts) == 2:
                        col_name, desc = parts[0].strip(), parts[1].strip()

                if col_name and desc:
                    entries.append(
                        DictionaryEntry(column_name=col_name, description=desc)
                    )

        return DataDictionary(entries=entries)
