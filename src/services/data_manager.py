import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple

import traceback
from src.utils.errors import DataLoadingError
from src.utils.logger import get_logger

from ..models.multi_file import (
    MultiFileInput,
    JoinSpecification,
    MergedDataset,
    JoinCandidate,
    JoinType,
)

logger = get_logger()


class DataService:
    """
    Unified service for data loading, metadata extraction, joining, and merging.

    Combines the former DataManager (load_data, metadata, sampling) and
    DataLoader (load_dataset, detect_joins, merge_datasets) into a single class.
    """

    MAX_FILE_SIZE_MB = 500

    # ------------------------------------------------------------------ #
    #  Loading helpers (from DataManager)
    # ------------------------------------------------------------------ #

    def load_data(self, path: str) -> pd.DataFrame:
        """
        Load data from a file path.

        Supports: .csv, .xlsx, .xls, .parquet, .log

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file format is invalid/empty.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path_obj.suffix.lower()

        try:
            if suffix in [".xlsx", ".xls"]:
                return pd.read_excel(path)
            elif suffix == ".parquet":
                return pd.read_parquet(path)

            # For .csv, .log, and others, try robust CSV loading
            from src.utils.file_utils import load_csv_robust

            return load_csv_robust(path)

        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            logger.error(f"Pandas load error: {e}")
            raise DataLoadingError(f"Invalid data file: {e}", original_error=e) from e
        except Exception as e:
            logger.error(f"Unexpected load error: {e}\n{traceback.format_exc()}")
            raise DataLoadingError(f"Failed to load data: {e}", original_error=e) from e

    # ------------------------------------------------------------------ #
    #  Metadata / sampling helpers (from DataManager)
    # ------------------------------------------------------------------ #

    def get_basic_metadata(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Extract basic metadata from a DataFrame.
        """
        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "missing_values": {
                str(k): int(v) for k, v in df.isnull().sum().to_dict().items()
            },
            "types": {
                str(k): str(v) for k, v in df.dtypes.astype(str).to_dict().items()
            },
            "duplicates": int(df.duplicated().sum()),
            "memory_usage": df.memory_usage(deep=True).sum(),
        }

    def get_unique_counts(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Get unique value counts for all columns.
        """
        return {str(k): int(v) for k, v in df.nunique().to_dict().items()}

    def get_sample(self, df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
        """
        Get a random sample of rows, falling back to head if n >= length.
        """
        if len(df) <= n:
            return df
        return df.sample(n=n, random_state=42)

    def get_head(self, df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
        """
        Get top n rows.
        """
        return df.head(n)

    # ------------------------------------------------------------------ #
    #  Dataset loading with size guard (from DataLoader)
    # ------------------------------------------------------------------ #

    def load_dataset(self, file_path: str) -> pd.DataFrame:
        """Load a dataset file into a DataFrame.

        Supports: .csv, .parquet, .log, .json, .xlsx
        """
        try:
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise ValueError(
                    f"File {file_path} is {file_size_mb:.1f} MB, exceeds limit of {self.MAX_FILE_SIZE_MB} MB"
                )

            ext = Path(file_path).suffix.lower()

            if ext == ".parquet":
                return pd.read_parquet(file_path)
            elif ext in [".xlsx", ".xls"]:
                return pd.read_excel(file_path)
            elif ext == ".json":
                return pd.read_json(file_path)
            else:
                # Use robust loader for CSV, log, and others
                from src.utils.file_utils import load_csv_robust

                return load_csv_robust(file_path)
        except FileNotFoundError:
            logger.error(f"Dataset file not found: {file_path}")
            raise
        except pd.errors.ParserError:
            logger.error(f"Dataset parsing failed: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load dataset {file_path}: {e}")
            raise e

    # ------------------------------------------------------------------ #
    #  Join detection (from DataLoader)
    # ------------------------------------------------------------------ #

    def detect_joins(self, file_paths: List[str]) -> List[JoinCandidate]:
        """
        Detect potential join keys between files based on column names.
        Optimized to O(N * C) where C is avg columns per file.
        Returns a list of candidate joins sorted by confidence.
        """
        if len(file_paths) < 2:
            return []

        # 1. Build Inverted Index: Column Name -> List of (File, OriginalName)
        column_index: Dict[
            str, List[Tuple[str, str]]
        ] = {}  # normalized_col -> [(file_path, original_col), ...]

        for path in file_paths:
            try:
                # Read just header
                ext = Path(path).suffix.lower()
                if ext == ".parquet":
                    cols = pd.read_parquet(path).columns.tolist()
                elif ext in [".xlsx", ".xls"]:
                    cols = pd.read_excel(path, nrows=0).columns.tolist()
                elif ext == ".json":
                    cols = pd.read_json(
                        path, orient="records", nrows=1
                    ).columns.tolist()
                elif ext == ".log":
                    # Simple heuristics for logs if not standard CSV
                    try:
                        cols = pd.read_csv(path, nrows=0).columns.tolist()
                    except Exception:
                        cols = ["timestamp", "message"]  # Fallback
                else:
                    cols = pd.read_csv(path, nrows=0).columns.tolist()

                for col in cols:
                    norm = col.lower().strip()
                    if norm not in column_index:
                        column_index[norm] = []
                    column_index[norm].append((path, col))
            except Exception as e:
                logger.debug(f"Skipping file {path} during join detection: {e}")
                continue

        candidates = []

        # 2. Find intersections
        # Any column appearing in > 1 file is a potential join key
        checked_pairs = set()

        for col_name, locations in column_index.items():
            if len(locations) < 2:
                continue

            # Generate pairs from this column's locations
            # Typically 1 column links 2 files. If linking 3, we get 3 pairs.
            for i in range(len(locations)):
                for j in range(i + 1, len(locations)):
                    f1, c1 = locations[i]
                    f2, c2 = locations[j]

                    # Sort to avoid duplicates (A,B) vs (B,A)
                    if f1 > f2:
                        f1, f2 = f2, f1

                    pair_id = (f1, f2, col_name)
                    if pair_id in checked_pairs:
                        continue
                    checked_pairs.add(pair_id)

                    # Scoring logic
                    score = 0.5
                    if "id" in col_name or "key" in col_name or "code" in col_name:
                        score += 0.4

                    # Heuristic: Prefer exact case match? (not implemented here, using norm)

                    if score > 0.6:
                        candidates.append(
                            JoinCandidate(
                                left_file=f1,
                                right_file=f2,
                                left_column=c1,
                                right_column=c2,
                                name_similarity=1.0,
                                type_compatibility=1.0,
                                value_overlap=0.0,
                                cardinality_ratio="unknown",
                                confidence_score=score,
                                recommended_join_type=JoinType.LEFT,
                            )
                        )

        candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        return candidates

    # ------------------------------------------------------------------ #
    #  Merge execution (from DataLoader)
    # ------------------------------------------------------------------ #

    def merge_datasets(
        self, multi_file_input: MultiFileInput
    ) -> Tuple[pd.DataFrame, MergedDataset]:
        """
        Execute the merge plan defined in MultiFileInput.
        Returns the merged DataFrame and the MergedDataset metadata.
        """
        inputs = multi_file_input.files
        if not inputs:
            raise ValueError("No input files provided")

        # Load all DataFrames
        loaded_dfs = {}  # file_path -> DataFrame
        for inp in inputs:
            loaded_dfs[inp.file_path] = self.load_dataset(inp.file_path)

        # Determine strict merge order and plan
        # If explicit_joins provided, use them.
        # If AUTO strategy, use heuristics (simplified here to just chaining strictly or failing).

        if multi_file_input.explicit_joins:
            joins = multi_file_input.explicit_joins
        else:
            # Simple auto-join: Try to chain files 0->1, 1->2 etc if candidates exist
            # For v1.8 MVP, let's rely on detect_joins logic to pick best candidates
            files = [inp.file_path for inp in inputs]
            candidates = self.detect_joins(files)

            joins = []

            # Very naive greedy merge strategy for MVP
            # A better approach would be a minimum spanning tree or evaluating a complete join graph
            merged_files = {inputs[0].file_path}

            for i in range(1, len(inputs)):
                target_file = inputs[i].file_path

                # Find best join to connect specific target_file to the already merged set
                best_join = None
                for candidate in candidates:
                    # Check if this candidate connects specific target_file to our merged cluster
                    if (
                        candidate.left_file in merged_files
                        and candidate.right_file == target_file
                    ) or (
                        candidate.right_file in merged_files
                        and candidate.left_file == target_file
                    ):
                        best_join = candidate
                        break

                if best_join:
                    # Normalize direction: left is already merged, right is new
                    if best_join.left_file in merged_files:
                        left = best_join.left_file
                        right = best_join.right_file
                        l_key = best_join.left_column
                        r_key = best_join.right_column
                    else:
                        left = best_join.right_file
                        right = best_join.left_file
                        l_key = best_join.right_column
                        r_key = best_join.left_column

                    joins.append(
                        JoinSpecification(
                            left_file=left,
                            right_file=right,
                            left_key=l_key,
                            right_key=r_key,
                            join_type=JoinType.LEFT,  # Default safe join
                        )
                    )
                    merged_files.add(target_file)
                else:
                    logger.warning(f"Could not find auto-join for {target_file}")

        # Execute joins
        # Base is the first file
        base_df = loaded_dfs[inputs[0].file_path]

        executed_joins = []

        for join_spec in joins:
            right_df = loaded_dfs[join_spec.right_file]

            # Execute merge
            # Note: Pandas merge is powerful. We assume 'left' refers to the accumulating base_df
            # if we are chaining. A robust system tracks aliases.
            # Here we simplify: we merge base_df with right_df.
            # We assume join_spec.left_file is somehow already in base_df.

            try:
                base_df = pd.merge(
                    base_df,
                    right_df,
                    left_on=join_spec.left_key,
                    right_on=join_spec.right_key,
                    how=join_spec.join_type.value,
                    suffixes=("", "_right"),  # Simple suffixing
                )

                # Record success
                executed_joins.append(
                    JoinCandidate(
                        left_file=join_spec.left_file,
                        right_file=join_spec.right_file,
                        left_column=join_spec.left_key,
                        right_column=join_spec.right_key,
                        name_similarity=1.0,
                        type_compatibility=1.0,
                        value_overlap=1.0,
                        cardinality_ratio="?",
                        confidence_score=1.0,
                        recommended_join_type=join_spec.join_type,
                    )
                )
            except Exception as e:
                logger.error(f"Join failed: {e}")

        # Create MergedDataset metadata
        merged_meta = MergedDataset(
            merged_df_path="memory",  # It's in memory here, caller might save it
            merged_hash="hash_placeholder",
            source_files=[inp.file_path for inp in inputs],
            join_plan_executed=executed_joins,
            final_row_count=len(base_df),
            final_column_count=len(base_df.columns),
            rows_dropped=sum(len(df) for df in loaded_dfs.values()) - len(base_df),
            rows_added=0,
            warnings=[],
        )

        return base_df, merged_meta


# Backward-compatible aliases
DataManager = DataService
DataLoader = DataService
