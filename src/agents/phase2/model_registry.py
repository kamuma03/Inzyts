from src.models.handoffs import AnalysisType

MODEL_REGISTRY = {
    AnalysisType.CLASSIFICATION: [
        {
            "model_name": "LogisticRegression",
            "import_path": "sklearn.linear_model.LogisticRegression",
            "hyperparameters": {"max_iter": 1000},
            "rationale": "Simple baseline for classification",
            "priority": 1,
        },
        {
            "model_name": "RandomForestClassifier",
            "import_path": "sklearn.ensemble.RandomForestClassifier",
            "hyperparameters": {"n_estimators": 100, "random_state": 42},
            "tuning_config": {
                "enabled": True,
                "search_type": "grid",
                "cv_folds": 3,
                "scoring_metric": "accuracy",
                "grids": [
                    {
                        "algorithm_name": "RandomForestClassifier",
                        "param_grid": {
                            "n_estimators": [50, 100, 200],
                            "max_depth": [None, 10, 20],
                            "min_samples_split": [2, 5],
                        },
                    }
                ],
            },
            "rationale": "Handles mixed features well, provides feature importance",
            "priority": 2,
        },
        {
            "model_name": "GradientBoostingClassifier",
            "import_path": "sklearn.ensemble.GradientBoostingClassifier",
            "hyperparameters": {"n_estimators": 100, "random_state": 42},
            "tuning_config": {
                "enabled": True,
                "search_type": "random",
                "cv_folds": 3,
                "scoring_metric": "accuracy",
                "n_iter": 10,
                "grids": [
                    {
                        "algorithm_name": "GradientBoostingClassifier",
                        "param_grid": {
                            "n_estimators": [50, 100, 200],
                            "learning_rate": [0.01, 0.1, 0.2],
                            "max_depth": [3, 5, 7],
                        },
                    }
                ],
            },
            "rationale": "High performance ensemble method",
            "priority": 3,
        },
        {
            "model_name": "SVC",
            "import_path": "sklearn.svm.SVC",
            "hyperparameters": {"probability": True, "random_state": 42},
            "rationale": "Effective for high dimensional spaces",
            "priority": 4,
        },
    ],
    AnalysisType.REGRESSION: [
        {
            "model_name": "LinearRegression",
            "import_path": "sklearn.linear_model.LinearRegression",
            "hyperparameters": {},
            "rationale": "Simple baseline for regression",
            "priority": 1,
        },
        {
            "model_name": "RandomForestRegressor",
            "import_path": "sklearn.ensemble.RandomForestRegressor",
            "hyperparameters": {"n_estimators": 100, "random_state": 42},
            "rationale": "Captures non-linear relationships",
            "priority": 2,
        },
        {
            "model_name": "GradientBoostingRegressor",
            "import_path": "sklearn.ensemble.GradientBoostingRegressor",
            "hyperparameters": {"n_estimators": 100, "random_state": 42},
            "rationale": "High performance for regression tasks",
            "priority": 3,
        },
        {
            "model_name": "SVR",
            "import_path": "sklearn.svm.SVR",
            "hyperparameters": {},
            "rationale": "Epsilon-Support Vector Regression",
            "priority": 4,
        },
    ],
    AnalysisType.CLUSTERING: [
        {
            "model_name": "KMeans",
            "import_path": "sklearn.cluster.KMeans",
            "hyperparameters": {"n_clusters": 3, "random_state": 42},
            "rationale": "Standard clustering algorithm",
            "priority": 1,
        }
    ],
    AnalysisType.EXPLORATORY: [],
}

METRIC_REGISTRY = {
    AnalysisType.CLASSIFICATION: ["accuracy", "precision", "recall", "f1"],
    AnalysisType.REGRESSION: ["mse", "rmse", "mae", "r2"],
    AnalysisType.CLUSTERING: ["silhouette_score", "inertia"],
    AnalysisType.EXPLORATORY: [],
}

VIZ_REGISTRY = {
    AnalysisType.CLASSIFICATION: [
        {
            "viz_type": "confusion_matrix",
            "title": "Confusion Matrix",
            "when_applicable": "classification",
        },
        {
            "viz_type": "roc_curve",
            "title": "ROC Curve",
            "when_applicable": "binary_classification",
        },
    ],
    AnalysisType.REGRESSION: [
        {
            "viz_type": "residual_plot",
            "title": "Residual Plot",
            "when_applicable": "regression",
        },
        {
            "viz_type": "prediction_vs_actual",
            "title": "Predicted vs Actual",
            "when_applicable": "regression",
        },
    ],
    AnalysisType.CLUSTERING: [
        {
            "viz_type": "cluster_scatter",
            "title": "Cluster Visualization",
            "when_applicable": "clustering",
        },
        {
            "viz_type": "elbow_plot",
            "title": "Elbow Method",
            "when_applicable": "clustering",
        },
    ],
    AnalysisType.EXPLORATORY: [
        {
            "viz_type": "pairplot",
            "title": "Feature Relationships",
            "when_applicable": "exploratory",
        }
    ],
}
