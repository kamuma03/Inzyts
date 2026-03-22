
import unittest
from src.models.handoffs import StrategyToCodeGenHandoff, ModelSpec, AnalysisType
from src.models.tuning import HyperparameterGrid, SearchType, TuningConfig

from unittest.mock import patch, MagicMock

class TestTuningCodegen(unittest.TestCase):
    def setUp(self):
        # Mock logger to avoid PermissionError
        self.logger_patcher = patch('src.utils.logger.get_logger')
        self.mock_logger = self.logger_patcher.start()
        self.mock_logger.return_value = MagicMock()
        
        # Import here to ensure patch is active when module-level get_logger() runs
        from src.agents.phase2.analysis_codegen import AnalysisCodeGeneratorAgent
        self.agent = AnalysisCodeGeneratorAgent()

    def tearDown(self):
        self.logger_patcher.stop()

    def test_grid_search_generation(self):
        """Test that GridSearchCV is generated correctly."""
        
        tuning_config = TuningConfig(
            enabled=True,
            search_type=SearchType.GRID,
            cv_folds=5,
            scoring_metric="accuracy",
            grids=[
                HyperparameterGrid(
                    algorithm_name="RandomForestClassifier",
                    param_grid={"n_estimators": [100, 200]}
                )
            ]
        )
        
        model = ModelSpec(
            model_name="Random Forest",
            import_path="sklearn.ensemble.RandomForestClassifier",
            hyperparameters={"random_state": 42},
            tuning_config=tuning_config,
            rationale="Test model",
            priority=1
        )
        
        strategy = StrategyToCodeGenHandoff(
            profile_reference="test",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test tuning",
            models_to_train=[model]
        )
        
        code = self.agent.template_generator._generate_training_code(strategy)
        
        self.assertIn("GridSearchCV", code)
        self.assertIn("param_grid = {'n_estimators': [100, 200]}", code)
        self.assertIn("scoring='accuracy'", code)
        self.assertIn("results = {}", code)

    def test_random_search_generation(self):
        """Test that RandomizedSearchCV is generated correctly."""
        
        tuning_config = TuningConfig(
            enabled=True,
            search_type=SearchType.RANDOM,
            cv_folds=3,
            scoring_metric="f1",
            n_iter=20,
            grids=[
                HyperparameterGrid(
                    algorithm_name="GradientBoostingClassifier",
                    param_grid={"learning_rate": [0.01, 0.1]}
                )
            ]
        )
        
        model = ModelSpec(
            model_name="GBM",
            import_path="sklearn.ensemble.GradientBoostingClassifier",
            hyperparameters={},
            tuning_config=tuning_config,
            rationale="Test model",
            priority=1
        )
        
        strategy = StrategyToCodeGenHandoff(
            profile_reference="test",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Test tuning",
            models_to_train=[model]
        )
        
        code = self.agent.template_generator._generate_training_code(strategy)
        
        self.assertIn("RandomizedSearchCV", code)
        self.assertIn("n_iter=20", code)
        self.assertIn("scoring='f1'", code)

if __name__ == '__main__':
    unittest.main()
