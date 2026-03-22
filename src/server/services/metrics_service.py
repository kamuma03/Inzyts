import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any
from src.utils.file_utils import load_csv_robust


class MetricsService:
    """Service for computing and caching dataset metrics."""

    @lru_cache(maxsize=100)
    def get_job_metrics(self, job_id: str, csv_path: Path) -> Dict[str, Any]:
        """
        Compute and cache metrics for a job.
        Using job_id as primary key, but csv_path must be valid.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        # Load Data
        df = load_csv_robust(str(csv_path))

        # Compute Metrics
        total_rows = len(df)
        total_cols = len(df.columns)

        columns_info = []
        numeric_cols = []

        for col in df.columns:
            dtype = str(df[col].dtype)
            is_numeric = pd.api.types.is_numeric_dtype(df[col])

            col_data = {
                "name": col,
                "type": dtype,
                "missing_count": int(df[col].isnull().sum()),
                "missing_pct": float(df[col].isnull().mean() * 100),
                "unique_count": int(df[col].nunique()),
                "is_numeric": is_numeric,
            }
            columns_info.append(col_data)
            if is_numeric:
                numeric_cols.append(col)

        stats: Dict[str, Dict[str, Any]] = {}
        if numeric_cols:
            desc = df[numeric_cols].describe().to_dict()
            for desc_col, metrics in desc.items():
                stats[str(desc_col)] = {
                    k: (float(v) if pd.notnull(v) else None) for k, v in metrics.items()
                }

                try:
                    valid_data = df[desc_col].dropna()
                    if not valid_data.empty:
                        counts, bin_edges = np.histogram(valid_data, bins=10)
                        stats[str(desc_col)]["histogram"] = {
                            "counts": counts.tolist(),
                            "bin_edges": bin_edges.tolist(),
                        }
                except Exception:
                    pass

        preview = df.head(5).replace({np.nan: None}).to_dict(orient="records")

        return {
            "job_id": job_id,
            "row_count": total_rows,
            "col_count": total_cols,
            "columns": columns_info,
            "numeric_stats": stats,
            "preview": preview,
        }


metrics_service = MetricsService()
