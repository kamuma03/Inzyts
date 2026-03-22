
import pytest
from src.services.mode_detector import ModeDetector
from src.models.handoffs import PipelineMode

class TestModeDetector:
    """Test suite for ModeDetector service."""

    @pytest.fixture
    def detector(self):
        return ModeDetector()

    def test_determine_mode_explicit(self, detector):
        """Test explicit mode arguments."""
        # Predictive
        mode, method = detector.determine_mode("predictive", None, None)
        assert mode == PipelineMode.PREDICTIVE
        assert method == "explicit"
        
        # Aliases
        mode, method = detector.determine_mode("pred", None, None)
        assert mode == PipelineMode.PREDICTIVE
        
        mode, method = detector.determine_mode("exp", None, None)
        assert mode == PipelineMode.EXPLORATORY
        
        mode, method = detector.determine_mode("diag", None, None)
        assert mode == PipelineMode.DIAGNOSTIC

        mode, method = detector.determine_mode("forecast", None, None)
        assert mode == PipelineMode.FORECASTING

    def test_determine_mode_target_column(self, detector):
        """Test target column implies predictive."""
        mode, method = detector.determine_mode(None, "churn", None)
        assert mode == PipelineMode.PREDICTIVE
        assert method == "target_column"

    def test_determine_mode_inference(self, detector):
        """Test keyword inference from user question."""
        # Forecasting
        mode, method = detector.determine_mode(None, None, "Forecast sales for next year")
        assert mode == PipelineMode.FORECASTING
        assert method == "inferred_keyword"

        # Diagnostic
        mode, method = detector.determine_mode(None, None, "Why did sales drop?")
        assert mode == PipelineMode.DIAGNOSTIC
        assert method == "inferred_keyword"
        
        # Comparative
        mode, method = detector.determine_mode(None, None, "Compare group A and B")
        assert mode == PipelineMode.COMPARATIVE
        assert method == "inferred_keyword"

        # Segmentation
        mode, method = detector.determine_mode(None, None, "Segment customers")
        assert mode == PipelineMode.SEGMENTATION
        assert method == "inferred_keyword"

    def test_determine_mode_default(self, detector):
        """Test default to exploratory."""
        mode, method = detector.determine_mode(None, None, "Just analyze this")
        assert mode == PipelineMode.EXPLORATORY
        assert method == "default"

    def test_case_insensitive_aliases(self, detector):
        """Test that aliases are case insensitive."""
        mode, _ = detector.determine_mode("PRED", None, None)
        assert mode == PipelineMode.PREDICTIVE
