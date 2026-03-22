import textwrap
from typing import List, Tuple, Dict, Any
from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType
from src.models.state import AnalysisState
from src.models.cells import NotebookCell, CellManifest


class TemplateGenerator:
    """Helper for generating template-based analysis code."""

    def generate_template_cells(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> Tuple[List[NotebookCell], List[CellManifest]]:
        """Generate template-based cells when LLM fails."""
        # Dispatch to specialized templates based on AnalysisType
        if strategy.analysis_type == AnalysisType.CAUSAL:
            return self._generate_diagnostic_template(strategy, state)
        elif strategy.analysis_type == AnalysisType.COMPARATIVE:
            return self._generate_comparative_template(strategy, state)
        elif strategy.analysis_type == AnalysisType.TIME_SERIES:
            return self._generate_forecasting_template(strategy, state)
        elif strategy.analysis_type == AnalysisType.CLUSTERING:
            return self._generate_segmentation_template(strategy, state)
        elif strategy.analysis_type == AnalysisType.DIMENSIONALITY:
            return self._generate_dimensionality_template(strategy, state)

        cells = []
        manifest = []
        idx = 0

        # Analysis header
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Analysis Phase\n\n**Objective**: {strategy.analysis_objective}\n\n"
                f"**Analysis Type**: {strategy.analysis_type.value.title()}",
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="markdown",
                purpose="Analysis header",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        # Imports
        imports_code = self._generate_imports(strategy)
        cells.append(NotebookCell(cell_type="code", source=imports_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Import libraries",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        # Load data (assume profiling has loaded it)
        load_code = """# Load data (assuming profiling has run)
# We strictly rely on the 'df' variable from Phase 1
df_analysis = df.copy()
print(f"Analysis dataset shape: {df_analysis.shape}")"""
        cells.append(NotebookCell(cell_type="code", source=load_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Load data",
                dependencies=[0],
                outputs_variables=["df_analysis"],
            )
        )
        idx += 1

        # Preprocessing section
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Data Preprocessing\n\nPreparing data for modeling.",
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="markdown",
                purpose="Preprocessing header",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        # Generate preprocessing code
        preprocess_code = self._generate_preprocessing_code(strategy)
        cells.append(NotebookCell(cell_type="code", source=preprocess_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Preprocessing pipeline",
                dependencies=[2],
                outputs_variables=["X", "y", "X_train", "X_test", "y_train", "y_test"],
            )
        )
        idx += 1

        # Model training section (if models specified)
        if strategy.models_to_train:
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 4.2 Model Training\n\nTraining and comparing models.",
                )
            )
            manifest.append(
                CellManifest(
                    index=idx,
                    cell_type="markdown",
                    purpose="Training header",
                    dependencies=[],
                    outputs_variables=[],
                )
            )
            idx += 1

            training_code = self._generate_training_code(strategy)
            cells.append(NotebookCell(cell_type="code", source=training_code))
            manifest.append(
                CellManifest(
                    index=idx,
                    cell_type="code",
                    purpose="Model training",
                    dependencies=[idx - 2],
                    outputs_variables=["models", "results"],
                )
            )
            idx += 1

            # Evaluation section
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 4.3 Model Evaluation\n\nComparing model performance.",
                )
            )
            manifest.append(
                CellManifest(
                    index=idx,
                    cell_type="markdown",
                    purpose="Evaluation header",
                    dependencies=[],
                    outputs_variables=[],
                )
            )
            idx += 1

            eval_code = self._generate_evaluation_code(strategy)
            cells.append(NotebookCell(cell_type="code", source=eval_code))
            manifest.append(
                CellManifest(
                    index=idx,
                    cell_type="code",
                    purpose="Model evaluation",
                    dependencies=[idx - 2],
                    outputs_variables=["evaluation_results"],
                )
            )
            idx += 1

        # Visualizations section
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.4 Results Visualization\n\nVisual analysis of model performance and insights.",
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="markdown",
                purpose="Visualization header",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        viz_code = self._generate_visualization_code(strategy)
        cells.append(NotebookCell(cell_type="code", source=viz_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Result visualizations",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        # Conclusions section
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.5 Analysis Conclusions\n\nKey findings and recommendations.",
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="markdown",
                purpose="Conclusions header",
                dependencies=[],
                outputs_variables=[],
            )
        )
        idx += 1

        conclusion_code = self._generate_conclusion_code(strategy)
        cells.append(NotebookCell(cell_type="code", source=conclusion_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Generate conclusions",
                dependencies=[],
                outputs_variables=[],
            )
        )

        return cells, manifest

    def _generate_imports(self, strategy: StrategyToCodeGenHandoff) -> str:
        """Generate import statements."""
        imports = [
            "import pandas as pd",
            "import numpy as np",
            "import matplotlib.pyplot as plt",
            "import seaborn as sns",
            "from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV",
            "from sklearn.preprocessing import StandardScaler, LabelEncoder",
            "from sklearn.impute import SimpleImputer",
            "import warnings",
            "",
            "warnings.filterwarnings('ignore')",
            "%matplotlib inline",
        ]

        # Add model imports
        for model in strategy.models_to_train:
            parts = model.import_path.rsplit(".", 1)
            if len(parts) == 2:
                imports.append(f"from {parts[0]} import {parts[1]}")

        # Add metric imports
        if strategy.analysis_type == AnalysisType.CLASSIFICATION:
            imports.append(
                "from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report, roc_auc_score, log_loss"
            )
        elif strategy.analysis_type == AnalysisType.REGRESSION:
            imports.append(
                "from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, mean_absolute_percentage_error"
            )
        elif strategy.analysis_type == AnalysisType.CLUSTERING:
            imports.append(
                "from sklearn.metrics import silhouette_score, calinski_harabasz_score"
            )
            imports.append("from sklearn.cluster import KMeans, DBSCAN")
            imports.append("from scipy.spatial.distance import cdist")
        elif strategy.analysis_type == AnalysisType.CAUSAL:  # Diagnostic
            imports.append("import statsmodels.api as sm")
            imports.append("from scipy.stats import pearsonr, spearmanr")
        elif strategy.analysis_type == AnalysisType.COMPARATIVE:
            imports.append(
                "from scipy.stats import ttest_ind, mannwhitneyu, f_oneway, kruskal, chi2_contingency"
            )
            imports.append("from statsmodels.stats.multicomp import pairwise_tukeyhsd")
        elif strategy.analysis_type == AnalysisType.TIME_SERIES:
            imports.append("from prophet import Prophet")
            imports.append("from statsmodels.tsa.seasonal import seasonal_decompose")
            imports.append(
                "from sklearn.metrics import mean_absolute_error, mean_squared_error"
            )

        return "\n".join(imports)

    def _generate_preprocessing_code(self, strategy: StrategyToCodeGenHandoff) -> str:
        """Generate preprocessing code."""
        lines = ["# Preprocessing Pipeline"]

        target = strategy.target_column
        features = strategy.feature_columns

        if target and features:
            lines.append(
                textwrap.dedent(f"""
                # Separate features and target
                target_col = '{target}'
                feature_cols = {features}

                # Filter to existing columns
                feature_cols = [c for c in feature_cols if c in df_analysis.columns and c != target_col]

                X = df_analysis[feature_cols].copy()
                y = df_analysis[target_col].copy()
            """)
            )

            if strategy.analysis_type == AnalysisType.CLASSIFICATION:
                lines.append(
                    textwrap.dedent("""
                # Encode target for classification
                try:
                    le = LabelEncoder()
                    y = le.fit_transform(y)
                    print(f"Encoded target labels. Classes: {le.classes_}")
                except Exception as e:
                    print(f"Warning: Failed to encode target: {e}")
                """)
                )

            lines.append(
                textwrap.dedent("""
                print(f"Features shape: {X.shape}")
                print(f"Target shape: {y.shape}")
            """)
            )
        else:
            lines.append(
                textwrap.dedent("""
                # Exploratory analysis - use all numeric columns
                numeric_cols = df_analysis.select_dtypes(include=[np.number]).columns.tolist()
                X = df_analysis[numeric_cols].copy()
                y = None

                print(f"Features shape: {X.shape}")
            """)
            )

        # Add preprocessing steps
        for step in sorted(strategy.preprocessing_steps, key=lambda s: s.order):
            if step.step_type == "imputation":
                if step.method == "median":
                    lines.append(
                        textwrap.dedent(f"""
                        # {step.step_name}
                        imputer_cols = [c for c in {step.target_columns} if c in X.columns]
                        if imputer_cols:
                            imputer = SimpleImputer(strategy='median')
                            X[imputer_cols] = imputer.fit_transform(X[imputer_cols])
                            print(f"Imputed {{len(imputer_cols)}} columns with median")
                    """)
                    )
                elif step.method == "mode":
                    lines.append(
                        textwrap.dedent(f"""
                        # {step.step_name}
                        cat_imputer_cols = [c for c in {step.target_columns} if c in X.columns]
                        if cat_imputer_cols:
                            cat_imputer = SimpleImputer(strategy='most_frequent')
                            X[cat_imputer_cols] = cat_imputer.fit_transform(X[cat_imputer_cols])
                            print(f"Imputed {{len(cat_imputer_cols)}} columns with mode")
                    """)
                    )

            elif step.step_type == "encoding":
                lines.append(
                    textwrap.dedent(f"""
                    # {step.step_name}
                    cat_cols = [c for c in {step.target_columns} if c in X.columns]
                    if cat_cols:
                        X = pd.get_dummies(X, columns=cat_cols, drop_first=True)
                        print(f"One-hot encoded {{len(cat_cols)}} categorical columns")
                        print(f"New shape: {{X.shape}}")
                """)
                )

            elif step.step_type == "scaling":
                lines.append(
                    textwrap.dedent(f"""
                    # {step.step_name}
                    scale_cols = [c for c in X.select_dtypes(include=[np.number]).columns if c in X.columns]
                    if scale_cols:
                        scaler = StandardScaler()
                        X[scale_cols] = scaler.fit_transform(X[scale_cols])
                        print(f"Scaled {{len(scale_cols)}} numeric columns")
                """)
                )

        # Train/test split
        if target:
            val_strategy = strategy.validation_strategy
            test_size = 0.2
            if val_strategy and val_strategy.parameters:
                test_size = val_strategy.parameters.get("test_size", 0.2)

            lines.append(
                textwrap.dedent(f"""
                # Train/Test Split
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size={test_size}, random_state=42
                )
                print(f"Training set: {{X_train.shape[0]}} samples")
                print(f"Test set: {{X_test.shape[0]}} samples")
            """)
            )
        else:
            lines.append(
                textwrap.dedent("""
                # No train/test split for exploratory analysis
                X_train, X_test = X, X
                y_train, y_test = None, None
            """)
            )

        return "\n".join(lines)

    def _generate_training_code(self, strategy: StrategyToCodeGenHandoff) -> str:
        """Generate model training code with optional hyperparameter tuning."""
        lines = ["# Model Training", "models = {}", "results = {}"]

        for model in sorted(strategy.models_to_train, key=lambda m: m.priority):
            model_var = model.model_name.lower().replace(" ", "_")
            class_name = model.import_path.split(".")[-1]
            base_params = ", ".join(
                f"{k}={repr(v)}" for k, v in model.hyperparameters.items()
            )

            lines.append(
                textwrap.dedent(f"""
                # Train {model.model_name}
                print("Training {model.model_name}...")
                try:
                    {model_var} = {class_name}({base_params})
            """)
            )

            # Check for tuning configuration
            if model.tuning_config and model.tuning_config.enabled:
                tc = model.tuning_config

                # Construct param grid
                # GridSearchCV accepts dict or list of dicts
                param_grid: dict[str, Any] | list[dict[str, Any]]
                if len(tc.grids) == 1:
                    param_grid = tc.grids[0].param_grid
                else:
                    param_grid = [g.param_grid for g in tc.grids]

                search_cls = (
                    "GridSearchCV" if tc.search_type == "grid" else "RandomizedSearchCV"
                )

                extra_args = ""
                if tc.search_type == "random" and hasattr(tc, "n_iter"):
                    extra_args = f", n_iter={tc.n_iter}"

                # Dynamic arguments based on search type
                search_params = ""
                if tc.search_type == "grid":
                    search_params = "param_grid=param_grid"
                else:
                    search_params = "param_distributions=param_grid"

                # Indent tuning logic to sit inside the try block
                tuning_code = textwrap.dedent(f"""
                    # Hyperparameter Tuning ({search_cls})
                    param_grid = {repr(param_grid)}
                    search = {search_cls}(
                        estimator={model_var}, 
                        {search_params},
                        cv={tc.cv_folds}, 
                        scoring='{tc.scoring_metric}',
                        n_jobs=-1{extra_args}
                    )
                    search.fit(X_train, y_train)
                    
                    # Use best estimator
                    models['{model.model_name}'] = search.best_estimator_
                    print(f"  ✓ Tuning complete. Best params: {{search.best_params_}}")
                    print(f"  ✓ Best CV {tc.scoring_metric}: {{search.best_score_:.4f}}")
                """)
                lines.append(textwrap.indent(tuning_code, "    "))

            else:
                # Standard training (indented)
                training_code = textwrap.dedent(f"""
                    {model_var}.fit(X_train, y_train)
                    models['{model.model_name}'] = {model_var}
                    print(f"  ✓ {model.model_name} trained successfully")
                """)
                lines.append(textwrap.indent(training_code, "    "))

            # Close try/except block
            lines.append(
                textwrap.dedent(f"""
                except Exception as e:
                    print(f"  ✗ {model.model_name} failed: {{e}}")
            """)
            )

        return "\n".join(lines)

    def _generate_evaluation_code(self, strategy: StrategyToCodeGenHandoff) -> str:
        """
        Generate evaluation code with dynamic metric support.

        Handles:
        1. Specific metrics requested by Strategy (e.g. roc_auc, log_loss)
        2. Probability prediction for metrics that need it
        3. Fallback to standard suite if no specific metrics provided
        """
        lines = ["# Model Evaluation", "evaluation_results = {}"]

        # Define metric registry with requirements
        # keys: metric names (as requested by strategy), values: (sklearn_func_name, needs_proba, needs_pos_label)
        metric_registry = {
            "accuracy": ("accuracy_score", False, False),
            "precision": ("precision_score", False, True),
            "recall": ("recall_score", False, True),
            "f1": ("f1_score", False, True),
            "f1_score": ("f1_score", False, True),
            "roc_auc": ("roc_auc_score", True, True),
            "log_loss": ("log_loss", True, False),
            "mse": ("mean_squared_error", False, False),
            "rmse": ("mean_squared_error", False, False),  # handled via sqrt(mse)
            "mae": ("mean_absolute_error", False, False),
            "r2": ("r2_score", False, False),
            "mape": ("mean_absolute_percentage_error", False, False),
        }

        # Check if we need probabilities
        requested_metrics = [m.lower() for m in strategy.evaluation_metrics]
        needs_proba = any(
            metric_registry.get(m, (None, False, False))[1] for m in requested_metrics
        )

        if strategy.analysis_type == AnalysisType.CLASSIFICATION:
            lines.append(
                textwrap.dedent("""
                for name, model in models.items():
                    print(f"\\nEvaluating {name}...")
                    y_pred = model.predict(X_test)
                    
                    results = {}
            """)
            )

            if needs_proba:
                lines.append(
                    textwrap.dedent("""
                    # Get probabilities for advanced metrics
                    y_prob = None
                    if hasattr(model, "predict_proba"):
                        try:
                            # Handle binary vs multiclass
                            if len(np.unique(y_test)) == 2:
                                y_prob = model.predict_proba(X_test)[:, 1]
                            else:
                                y_prob = model.predict_proba(X_test)
                        except Exception as e:
                            print(f"  Warning: Could not predict probabilities: {e}")
                """)
                )
                # Indent this block to match loop context (4 spaces)
                lines[-1] = textwrap.indent(lines[-1], "    ")

            # Dynamic Metric Generation
            metrics_added = False
            if requested_metrics:
                for metric in requested_metrics:
                    if metric in metric_registry:
                        func, requires_proba, requires_pos_label = metric_registry[
                            metric
                        ]

                        if requires_proba:
                            # Generate metric-specific code
                            if metric == "roc_auc":
                                code_chunk = textwrap.dedent("""
                                    if y_prob is not None:
                                        try:
                                            # ROC AUC specific handling
                                            if len(np.unique(y_test)) > 2:
                                                results['roc_auc'] = roc_auc_score(y_test, y_prob, multi_class='ovr')
                                            else:
                                                results['roc_auc'] = roc_auc_score(y_test, y_prob)
                                        except Exception as e:
                                            print(f"  Skipping roc_auc: {e}")
                                 """)
                                lines.append(textwrap.indent(code_chunk, "    "))
                                metrics_added = True
                            elif metric == "log_loss":
                                code_chunk = textwrap.dedent("""
                                    if y_prob is not None:
                                        try:
                                            results['log_loss'] = log_loss(y_test, y_prob)
                                        except Exception:
                                            pass
                                 """)
                                lines.append(textwrap.indent(code_chunk, "    "))
                                metrics_added = True

                        elif requires_pos_label:
                            lines.append(
                                f"    results['{metric}'] = {func}(y_test, y_pred, average='weighted', zero_division=0)"
                            )
                            metrics_added = True
                        elif metric == "rmse":
                            lines.append(
                                f"    results['{metric}'] = np.sqrt(mean_squared_error(y_test, y_pred))"
                            )
                            metrics_added = True
                        else:
                            lines.append(
                                f"    results['{metric}'] = {func}(y_test, y_pred)"
                            )
                            metrics_added = True

            if not metrics_added:
                # Default Classification Metrics
                code_chunk = textwrap.dedent("""
                    results = {
                        'accuracy': accuracy_score(y_test, y_pred),
                        'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
                        'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
                        'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
                    }
                 """)
                lines.append(textwrap.indent(code_chunk, "    "))

            # Common finish
            code_chunk = textwrap.dedent("""
                    evaluation_results[name] = results
                    
                    for metric, value in results.items():
                        print(f"  {metric}: {value:.4f}")
                    
                    print(f"\\nClassification Report for {name}:")
                    print(classification_report(y_test, y_pred))
            """)
            lines.append(textwrap.indent(code_chunk, "    "))

        elif strategy.analysis_type == AnalysisType.REGRESSION:
            lines.append(
                textwrap.dedent("""
                for name, model in models.items():
                    y_pred = model.predict(X_test)
                    
                    results = {}
            """)
            )

            # Dynamic Regression Metrics
            metrics_added = False
            if requested_metrics:
                for metric in requested_metrics:
                    if metric == "rmse":
                        lines.append(
                            "                    results['rmse'] = np.sqrt(mean_squared_error(y_test, y_pred))"
                        )
                        metrics_added = True
                    elif metric in metric_registry:
                        func, _, _ = metric_registry[metric]
                        lines.append(
                            f"                    results['{metric}'] = {func}(y_test, y_pred)"
                        )
                        metrics_added = True

            if not metrics_added:
                # Default Regression Metrics
                lines.append(
                    textwrap.dedent("""
                    mse = mean_squared_error(y_test, y_pred)
                    results = {
                        'mse': mse,
                        'rmse': np.sqrt(mse),
                        'mae': mean_absolute_error(y_test, y_pred),
                        'r2': r2_score(y_test, y_pred)
                    }
                """)
                )

            lines.append(
                textwrap.dedent("""
                    evaluation_results[name] = results
                    
                    print(f"\\n{name}:")
                    for metric, value in results.items():
                        print(f"  {metric}: {value:.4f}")
            """)
            )

        else:
            # Fallback for EXPLORATORY or other types
            lines.append(
                textwrap.dedent("""
                # Fallback evaluation for Exploratory/Unspecified type
                # Determine task type based on y values
                is_classification = False
                if y_test is not None:
                    # Check if target is discrete/categorical or low cardinality numeric
                    if y_test.dtype == 'object' or y_test.dtype.name == 'category' or y_test.nunique() < 20:
                        is_classification = True
                
                for name, model in models.items():
                    y_pred = model.predict(X_test)
                    
                    if is_classification:
                        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, classification_report
                        results = {
                            'accuracy': accuracy_score(y_test, y_pred),
                            'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
                            'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
                            'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
                        }
                        print(f"\\nClassification Report for {name}:")
                        print(classification_report(y_test, y_pred))
                    else:
                        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
                        mse = mean_squared_error(y_test, y_pred)
                        results = {
                            'mse': mse,
                            'rmse': np.sqrt(mse),
                            'mae': mean_absolute_error(y_test, y_pred),
                            'r2': r2_score(y_test, y_pred)
                        }

                    evaluation_results[name] = results
                    
                    print(f"\\n{name}:")
                    for metric, value in results.items():
                        print(f"  {metric}: {value:.4f}")
            """)
            )

        # Results comparison table
        lines.append(
            textwrap.dedent("""
            # Results comparison
            if evaluation_results:
                results_df = pd.DataFrame(evaluation_results).T
                print("\\nModel Comparison:")
                print(results_df.to_string())
        """)
        )

        return "\n".join(lines)

    def _generate_visualization_code(self, strategy: StrategyToCodeGenHandoff) -> str:
        """Generate visualization code."""
        lines = ["# Result Visualizations"]

        if strategy.analysis_type == AnalysisType.CLASSIFICATION:
            lines.append(
                textwrap.dedent("""
                # Confusion Matrix
                if models:
                    fig, axes = plt.subplots(1, len(models), figsize=(6*len(models), 5))
                    if len(models) == 1:
                        axes = [axes]
                    
                    for ax, (name, model) in zip(axes, models.items()):
                        y_pred = model.predict(X_test)
                        cm = confusion_matrix(y_test, y_pred)
                        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
                        ax.set_title(f'{name}\\nConfusion Matrix')
                        ax.set_xlabel('Predicted')
                        ax.set_ylabel('Actual')
                    
                    plt.tight_layout()
                    plt.show()
            """)
            )

        elif strategy.analysis_type == AnalysisType.REGRESSION:
            lines.append(
                textwrap.dedent("""
                # Predicted vs Actual
                if models:
                    fig, axes = plt.subplots(1, len(models), figsize=(6*len(models), 5))
                    if len(models) == 1:
                        axes = [axes]
                    
                    for ax, (name, model) in zip(axes, models.items()):
                        y_pred = model.predict(X_test)
                        ax.scatter(y_test, y_pred, alpha=0.5)
                        ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
                        ax.set_xlabel('Actual')
                        ax.set_ylabel('Predicted')
                        ax.set_title(f'{name}\\nPredicted vs Actual')
                    
                    plt.tight_layout()
                    plt.show()
            """)
            )

        # Feature importance (for tree-based models)
        if strategy.models_to_train:
            lines.append("""
# Feature Importance
for name, model in models.items():
    if hasattr(model, 'feature_importances_'):
        importance = pd.DataFrame({
            'feature': X.columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=True)
        
        plt.figure(figsize=(10, max(6, len(importance) * 0.3)))
        plt.barh(importance['feature'], importance['importance'])
        plt.xlabel('Importance')
        plt.title(f'{name} - Feature Importance')
        plt.tight_layout()
        plt.show()
        break  # Show for first model with feature_importances_
""")

        # Model comparison bar chart
        lines.append("""
# Model Comparison
if evaluation_results:
    results_df = pd.DataFrame(evaluation_results).T
    
    fig, ax = plt.subplots(figsize=(10, 6))
    results_df.plot(kind='bar', ax=ax)
    plt.title('Model Performance Comparison')
    plt.xlabel('Model')
    plt.ylabel('Score')
    plt.legend(loc='best')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
""")

        return "\n".join(lines)

    def _generate_conclusion_code(self, strategy: StrategyToCodeGenHandoff) -> str:
        """Generate conclusion code."""
        return textwrap.dedent(f"""
            # Generate Conclusions
            print("="*60)
            print("ANALYSIS CONCLUSIONS")
            print("="*60)

            # Best model
            if evaluation_results:
                metric_to_use = list(list(evaluation_results.values())[0].keys())[0]
                best_model = max(evaluation_results.items(), key=lambda x: x[1][metric_to_use])
                print(f"\\n1. Best Model: {{best_model[0]}}")
                print(f"   {{metric_to_use}}: {{best_model[1][metric_to_use]:.4f}}")
                
                # Performance summary
                print("\\n2. Performance Summary:")
                for name, metrics in evaluation_results.items():
                    print(f"   - {{name}}: {{', '.join(f'{{k}}={{v:.4f}}' for k, v in list(metrics.items())[:3])}}")

            # Feature insights
            print("\\n3. Key Insights:")
            insights = {strategy.conclusion_points}
            for i, insight in enumerate(insights, 1):
                print(f"   {{i}}. {{insight}}")

            # Limitations
            print("\\n4. Profile Limitations Acknowledged:")
            limitations = {strategy.profile_limitations}
            if limitations:
                for lim in limitations:
                    print(f"   - {{lim}}")
            else:
                print("   No significant limitations identified")

            print("\\n" + "="*60)
            print("Analysis complete!")
        """)

    def build_template_result(
        self, cells: List[NotebookCell], strategy: StrategyToCodeGenHandoff
    ) -> Dict[str, Any]:
        """Build result dictionary for template cells."""
        return {
            "required_imports": ["pandas", "numpy", "sklearn", "matplotlib", "seaborn"],
            "pip_dependencies": ["scikit-learn", "matplotlib", "seaborn"],
            "expected_models": [
                m.model_name.lower().replace(" ", "_") for m in strategy.models_to_train
            ],
            "expected_metrics": strategy.evaluation_metrics,
            "expected_visualizations": 3,
            "confidence": 0.85,
        }

    def _generate_diagnostic_template(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> tuple:
        """Generate Diagnostic/Causal analysis template."""
        cells = []
        manifest = []
        idx = 0

        # Header
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Diagnostic Analysis\n\n**Objective**: {strategy.analysis_objective}",
            )
        )
        manifest.append(CellManifest(index=idx, cell_type="markdown", purpose="Header"))
        idx += 1

        # Imports & Load
        cells.append(
            NotebookCell(
                cell_type="code",
                source=self._generate_imports(strategy)
                + "\n\n# Load Data\ndf_analysis = df.copy()",
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Imports & Load",
                outputs_variables=["df_analysis"],
            )
        )
        idx += 1

        # Preprocessing
        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_preprocessing_code(strategy)
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Preprocessing",
                outputs_variables=["X", "y"],
            )
        )
        idx += 1

        # Correlation Analysis
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Correlation Analysis\nIdentifying relationships between variables.",
            )
        )
        idx += 1
        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent("""
            # Correlation Matrix
            numeric_df = df_analysis.select_dtypes(include=[np.number])
            corr = numeric_df.corr()
            
            plt.figure(figsize=(10, 8))
            sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
            plt.title('Correlation Matrix')
            plt.show()
            
            # Print significant correlations with target if applicable
            if 'target_col' in locals():
                print(f"\\nCorrelations with {target_col}:")
                if target_col in corr.columns:
                    print(corr[target_col].sort_values(ascending=False))
        """),
            )
        )
        manifest.append(
            CellManifest(index=idx, cell_type="code", purpose="Correlation Analysis")
        )
        idx += 1

        # OLS Regression (for drivers)
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.2 Key Drivers Analysis (OLS)\nUsing regression to identify statistically significant factors.",
            )
        )
        idx += 1
        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent("""
            # OLS for Drivers
            try:
                # Ensure X is numeric
                X_numeric = X.select_dtypes(include=[np.number])
                # Add constant
                X_const = sm.add_constant(X_numeric.fillna(0))
                
                if y is not None:
                    # Handle non-numeric y if needed (LabelEncode)
                    y_numeric = y
                    if not pd.api.types.is_numeric_dtype(y):
                         y_numeric = LabelEncoder().fit_transform(y)
                    
                    model = sm.OLS(y_numeric, X_const).fit()
                    print(model.summary())
                    
                    # Store results roughly
                    evaluation_results = {'OLS_R2': {'value': model.rsquared}}
                else:
                    print("No target variable defined for OLS.")
                    evaluation_results = {}
            except Exception as e:
                print(f"OLS Analysis failed: {e}")
                evaluation_results = {}
        """),
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Key Drivers OLS",
                outputs_variables=["model"],
            )
        )
        idx += 1

        # Conclusions
        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_conclusion_code(strategy)
            )
        )
        idx += 1

        return cells, manifest

    def _generate_comparative_template(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> tuple:
        """Generate Comparative analysis template."""
        cells = []
        manifest = []
        idx = 0

        # Header
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Comparative Analysis\n\n**Objective**: {strategy.analysis_objective}",
            )
        )
        idx += 1

        # Imports & Load
        cells.append(
            NotebookCell(
                cell_type="code",
                source=self._generate_imports(strategy)
                + "\n\n# Load Data\ndf_analysis = df.copy()",
            )
        )
        idx += 1

        # Group Analysis
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Group Comparisons\nComparing groups using statistical tests.",
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent(f"""
            # Identify groups
            # Using feature columns or target to define groups
            features = {strategy.feature_columns}
            target = '{strategy.target_column}'
            
            # If target is categorical, compare features across target groups
            if target and target in df_analysis.columns:
                print(f"Comparing Features across Groups defined by: {{target}}")
                groups = df_analysis[target].unique()
                print(f"Groups: {{groups}}")
                
                for feature in features:
                    if feature in df_analysis.columns and pd.api.types.is_numeric_dtype(df_analysis[feature]):
                        print(f"\\nAnalyzing {{feature}} by {{target}}...")
                        
                        # Boxplot
                        plt.figure(figsize=(10, 6))
                        sns.boxplot(x=target, y=feature, data=df_analysis)
                        plt.title(f'{{feature}} by {{target}}')
                        plt.show()
                        
                        # Statistical Test (ANOVA or T-Test)
                        group_data = [df_analysis[df_analysis[target] == g][feature].dropna() for g in groups]
                        if len(groups) == 2:
                             stat, p = ttest_ind(group_data[0], group_data[1])
                             print(f"T-Test: statistic={{stat:.4f}}, p-value={{p:.4f}}")
                        elif len(groups) > 2:
                             stat, p = f_oneway(*group_data)
                             print(f"ANOVA: statistic={{stat:.4f}}, p-value={{p:.4f}}")
            
            # Dummy evaluation results for validator
            evaluation_results = {{'Comparisons': {{'tests_run': len(features)}}}}
        """),
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Group Comparisons",
                outputs_variables=["evaluation_results"],
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_conclusion_code(strategy)
            )
        )

        return cells, manifest

    def _generate_forecasting_template(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> tuple:
        """Generate Forecasting template (Prophet)."""
        cells = []
        manifest = []
        idx = 0

        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Forecasting Analysis\n\n**Objective**: {strategy.analysis_objective}",
            )
        )
        idx += 1

        # Imports & Load
        cells.append(
            NotebookCell(
                cell_type="code",
                source=self._generate_imports(strategy)
                + "\n\n# Load Data\ndf_analysis = df.copy()",
            )
        )
        idx += 1

        # Prepare Data for Prophet
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Prophet Modeling\nForecasting future values.",
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent(f"""
            # Prepare data (Prophet requires 'ds' and 'y')
            # Heuristic: Find datetime column
            date_col = None
            for col in df_analysis.columns:
                if pd.api.types.is_datetime64_any_dtype(df_analysis[col]):
                    date_col = col
                    break
            
            target = '{strategy.target_column}'
            
            if date_col and target:
                print(f"Forecasting {{target}} over {{date_col}}")
                prophet_df = df_analysis[[date_col, target]].rename(columns={{date_col: 'ds', target: 'y'}})
                prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
                prophet_df = prophet_df.sort_values('ds')
                
                # Split
                train_size = int(len(prophet_df) * 0.8)
                train_df = prophet_df.iloc[:train_size]
                test_df = prophet_df.iloc[train_size:]
                
                # Train
                m = Prophet()
                m.fit(train_df)
                
                # Predict
                future = m.make_future_dataframe(periods=len(test_df))
                forecast = m.predict(future)
                
                # Plot
                fig1 = m.plot(forecast)
                plt.title('Prophet Forecast')
                plt.show()
                
                # Components
                fig2 = m.plot_components(forecast)
                plt.show()
                
                # Evaluate
                y_true = test_df['y'].values
                y_pred = forecast.iloc[train_size:]['yhat'].values
                
                mae = mean_absolute_error(y_true, y_pred)
                mse = mean_squared_error(y_true, y_pred)
                
                print(f"MAE: {{mae:.4f}}")
                print(f"RMSE: {{np.sqrt(mse):.4f}}")
                
                evaluation_results = {{'Prophet': {{'MAE': mae, 'RMSE': np.sqrt(mse)}}}}
            else:
                print("Could not identify Date column or Target for forecasting.")
                evaluation_results = {{}}
        """),
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Prophet Modeling",
                outputs_variables=["m", "forecast", "evaluation_results"],
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_conclusion_code(strategy)
            )
        )

        return cells, manifest

    def _generate_segmentation_template(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> tuple:
        """Generate Segmentation/Clustering template."""
        cells = []
        manifest = []
        idx = 0

        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Segmentation Analysis\n\n**Objective**: {strategy.analysis_objective}",
            )
        )
        idx += 1

        # Imports & Load
        cells.append(
            NotebookCell(
                cell_type="code",
                source=self._generate_imports(strategy)
                + "\n\n# Load Data\ndf_analysis = df.copy()",
            )
        )
        idx += 1

        # Preprocessing
        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_preprocessing_code(strategy)
            )
        )
        idx += 1

        # Clustering
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Clustering (K-Means)\nIdentifying distinct segments.",
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent("""
            # Select numeric features for clustering
            X_cluster = X.select_dtypes(include=[np.number])
            
            # Elbow Method
            distortions = []
            K = range(1, 10)
            for k in K:
                kmeanModel = KMeans(n_clusters=k)
                kmeanModel.fit(X_cluster)
                distortions.append(kmeanModel.inertia_)
                
            plt.figure(figsize=(10, 6))
            plt.plot(K, distortions, 'bx-')
            plt.xlabel('k')
            plt.ylabel('Inertia')
            plt.title('Elbow Method showing optimal k')
            plt.show()
            
            # Apply K-Means (defaulting to 3 if optimal not obvious)
            optimal_k = 3
            kmeans = KMeans(n_clusters=optimal_k, random_state=42)
            clusters = kmeans.fit_predict(X_cluster)
            
            df_analysis['Cluster'] = clusters
            
            # Profile Segments
            print("Cluster Profiles:")
            print(df_analysis.groupby('Cluster')[X_cluster.columns].mean())
            
            # Silhouette Score
            score = silhouette_score(X_cluster, clusters)
            print(f"Silhouette Score: {score:.4f}")
            
            evaluation_results = {'KMeans': {'Silhouette': score, 'k': optimal_k}}
        """),
            )
        )
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="Clustering",
                outputs_variables=["kmeans", "df_analysis", "evaluation_results"],
            )
        )
        idx += 1

        # Visualization
        cells.append(
            NotebookCell(
                cell_type="code",
                source=textwrap.dedent("""
            # Pairplot of Clusters
            if len(X_cluster.columns) < 10:
                sns.pairplot(df_analysis, vars=X_cluster.columns, hue='Cluster', palette='viridis')
                plt.show()
        """),
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_conclusion_code(strategy)
            )
        )

        return cells, manifest

    def _generate_dimensionality_template(
        self, strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> tuple:
        """Generate Dimensionality Reduction (PCA) template."""
        cells = []
        manifest = []
        idx = 0

        cells.append(
            NotebookCell(
                cell_type="markdown",
                source=f"# Dimensionality Reduction Analysis\n\n**Objective**: {strategy.analysis_objective}",
            )
        )
        idx += 1

        # Imports & Load
        cells.append(
            NotebookCell(
                cell_type="code",
                source=self._generate_imports(strategy)
                + "\\n\\n# Load Data\\ndf_analysis = df.copy()",
            )
        )
        idx += 1

        # Preprocessing (Standard Scaling is critical)
        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_preprocessing_code(strategy)
            )
        )
        idx += 1

        # PCA
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 4.1 Principal Component Analysis (PCA)\\nReducing dimensionality while retaining variance.",
            )
        )
        idx += 1

        pca_code = textwrap.dedent("""
            from sklearn.decomposition import PCA
            
            # Select numeric features
            X_pca = X.select_dtypes(include=[np.number])
            
            # PCA
            # Determine n_components (using 0.95 explained variance or max 10 components)
            n_comp = min(X_pca.shape[1], 10)
            pca = PCA(n_components=n_comp)
            X_reduced = pca.fit_transform(X_pca)
            
            # Analysis Results
            explained_variance = pca.explained_variance_ratio_
            cumulative_variance = np.cumsum(explained_variance)
            
            print(f"Explained Variance Ratios: {explained_variance}")
            print(f"Cumulative Variance: {cumulative_variance}")
            
            # Scree Plot
            plt.figure(figsize=(10, 6))
            plt.plot(range(1, len(explained_variance) + 1), cumulative_variance, marker='o', linestyle='--')
            plt.title('PCA Explained Variance (Scree Plot)')
            plt.xlabel('Number of Components')
            plt.ylabel('Cumulative Explained Variance')
            plt.grid(True)
            plt.show()
            
            # 2D Projection
            if n_comp >= 2:
                plt.figure(figsize=(10, 8))
                plt.scatter(X_reduced[:, 0], X_reduced[:, 1], alpha=0.5)
                plt.title('PCA: First 2 Components')
                plt.xlabel(f'PC1 ({explained_variance[0]:.2%} var)')
                plt.ylabel(f'PC2 ({explained_variance[1]:.2%} var)')
                plt.grid(True)
                plt.show()
                
            # Component Loadings
            loadings = pd.DataFrame(pca.components_.T, columns=[f'PC{i+1}' for i in range(n_comp)], index=X_pca.columns)
            print("Top Loadings for PC1:")
            print(loadings['PC1'].abs().sort_values(ascending=False).head(5))
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=pca_code))
        manifest.append(
            CellManifest(
                index=idx,
                cell_type="code",
                purpose="PCA Analysis",
                outputs_variables=["pca", "X_reduced", "loadings"],
            )
        )
        idx += 1

        cells.append(
            NotebookCell(
                cell_type="code", source=self._generate_conclusion_code(strategy)
            )
        )

        return cells, manifest
