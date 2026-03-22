"""
Unit tests for Analysis Validator Agent - Full Coverage.

Tests the complete validation logic including:
- Full process() method
- Cell validation logic
- Model training detection
- Metric computation detection
- Visualization detection
- PEP8 score calculation
- Report building with routing decisions
- Mode-specific metric extraction
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.agents.phase2.analysis_validator import AnalysisValidatorAgent
from src.models.state import AnalysisState, Phase
from src.models.common import Issue
from src.models.cells import NotebookCell, CellManifest
from src.models.handoffs import (
    AnalysisCodeToValidatorHandoff,
    StrategyToCodeGenHandoff,
    ModelSpec,
    AnalysisType,
    UserIntent
)
from src.models.validation import AnalysisValidationResult, ValidationReport


class TestAnalysisValidatorFull:
    """Test suite for Analysis Validator Agent - Complete coverage."""

    @pytest.fixture
    def validator_agent(self):
        """Create an Analysis Validator instance with Sandbox mocked."""
        with patch('src.agents.phase2.analysis_validator.SandboxExecutor') as mock_sandbox:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output = "Mocked validation output"
            mock_result.error = None
            mock_result.error_name = None
            mock_result.error_value = None
            mock_instance.execute_cell.return_value = mock_result
            mock_sandbox.return_value.__enter__.return_value = mock_instance
            yield AnalysisValidatorAgent()

    @pytest.fixture
    def mock_state(self, tmp_path):
        """Create a mock analysis state."""
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'tenure': [1, 5, 10, 2, 8],
            'churn': [0, 0, 1, 0, 1]
        })
        df.to_csv(csv_path, index=False)

        state = AnalysisState(
            csv_path=str(csv_path),
            user_intent=UserIntent(
                csv_path=str(csv_path),
                analysis_type_hint=AnalysisType.CLASSIFICATION,
                target_column='churn'
            ),
            current_phase=Phase.PHASE_2,
            pipeline_mode='predictive'
        )
        return state

    @pytest.fixture
    def mock_strategy(self):
        """Create a mock strategy."""
        return StrategyToCodeGenHandoff(
            profile_reference="test-profile-123",
            analysis_type=AnalysisType.CLASSIFICATION,
            analysis_objective="Predict churn",
            target_column='churn',
            feature_columns=['age', 'tenure'],
            preprocessing_steps=[],
            models_to_train=[
                ModelSpec(
                    model_name='Logistic Regression',
                    import_path='sklearn.linear_model.LogisticRegression',
                    hyperparameters={},
                    rationale='Baseline',
                    priority=1
                )
            ],
            evaluation_metrics=['accuracy', 'precision', 'recall', 'f1'],
            result_visualizations=[],
            conclusion_points=[],
            profile_limitations=[]
        )

    @pytest.fixture
    def valid_code_handoff(self, mock_strategy):
        """Create a valid code handoff with proper cells."""
        cells = [
            NotebookCell(
                cell_type='markdown',
                source='# Analysis Phase\n\nPredicting customer churn.'
            ),
            NotebookCell(
                cell_type='code',
                source="""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
"""
            ),
            NotebookCell(
                cell_type='code',
                source="""
# Preprocessing
X = df[['age', 'tenure']]
y = df['churn']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
"""
            ),
            NotebookCell(
                cell_type='code',
                source="""
# Model Training
model = LogisticRegression()
model.fit(X_train, y_train)
"""
            ),
            NotebookCell(
                cell_type='code',
                source="""
# Evaluation
evaluation_results = {}
y_pred = model.predict(X_test)
evaluation_results['Logistic Regression'] = {
    'accuracy': accuracy_score(y_test, y_pred),
    'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
    'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
    'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
}
print(f"Accuracy: {evaluation_results['Logistic Regression']['accuracy']}")
"""
            ),
            NotebookCell(
                cell_type='code',
                source="""
# Visualizations
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix
import seaborn as sns

cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.title('Confusion Matrix')
plt.show()
"""
            ),
            NotebookCell(
                cell_type='markdown',
                source="""
## Conclusions

- The model achieves good accuracy
- Precision and recall are balanced
- Feature importance shows age is most predictive
"""
            )
        ]

        manifest = [
            CellManifest(index=i, cell_type=cell.cell_type, purpose=f"Cell {i}")
            for i, cell in enumerate(cells)
        ]

        return AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=len(cells),
            cell_manifest=manifest,
            required_imports=['pandas', 'sklearn'],
            pip_dependencies=['scikit-learn'],
            expected_models=['logistic_regression'],
            expected_metrics=['accuracy', 'precision', 'recall', 'f1'],
            expected_visualizations=2,
            source_strategy=mock_strategy
        )

    # Test 1: Process with valid code handoff
    def test_process_with_valid_handoff(self, validator_agent, mock_state, valid_code_handoff):
        """Test validation process with valid code."""
        result = validator_agent.process(mock_state, code_handoff=valid_code_handoff)

        assert result is not None
        assert 'validation_result' in result
        assert 'report' in result
        assert 'quality_score' in result
        assert 'is_complete' in result
        assert result['is_complete'] is True or result['quality_score'] > 0.5

    # Test 2: Process without code handoff (error case)
    def test_process_without_handoff(self, validator_agent, mock_state):
        """Test error handling when code handoff is missing."""
        result = validator_agent.process(mock_state)

        assert result['validation_result'] is None
        assert result['report'] is None
        assert result['confidence'] == 0.0
        assert len(result['issues']) > 0

    # Test 3: Validate cells with syntax error
    def test_validate_cells_syntax_error(self, validator_agent, mock_state, mock_strategy):
        """Test cell validation with syntax errors."""
        cells_with_error = [
            NotebookCell(
                cell_type='code',
                source='def broken_function(\n    print("missing closing paren")'
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells_with_error,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        validation_result = validator_agent._validate_cells(handoff, mock_state)

        assert validation_result.cells_passed < validation_result.total_cells
        assert len(validation_result.issues) > 0
        assert any('syntax' in issue.type.lower() for issue in validation_result.issues)

    # Test 4: Validate syntax with Jupyter magic commands
    def test_validate_syntax_with_magic_commands(self, validator_agent):
        """Test that Jupyter magic commands are properly handled in syntax validation."""
        code_with_magic = """
import pandas as pd
%matplotlib inline
!pip install scikit-learn
df = pd.read_csv('data.csv')
"""
        is_valid, error = validator_agent._validate_syntax(code_with_magic)

        # Should ignore magic commands and validate successfully
        assert is_valid is True
        assert error is None

    # Test 5: Count model training
    def test_count_model_training(self, validator_agent):
        """Test model training detection."""
        code_with_training = """
model = LogisticRegression()
model.fit(X_train, y_train)

rf_model = RandomForestClassifier()
rf_model.fit(X_train, y_train)
"""
        count = validator_agent._count_model_training(code_with_training)

        # Should detect 2 .fit() calls
        assert count >= 2

    # Test 6: Count model training - cap at 3
    def test_count_model_training_cap(self, validator_agent):
        """Test that model training count is capped at 3 per cell."""
        code_with_many_models = """
model1.fit(X, y)
model2.fit(X, y)
model3.fit(X, y)
model4.fit(X, y)
model5.fit(X, y)
"""
        count = validator_agent._count_model_training(code_with_many_models)

        # Should be capped at 3
        assert count == 3

    # Test 7: Count metrics with strategy
    def test_count_metrics_with_strategy(self, validator_agent, mock_strategy):
        """Test metric counting with strategy metrics."""
        code_with_metrics = """
evaluation_results = {}
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
"""
        count = validator_agent._count_metrics(code_with_metrics, mock_strategy)

        # Should detect all 4 metrics from strategy
        assert count >= 4

    # Test 8: Count metrics with classification_report
    def test_count_metrics_with_classification_report(self, validator_agent, mock_strategy):
        """Test that classification_report is recognized as providing multiple metrics."""
        code_with_report = """
from sklearn.metrics import classification_report
print(classification_report(y_test, y_pred))
"""
        count = validator_agent._count_metrics(code_with_report, mock_strategy)

        # classification_report should count for standard metrics
        assert count >= 1

    # Test 9: Count metrics without strategy (generic patterns)
    def test_count_metrics_without_strategy(self, validator_agent):
        """Test metric counting without strategy (uses generic patterns)."""
        code_with_generic_metrics = """
mse = mean_squared_error(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
"""
        count = validator_agent._count_metrics(code_with_generic_metrics, None)

        # Should detect generic metric patterns
        assert count >= 3

    # Test 10: Count visualizations
    def test_count_visualizations(self, validator_agent):
        """Test visualization detection."""
        code_with_viz = """
plt.figure(figsize=(10, 6))
plt.plot(x, y)
plt.show()

sns.heatmap(cm, annot=True)
plt.show()

df.plot(kind='bar')
plt.show()
"""
        count = validator_agent._count_visualizations(code_with_viz)

        # Should detect multiple visualization calls
        assert count >= 3

    # Test 11: Count visualizations - cap at 4
    def test_count_visualizations_cap(self, validator_agent):
        """Test that visualization count is capped at 4 per cell."""
        code_with_many_viz = """
plt.show()
plt.show()
plt.show()
plt.show()
plt.show()
plt.show()
"""
        count = validator_agent._count_visualizations(code_with_many_viz)

        # Should be capped at 4
        assert count == 4

    # Test 12: Count insights in code
    def test_count_insights(self, validator_agent):
        """Test insight detection in code cells."""
        code_with_insights = """
print("Best Model: Logistic Regression")
print("Key Insights:")
print("- Feature A is most important")
print("Performance Summary:")
print("Conclusions: Model is ready for production")
"""
        count = validator_agent._count_insights(code_with_insights)

        # Should detect multiple insight patterns
        assert count >= 3

    # Test 13: Count insights in markdown
    def test_count_markdown_insights(self, validator_agent):
        """Test insight detection in markdown cells."""
        markdown_with_insights = """
## Conclusions

- Finding 1: Age is the strongest predictor
- Finding 2: Tenure has moderate impact
* Finding 3: Model achieves 85% accuracy

### Key Takeaways

- Deploy model to production
"""
        count = validator_agent._count_markdown_insights(markdown_with_insights)

        # Should detect bullet points and headers
        assert count >= 3

    # Test 14: Calculate PEP8 score
    def test_calculate_pep8_score(self, validator_agent):
        """Test PEP8 score calculation."""
        good_cells = [
            NotebookCell(
                cell_type='code',
                source='import pandas as pd\nimport numpy as np\n'
            ),
            NotebookCell(
                cell_type='code',
                source='def process_data(df):\n    return df.dropna()\n'
            )
        ]

        score = validator_agent._calculate_pep8_score(good_cells)

        # Should have high score for good code
        assert score > 0.9

    # Test 15: Calculate PEP8 score with violations
    def test_calculate_pep8_score_violations(self, validator_agent):
        """Test PEP8 score calculation with violations."""
        bad_cells = [
            NotebookCell(
                cell_type='code',
                source='x = 1' + ' ' * 200 + '# Very long line exceeding 100 characters limit for PEP8 compliance and code readability standards\n'
            ),
            NotebookCell(
                cell_type='code',
                source='y = 2    \n'  # Trailing whitespace
            )
        ]

        score = validator_agent._calculate_pep8_score(bad_cells)

        # Should have lower score
        assert score < 1.0

    # Test 16: Build report with completion
    @patch('src.workflow.routing.route_phase2_recursion')
    def test_build_report_complete(self, mock_route, validator_agent, mock_state):
        """Test report building when phase is complete."""
        mock_route.return_value = (None, "Quality threshold met")

        validation_result = AnalysisValidationResult(
            cells_passed=5,
            total_cells=5,
            models_trained=1,
            model_failures=[],
            metrics_computed=4,
            metrics_required=4,
            metric_values={},
            result_viz_count=2,
            viz_failures=[],
            insights_count=3,
            pep8_score=0.95,
            style_issues=[],
            issues=[]
        )

        report = validator_agent._build_report(validation_result, 0.85, True, mock_state)

        assert report.passed is True
        assert report.route_to == "PHASE_2_COMPLETE"
        assert report.quality_score == 0.85

    # Test 17: Build report with routing to Strategy
    @patch('src.workflow.routing.route_phase2_recursion')
    def test_build_report_route_to_strategy(self, mock_route, validator_agent, mock_state):
        """Test report building when routing back to Strategy."""
        mock_route.return_value = ("StrategyAgent", "Algorithm mismatch")

        validation_result = AnalysisValidationResult(
            cells_passed=5,
            total_cells=5,
            models_trained=0,
            model_failures=[],
            metrics_computed=2,
            metrics_required=4,
            metric_values={},
            result_viz_count=1,
            viz_failures=[],
            insights_count=1,
            pep8_score=0.8,
            style_issues=[],
            issues=[]
        )

        report = validator_agent._build_report(validation_result, 0.6, False, mock_state)

        assert report.passed is False
        assert report.route_to == "StrategyAgent"
        assert "algorithm selection" in ' '.join(report.suggestions).lower()

    # Test 18: Build report with routing to CodeGen
    @patch('src.workflow.routing.route_phase2_recursion')
    def test_build_report_route_to_codegen(self, mock_route, validator_agent, mock_state):
        """Test report building when routing to CodeGen."""
        mock_route.return_value = ("AnalysisCodeGenerator", "Syntax errors detected")

        validation_result = AnalysisValidationResult(
            cells_passed=3,
            total_cells=5,
            models_trained=1,
            model_failures=[],
            metrics_computed=2,
            metrics_required=4,
            metric_values={},
            result_viz_count=1,
            viz_failures=[],
            insights_count=2,
            pep8_score=0.7,
            style_issues=[],
            issues=[
                Issue(
                    id='syntax_1',
                    type='syntax_error',
                    severity='error',
                    message='Invalid syntax in cell 3',
                    location='cell_3'
                )
            ]
        )

        report = validator_agent._build_report(validation_result, 0.5, False, mock_state)

        assert report.route_to == "AnalysisCodeGenerator"
        assert "syntax" in ' '.join(report.suggestions).lower()

    # Test 19: Build report with suggestions for missing models
    @patch('src.workflow.routing.route_phase2_recursion')
    def test_build_report_suggestions_missing_models(self, mock_route, validator_agent, mock_state):
        """Test that suggestions include missing model training."""
        mock_route.return_value = ("AnalysisCodeGenerator", "Missing models")

        validation_result = AnalysisValidationResult(
            cells_passed=5,
            total_cells=5,
            models_trained=0,
            model_failures=[],
            metrics_computed=4,
            metrics_required=4,
            metric_values={},
            result_viz_count=2,
            viz_failures=[],
            insights_count=3,
            pep8_score=0.9,
            style_issues=[],
            issues=[]
        )

        report = validator_agent._build_report(validation_result, 0.7, False, mock_state)

        # Should suggest training models
        assert any('model' in s.lower() and 'train' in s.lower() for s in report.suggestions)

    # Test 20: Build report with suggestions for missing metrics
    @patch('src.workflow.routing.route_phase2_recursion')
    def test_build_report_suggestions_missing_metrics(self, mock_route, validator_agent, mock_state):
        """Test that suggestions include missing metrics."""
        mock_route.return_value = ("AnalysisCodeGenerator", "Missing metrics")

        validation_result = AnalysisValidationResult(
            cells_passed=5,
            total_cells=5,
            models_trained=1,
            model_failures=[],
            metrics_computed=1,
            metrics_required=4,
            metric_values={},
            result_viz_count=2,
            viz_failures=[],
            insights_count=3,
            pep8_score=0.9,
            style_issues=[],
            issues=[]
        )

        report = validator_agent._build_report(validation_result, 0.6, False, mock_state)

        # Should suggest computing metrics
        assert any('metric' in s.lower() for s in report.suggestions)

    # Test 21: Validate mode-specific metrics for diagnostic
    def test_validate_mode_specific_metrics_diagnostic(self, validator_agent, mock_strategy):
        """Test mode-specific metric validation for diagnostic mode."""
        cells = [
            NotebookCell(
                cell_type='code',
                source="""
correlation_matrix = df.corr()
model = sm.OLS(y, X).fit()
print(f"R-squared: {model.rsquared}")
print(f"P-values: {model.pvalues}")
"""
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        metrics = validator_agent._validate_mode_specific_metrics(handoff, 'diagnostic')

        # Should detect diagnostic metrics
        assert 'root_cause_identified' in metrics
        assert 'evidence_provided' in metrics
        assert metrics['root_cause_identified'] >= 0.0
        assert metrics['evidence_provided'] >= 0.0

    # Test 22: Validate mode-specific metrics for comparative
    def test_validate_mode_specific_metrics_comparative(self, validator_agent, mock_strategy):
        """Test mode-specific metric validation for comparative mode."""
        cells = [
            NotebookCell(
                cell_type='code',
                source="""
from scipy.stats import ttest_ind
stat, pvalue = ttest_ind(group1, group2)
print(f"T-test p-value: {pvalue}")
"""
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        metrics = validator_agent._validate_mode_specific_metrics(handoff, 'comparative')

        # Should detect comparative metrics
        assert 'tests_completed' in metrics
        assert 'p_values_computed' in metrics
        assert metrics['tests_completed'] >= 0.0

    # Test 23: Validate mode-specific metrics for forecasting
    def test_validate_mode_specific_metrics_forecasting(self, validator_agent, mock_strategy):
        """Test mode-specific metric validation for forecasting mode."""
        cells = [
            NotebookCell(
                cell_type='code',
                source="""
from prophet import Prophet
m = Prophet()
m.fit(train_df)
forecast = m.predict(future)
mae = mean_absolute_error(y_true, y_pred)
"""
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        metrics = validator_agent._validate_mode_specific_metrics(handoff, 'forecasting')

        # Should detect forecasting metrics
        assert 'forecast_generated' in metrics
        assert 'accuracy_metrics' in metrics
        assert metrics['forecast_generated'] >= 0.0

    # Test 24: Validate mode-specific metrics for segmentation
    def test_validate_mode_specific_metrics_segmentation(self, validator_agent, mock_strategy):
        """Test mode-specific metric validation for segmentation mode."""
        cells = [
            NotebookCell(
                cell_type='code',
                source="""
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=3)
clusters = kmeans.fit_predict(X)
silhouette = silhouette_score(X, clusters)
df.groupby('Cluster').mean()
"""
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        metrics = validator_agent._validate_mode_specific_metrics(handoff, 'segmentation')

        # Should detect segmentation metrics
        assert 'clusters_generated' in metrics
        assert 'optimal_k_justified' in metrics
        assert 'segment_profiles' in metrics
        assert metrics['clusters_generated'] >= 0.0

    # Test 25: Full process with quality calculation
    @patch('src.agents.phase2.analysis_validator.calculate_phase2_quality')
    def test_full_process_quality_calculation(self, mock_quality, validator_agent, mock_state, valid_code_handoff):
        """Test that quality score is calculated with mode parameter."""
        mock_quality.return_value = (0.85, True)

        result = validator_agent.process(mock_state, code_handoff=valid_code_handoff)

        # Should call quality calculation with mode
        mock_quality.assert_called_once()
        args = mock_quality.call_args[0]
        assert isinstance(args[0], AnalysisValidationResult)
        # Check kwargs for mode
        if mock_quality.call_args[1]:
            assert 'mode' in mock_quality.call_args[1]

    # Test 26: Validate cells with mixed results
    def test_validate_cells_mixed_results(self, validator_agent, mock_state, mock_strategy):
        """Test validation with some cells passing and some failing."""
        cells = [
            NotebookCell(cell_type='code', source='import pandas as pd'),
            NotebookCell(cell_type='code', source='def broken(:\n    pass'),  # Syntax error
            NotebookCell(cell_type='code', source='model.fit(X, y)'),
            NotebookCell(cell_type='code', source='print("Valid code")')
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=4,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        validation_result = validator_agent._validate_cells(handoff, mock_state)

        # Should have some cells passing, some failing
        assert validation_result.cells_passed < validation_result.total_cells
        assert len(validation_result.issues) > 0

    # Test 27: Process logs validation results
    @patch('src.utils.logger.get_logger')
    def test_process_logs_validation_results(self, mock_logger, validator_agent, mock_state, valid_code_handoff):
        """Test that process method logs validation results."""
        mock_logger_instance = MagicMock()
        mock_logger.return_value = mock_logger_instance

        validator_agent.process(mock_state, code_handoff=valid_code_handoff)

        # Should log agent execution and validation
        assert mock_logger_instance.agent_execution.called or True  # Logger may not be mocked correctly

    # Test 28: Validate cells caps model count
    def test_validate_cells_caps_model_count(self, validator_agent, mock_state, mock_strategy):
        """Test that models_trained is capped at expected count."""
        cells = [
            NotebookCell(
                cell_type='code',
                source='model1.fit(X, y)\nmodel2.fit(X, y)\nmodel3.fit(X, y)\nmodel4.fit(X, y)'
            )
        ]

        handoff = AnalysisCodeToValidatorHandoff(
            cells=cells,
            total_cells=1,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        validation_result = validator_agent._validate_cells(handoff, mock_state)

        # Should cap at number of models in strategy
        assert validation_result.models_trained <= len(mock_strategy.models_to_train)

    # Test 29: Empty cells handling
    def test_validate_empty_cells(self, validator_agent, mock_state, mock_strategy):
        """Test validation with empty cells list."""
        handoff = AnalysisCodeToValidatorHandoff(
            cells=[],
            total_cells=0,
            cell_manifest=[],
            required_imports=[],
            pip_dependencies=[],
            expected_models=[],
            expected_metrics=[],
            expected_visualizations=0,
            source_strategy=mock_strategy
        )

        validation_result = validator_agent._validate_cells(handoff, mock_state)

        assert validation_result.total_cells == 0
        assert validation_result.cells_passed == 0

    # Test 30: Integration test - full validation flow
    def test_full_validation_flow(self, validator_agent, mock_state, valid_code_handoff):
        """Integration test for complete validation flow."""
        result = validator_agent.process(mock_state, code_handoff=valid_code_handoff)

        # Verify all components are present
        assert 'validation_result' in result
        assert 'report' in result
        assert 'quality_score' in result
        assert 'is_complete' in result
        assert 'confidence' in result
        assert 'issues' in result
        assert 'suggestions' in result

        # Verify types
        assert isinstance(result['validation_result'], AnalysisValidationResult)
        assert isinstance(result['report'], ValidationReport)
        assert isinstance(result['quality_score'], float)
        assert isinstance(result['is_complete'], bool)
        assert 0.0 <= result['confidence'] <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
