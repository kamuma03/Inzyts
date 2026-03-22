from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum


class SearchType(str, Enum):
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"  # Reserved for future use


class HyperparameterGrid(BaseModel):
    """Defines a hyperparameter search space for a specific algorithm."""

    algorithm_name: str = Field(
        description="Name of the algorithm (e.g., 'RandomForestClassifier')"
    )
    param_grid: Dict[str, List[Any]] = Field(
        description="Dictionary mapping parameter names to lists of values to try"
    )


class TuningConfig(BaseModel):
    """Configuration for the hyperparameter tuning process."""

    enabled: bool = Field(
        default=False, description="Whether to perform hyperparameter tuning"
    )
    search_type: SearchType = Field(
        default=SearchType.GRID, description="Type of search to perform"
    )
    cv_folds: int = Field(default=5, description="Number of cross-validation folds")
    scoring_metric: str = Field(
        default="accuracy",
        description="Metric to optimize (e.g., 'accuracy', 'f1', 'r2')",
    )
    n_iter: int = Field(
        default=10, description="Number of iterations for randomized search"
    )
    grids: List[HyperparameterGrid] = Field(
        default_factory=list, description="List of grids to explore"
    )
