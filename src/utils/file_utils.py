import pandas as pd
import csv
from pathlib import Path
from typing import Optional, Tuple


def detect_csv_dialect(
    file_path: str, sample_bytes: int = 4096
) -> Tuple[Optional[str], Optional[str]]:
    """
    Detects the delimiter and quotechar of a CSV file using csv.Sniffer.

    Args:
        file_path: Path to the CSV file.
        sample_bytes: Number of bytes to read for sniffing.

    Returns:
        Tuple of (delimiter, quotechar). Returns (None, None) if detection fails.
    """
    try:
        if not Path(file_path).exists():
            return None, None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Read a chunk, but skip empty lines if any at start (sniffer dislikes them)
            sample = f.read(sample_bytes)

            if not sample:
                return None, None

            try:
                dialect = csv.Sniffer().sniff(sample)
                return dialect.delimiter, dialect.quotechar
            except csv.Error:
                # Common fallback: assume comma if sniffer fails but it looks like text
                return None, None

    except Exception as e:
        # Log failure but continue (soft failure)
        # We import logger locally to avoid circular imports if logger uses file_utils
        from src.utils.logger import get_logger

        logger = get_logger()
        logger.warning(f"CSV dialect detection failed for {file_path}: {e}")
        return None, None


# Removed lru_cache to prevent returning mutable DataFrames that can be modified by callers
# and to avoid memory issues with large files. Caching should be handled by the caller
# or specific services (e.g. MetricsService) if needed.
def load_csv_robust(file_path: str, **kwargs) -> pd.DataFrame:
    """
    Loads a CSV file into a DataFrame, automatically detecting delimiter and encoding.

    Args:
        file_path: Path to the CSV file.
        **kwargs: Additional arguments passed to pd.read_csv.

    Returns:
        pd.DataFrame: The loaded DataFrame.

    Raises:
        ValueError: If the file cannot be read.
    """
    # 1. Detect delimiter
    delimiter, quotechar = detect_csv_dialect(file_path)

    # If detection failed, fallback to comma (or let pandas decide if sep=None)
    # We default to None if detection failed, letting pandas python engine guess?
    # Or default to ','? Pandas C engine is default and fast, uses ',' by default.
    # If we pass sep=None, we MUST use engine='python'.

    # Strategy:
    # If detected, use it.
    # If not detected, try default (comma).

    detected_sep = delimiter if delimiter else ","

    # 2. Try encodings
    encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    # Allow override from kwargs if user explicitly passed sep/delimiter
    if "sep" in kwargs or "delimiter" in kwargs:
        # User knows what they are doing
        pass
    else:
        # Use our detected one
        kwargs["sep"] = detected_sep
        if quotechar:
            kwargs["quotechar"] = quotechar

    last_exception = None

    # First pass attempt with detected settings
    for encoding in encodings_to_try:
        try:
            # Attempt to read with detected/default settings
            df = pd.read_csv(file_path, encoding=encoding, **kwargs)

            # HEURISTIC CHECK:
            # If we only got 1 column, but the file clearly has other delimiters, retry.
            if len(df.columns) == 1:
                # Read just the first line for sniffing (avoid full reload if possible)
                with open(file_path, "r", encoding=encoding, errors="ignore") as f:
                    first_line = f.readline()

                # Check for common delimiters that might have been missed by Sniffer
                # Prioritize semicolon as it's the most common culprit for "European CSVs"
                common_delimiters = [";", "\t", "|"]

                # Check if first line contains quotes, which might confuse simple split checks
                # Sniffer often fails on quoted fields with delimiters inside

                for candidate in common_delimiters:
                    # Simple check: does the candidate appear in the line?
                    # Better check: does it appear frequently?
                    if candidate in first_line and candidate != detected_sep:
                        # Found a better candidate! Retry immediately with this candidate
                        try:
                            # Override separator and retry
                            new_kwargs = kwargs.copy()
                            new_kwargs["sep"] = candidate
                            if "delimiter" in new_kwargs:
                                del new_kwargs["delimiter"]

                            new_df = pd.read_csv(
                                file_path, encoding=encoding, **new_kwargs
                            )

                            # If this yields more columns, accept it!
                            if len(new_df.columns) > 1:
                                return new_df
                        except Exception:
                            # If retry fails, ignore and try next candidate or return original df
                            pass

            return df

        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ) as e:
            last_exception = e
            continue
        except Exception as e:
            raise e

    # If all encodings fail with the detected separator, try one last time with python engine and auto-detect
    try:
        # Remove specific sep/quotechar to let python engine guess
        kwargs.pop("sep", None)
        kwargs.pop("delimiter", None)
        kwargs.pop("quotechar", None)
        return pd.read_csv(file_path, sep=None, engine="python", **kwargs)
    except Exception as e:
        raise ValueError(
            f"Failed to load CSV {file_path}. Last error: {last_exception}. Final attempt error: {e}"
        )
