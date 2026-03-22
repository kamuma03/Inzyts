from unittest.mock import MagicMock
from src.agents.phase2.prompt_builder import PromptBuilder
from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType, ModelSpec, ValidationStrategy
from src.models.state import AnalysisState

class TestPromptBuilder:
    def test_build_generation_prompt(self):
        strategy = StrategyToCodeGenHandoff(
            profile_reference="ref",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Objective",
            target_column="target",
            feature_columns=["f1"],
            models_to_train=[ModelSpec(model_name="LogReg", import_path="sklearn.lm.LR", hyperparameters={}, priority=1, rationale="rationale")],
            validation_strategy=ValidationStrategy(method="train_test_split"),
            evaluation_metrics=["accuracy"],
            result_visualizations=[]
        )
        state = MagicMock(spec=AnalysisState)
        state.csv_path = "data.csv"
        state.analysis_validation_reports = []
        
        prompt = PromptBuilder.build_generation_prompt(strategy, state)
        
        assert "ANALYSIS TYPE: classification" in prompt
        assert "OBJECTIVE: Objective" in prompt
        assert "SAFETY NET" in prompt
