import pytest
from unittest.mock import MagicMock

from src.agents.phase2.template_generator import TemplateGenerator
from src.models.handoffs import (
    StrategyToCodeGenHandoff, 
    AnalysisType, 
    ModelSpec, 
    PreprocessingStep,
    ValidationStrategy
)
from src.models.state import AnalysisState

class TestTemplateGenerator:
    
    @pytest.fixture
    def generator(self):
        return TemplateGenerator()
        
    @pytest.fixture
    def state(self):
        return MagicMock(spec=AnalysisState)

    @pytest.fixture
    def mock_classification_strategy(self):
        return StrategyToCodeGenHandoff(
            profile_reference="locked_profile_123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Predict churn probability",
            target_column='churn',
            feature_columns=['age', 'tenure', 'monthly_charges'],
            dropped_columns=['customer_id'],
            models_to_train=[
                ModelSpec(
                    model_name='LogisticRegression',
                    import_path='sklearn.linear_model.LogisticRegression',
                    hyperparameters={'max_iter': 1000},
                    rationale='Baseline model',
                    priority=1
                )
            ],
            preprocessing_steps=[
                PreprocessingStep(
                    step_name='StandardScaler',
                    step_type='scaling',
                    target_columns=['age', 'tenure', 'monthly_charges'],
                    rationale='Scale numerical features',
                    order=1
                )
            ],
            validation_strategy=ValidationStrategy(method='train_test_split', parameters={'test_size': 0.2}),
            evaluation_metrics=['accuracy'],
            result_visualizations=[]
        )

    def test_generate_template_cells(self, generator, mock_classification_strategy, state):
        cells, manifest = generator.generate_template_cells(mock_classification_strategy, state)
        
        assert len(cells) > 0
        source = ' '.join(c.source for c in cells)
        assert 'train_test_split' in source or 'StandardScaler' in source
        assert 'LogisticRegression' in source

    def test_diagnostic_template_generation(self, generator, state):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CAUSAL,
            analysis_objective="Find root causes",
            feature_columns=["f1", "f2"],
            target_column="target"
        )
        
        cells, manifest = generator.generate_template_cells(strategy, state)
        source_code = "\n".join([c.source for c in cells])
        assert "statsmodels.api as sm" in source_code
        assert "Correlation Matrix" in source_code

    def test_comparative_template_generation(self, generator, state):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.COMPARATIVE,
            analysis_objective="Compare groups",
            feature_columns=["f1"],
            target_column="group"
        )
        
        cells, manifest = generator.generate_template_cells(strategy, state)
        source_code = "\n".join([c.source for c in cells])
        assert "scipy.stats import ttest_ind" in source_code

    def test_forecasting_template_generation(self, generator, state):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.TIME_SERIES,
            analysis_objective="Forecast sales",
            target_column="sales"
        )
        
        cells, manifest = generator.generate_template_cells(strategy, state)
        source_code = "\n".join([c.source for c in cells])
        assert "from prophet import Prophet" in source_code

    def test_segmentation_template_generation(self, generator, state):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLUSTERING,
            analysis_objective="Segment customers",
            feature_columns=["age", "spend"]
        )
        
        cells, manifest = generator.generate_template_cells(strategy, state)
        source_code = "\n".join([c.source for c in cells])
        assert "KMeans" in source_code
        assert "Elbow Method" in source_code

    def test_generate_preprocessing_code(self, generator, mock_classification_strategy):
        code = generator._generate_preprocessing_code(mock_classification_strategy)
        assert 'StandardScaler' in code
        assert 'train_test_split' in code

        code = generator._generate_training_code(mock_classification_strategy)
        assert 'LogisticRegression' in code
        assert '.fit(' in code

    def test_preprocessing_variations(self, generator):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test prep",
            preprocessing_steps=[
                PreprocessingStep(step_name="Median_Impute", step_type="imputation", target_columns=["age"], method="median", rationale="", order=1),
                PreprocessingStep(step_name="Mode_Impute", step_type="imputation", target_columns=["cat"], method="mode", rationale="", order=2),
                PreprocessingStep(step_name="OHE", step_type="encoding", target_columns=["cat"], rationale="", order=3),
                PreprocessingStep(step_name="Scale", step_type="scaling", target_columns=["age"], rationale="", order=4)
            ]
        )
        code = generator._generate_preprocessing_code(strategy)
        assert "strategy='median'" in code
        assert "strategy='most_frequent'" in code
        assert "pd.get_dummies" in code
        assert "StandardScaler" in code

    def test_training_with_tuning(self, generator):
        from src.models.tuning import TuningConfig, HyperparameterGrid
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test tuning",
            models_to_train=[
                ModelSpec(
                    model_name="RandomForest",
                    import_path="sklearn.ensemble.RandomForestClassifier",
                    hyperparameters={},
                    rationale="",
                    priority=1,
                    tuning_config=TuningConfig(
                        enabled=True,
                        search_type="grid",
                        cv_folds=3,
                        scoring_metric="accuracy",
                        grids=[HyperparameterGrid(algorithm_name="RF", param_grid={"n_estimators": [10, 50]})]
                    )
                ),
                ModelSpec(
                    model_name="SVC",
                    import_path="sklearn.svm.SVC",
                    hyperparameters={},
                    rationale="",
                    priority=2,
                    tuning_config=TuningConfig(
                        enabled=True,
                        search_type="random",
                        cv_folds=3,
                        scoring_metric="accuracy",
                        n_iter=5,
                        grids=[HyperparameterGrid(algorithm_name="SVC", param_grid={"C": [0.1, 1]})]
                    )
                )
            ]
        )
        code = generator._generate_training_code(strategy)
        assert "GridSearchCV" in code
        assert "RandomizedSearchCV" in code
        assert "param_distributions=param_grid" in code

    def test_evaluation_code_variations(self, generator):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test eval",
            evaluation_metrics=["accuracy", "precision", "recall", "f1", "roc_auc", "mse", "rmse", "mae", "r2"]
        )
        code = generator._generate_evaluation_code(strategy)
        assert "accuracy_score" in code
        assert "precision_score" in code
        assert "mean_squared_error" in code
        assert "r2_score" in code

    def test_visualization_code_variations(self, generator):
        from src.models.handoffs import ResultVisualization
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test viz",
            result_visualizations=[],
            models_to_train=[ModelSpec(model_name="RF", import_path="x", rationale="", priority=1)]
        )
        code = generator._generate_visualization_code(strategy)
        assert "confusion_matrix" in code
        
        strategy.analysis_type = AnalysisType.REGRESSION
        code = generator._generate_visualization_code(strategy)
        assert "ax.scatter(y_test, y_pred" in code

    def test_fallback_methods(self, generator, state):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CAUSAL,
            analysis_objective="diagnostic logic",
            target_column="sales",
            feature_columns=["marketing"]
        )
        cells, manifest = generator._generate_diagnostic_template(strategy, state)
        assert any("statsmodels.api as sm" in c.source for c in cells)
        
        strategy.analysis_type = AnalysisType.COMPARATIVE
        strategy.target_column = "group"
        cells, manifest = generator._generate_comparative_template(strategy, state)
        assert any("scipy.stats import ttest_ind" in c.source for c in cells)

        strategy.analysis_type = AnalysisType.TIME_SERIES
        cells, manifest = generator._generate_forecasting_template(strategy, state)
        assert any("Prophet" in c.source for c in cells)

        strategy.analysis_type = AnalysisType.CLUSTERING
        cells, manifest = generator._generate_segmentation_template(strategy, state)
        assert any("KMeans" in c.source for c in cells)
