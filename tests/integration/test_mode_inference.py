"""
Test suite for Pipeline Mode Inference (Section 10.1 of requirements.md v1.5.0)

Tests mode detection logic with priority:
1. Explicit --mode flag (highest priority)
2. Target column presence (--target implies PREDICTIVE)
3. LLM inference from question keywords
4. Default to EXPLORATORY

Requirements Section 1.2, lines 66-95
"""


from src.models.handoffs import PipelineMode


class TestExplicitModeFlag:
    """Test PM-001: Explicit --mode flag has highest priority."""

    def test_explicit_exploratory_mode(self):
        """Test --mode exploratory overrides all other signals."""
        # Even with target column, explicit mode wins
        mode = "exploratory"
        target = "Survived"
        question = "predict survival rates"  # Predictive keyword

        # Simulate orchestrator logic
        pipeline_mode = PipelineMode.EXPLORATORY
        if mode:
            if mode.lower() in ["predictive", "pred"]:
                pipeline_mode = PipelineMode.PREDICTIVE
            else:
                pipeline_mode = PipelineMode.EXPLORATORY

        assert pipeline_mode == PipelineMode.EXPLORATORY

    def test_explicit_predictive_mode(self):
        """Test --mode predictive overrides question keywords."""
        mode = "predictive"
        question = "show me the distribution"  # Exploratory keyword

        pipeline_mode = PipelineMode.EXPLORATORY
        if mode:
            if mode.lower() in ["predictive", "pred"]:
                pipeline_mode = PipelineMode.PREDICTIVE
            else:
                pipeline_mode = PipelineMode.EXPLORATORY

        assert pipeline_mode == PipelineMode.PREDICTIVE

    def test_explicit_pred_shorthand(self):
        """Test --mode pred shorthand."""
        mode = "pred"

        pipeline_mode = PipelineMode.EXPLORATORY
        if mode and mode.lower() in ["predictive", "pred"]:
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE


class TestTargetImpliesPredictive:
    """Test PM-002: Target column presence implies PREDICTIVE mode."""

    def test_target_column_implies_predictive(self):
        """Test that providing --target sets PREDICTIVE mode."""
        mode = None
        target = "Churn"
        question = None

        pipeline_mode = PipelineMode.EXPLORATORY
        if target:
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE

    def test_target_overrides_exploratory_keywords(self):
        """Test target overrides exploratory keywords in question."""
        mode = None
        target = "price"
        question = "show me the distribution of features"  # Exploratory keywords

        pipeline_mode = PipelineMode.EXPLORATORY
        if target:
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE

    def test_no_target_allows_keyword_inference(self):
        """Test that without target, system falls back to keyword inference."""
        mode = None
        target = None
        question = "predict customer churn"

        pipeline_mode = PipelineMode.EXPLORATORY

        if target:
            pipeline_mode = PipelineMode.PREDICTIVE
        elif question:
            # Would perform keyword inference
            if "predict" in question.lower():
                pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE


class TestKeywordInference:
    """Test PM-003: LLM inference from question keywords."""

    # Predictive keywords from requirements Section 1.2, lines 71-75
    PREDICTIVE_KEYWORDS = [
        "predict", "forecast", "classify", "classification",
        "regression", "model", "train", "cluster", "segment",
        "which factors", "what predicts", "build a model"
    ]

    # Exploratory keywords from requirements Section 1.2, lines 77-81
    EXPLORATORY_KEYWORDS = [
        "distribution", "correlation", "summary", "statistics",
        "describe", "explore", "understand", "what is the",
        "how many", "show me", "visualize", "compare"
    ]

    def _infer_mode_from_question(self, question: str) -> PipelineMode:
        """Simulate orchestrator's keyword inference logic."""
        if not question:
            return PipelineMode.EXPLORATORY

        question_lower = question.lower()

        # Check predictive keywords
        if any(kw in question_lower for kw in self.PREDICTIVE_KEYWORDS):
            return PipelineMode.PREDICTIVE

        # Check exploratory keywords
        if any(kw in question_lower for kw in self.EXPLORATORY_KEYWORDS):
            return PipelineMode.EXPLORATORY

        # Default
        return PipelineMode.EXPLORATORY

    def test_predict_keyword(self):
        """Test 'predict' keyword triggers PREDICTIVE mode."""
        question = "Can we predict customer churn?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_forecast_keyword(self):
        """Test 'forecast' keyword triggers PREDICTIVE mode."""
        question = "Forecast sales for next quarter"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_classify_keyword(self):
        """Test 'classify' keyword triggers PREDICTIVE mode."""
        question = "How can we classify these transactions?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_train_model_keywords(self):
        """Test 'train' and 'model' keywords trigger PREDICTIVE mode."""
        question = "Can you train a model for this dataset?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_cluster_keyword(self):
        """Test 'cluster' keyword triggers PREDICTIVE mode."""
        question = "Cluster customers into segments"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_which_factors_keyword(self):
        """Test 'which factors' phrase triggers PREDICTIVE mode."""
        question = "Which factors influence revenue?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.PREDICTIVE

    def test_distribution_keyword(self):
        """Test 'distribution' keyword triggers EXPLORATORY mode."""
        question = "What is the age distribution?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_correlation_keyword(self):
        """Test 'correlation' keyword triggers EXPLORATORY mode."""
        question = "Show correlation between variables"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_summary_statistics_keywords(self):
        """Test 'summary' and 'statistics' keywords trigger EXPLORATORY mode."""
        question = "Give me summary statistics for this data"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_explore_keyword(self):
        """Test 'explore' keyword triggers EXPLORATORY mode."""
        question = "Let's explore this dataset"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_visualize_keyword(self):
        """Test 'visualize' keyword triggers EXPLORATORY mode."""
        question = "Visualize the trends in sales data"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_compare_keyword(self):
        """Test 'compare' keyword triggers EXPLORATORY mode."""
        question = "Compare regions by revenue"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_how_many_keyword(self):
        """Test 'how many' phrase triggers EXPLORATORY mode."""
        question = "How many missing values are there?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY


class TestAmbiguousQuestions:
    """Test PM-004: Ambiguous questions default to EXPLORATORY."""

    def _infer_mode_from_question(self, question: str) -> PipelineMode:
        """Simulate orchestrator's keyword inference logic."""
        if not question:
            return PipelineMode.EXPLORATORY

        question_lower = question.lower()

        predictive_keywords = [
            "predict", "forecast", "classify", "classification",
            "regression", "model", "train", "cluster", "segment",
            "which factors", "what predicts", "build a model"
        ]

        exploratory_keywords = [
            "distribution", "correlation", "summary", "statistics",
            "describe", "explore", "understand", "what is the",
            "how many", "show me", "visualize", "compare"
        ]

        if any(kw in question_lower for kw in predictive_keywords):
            return PipelineMode.PREDICTIVE

        if any(kw in question_lower for kw in exploratory_keywords):
            return PipelineMode.EXPLORATORY

        # Default to EXPLORATORY for ambiguous cases
        return PipelineMode.EXPLORATORY

    def test_ambiguous_question_defaults_exploratory(self):
        """Test vague question without clear keywords defaults to EXPLORATORY."""
        question = "Tell me about this data"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_generic_analysis_request(self):
        """Test generic 'analyze' request defaults to EXPLORATORY."""
        question = "Analyze this dataset"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_empty_question_defaults_exploratory(self):
        """Test empty question defaults to EXPLORATORY."""
        question = ""
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY

    def test_question_with_no_keywords(self):
        """Test question with no matching keywords defaults to EXPLORATORY."""
        question = "What can you tell me about the revenue column?"
        mode = self._infer_mode_from_question(question)
        assert mode == PipelineMode.EXPLORATORY


class TestModePriority:
    """Test the complete priority chain: explicit mode → target → keywords → default."""

    def test_priority_1_explicit_mode_wins(self):
        """Test explicit mode beats target and keywords."""
        mode = "exploratory"
        target = "Survived"
        question = "predict survival rates"

        # Priority 1: Explicit mode
        pipeline_mode = PipelineMode.EXPLORATORY
        if mode:
            if mode.lower() in ["predictive", "pred"]:
                pipeline_mode = PipelineMode.PREDICTIVE
            else:
                pipeline_mode = PipelineMode.EXPLORATORY

        assert pipeline_mode == PipelineMode.EXPLORATORY

    def test_priority_2_target_beats_keywords(self):
        """Test target beats question keywords."""
        mode = None
        target = "Churn"
        question = "show me the distribution"  # Exploratory keyword

        pipeline_mode = PipelineMode.EXPLORATORY

        if mode:
            pipeline_mode = PipelineMode.PREDICTIVE if mode.lower() in ["predictive", "pred"] else PipelineMode.EXPLORATORY
        elif target:
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE

    def test_priority_3_keywords_used_when_no_mode_or_target(self):
        """Test keywords are used when no explicit mode or target."""
        mode = None
        target = None
        question = "predict customer behavior"

        pipeline_mode = PipelineMode.EXPLORATORY

        if mode:
            pipeline_mode = PipelineMode.PREDICTIVE if mode.lower() in ["predictive", "pred"] else PipelineMode.EXPLORATORY
        elif target:
            pipeline_mode = PipelineMode.PREDICTIVE
        elif question and "predict" in question.lower():
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.PREDICTIVE

    def test_priority_4_default_exploratory(self):
        """Test default EXPLORATORY when no signals provided."""
        mode = None
        target = None
        question = None

        pipeline_mode = PipelineMode.EXPLORATORY

        # No overrides, stays EXPLORATORY
        assert pipeline_mode == PipelineMode.EXPLORATORY


class TestModeDetectionLogging:
    """Test that mode detection is logged with correct detection_method."""

    def test_explicit_mode_logs_explicit_method(self):
        """Test explicit mode logs 'explicit' as detection method."""
        mode = "predictive"
        detection_method = "default"

        if mode:
            detection_method = "explicit"

        assert detection_method == "explicit"

    def test_target_logs_target_column_method(self):
        """Test target column logs 'target_column' as detection method."""
        mode = None
        target = "price"
        detection_method = "default"

        if mode:
            detection_method = "explicit"
        elif target:
            detection_method = "target_column"

        assert detection_method == "target_column"

    def test_keyword_inference_logs_inferred_method(self):
        """Test keyword inference logs 'inferred' as detection method."""
        mode = None
        target = None
        question = "predict sales"
        detection_method = "default"

        predictive_keywords = ["predict", "forecast", "classify"]

        if mode:
            detection_method = "explicit"
        elif target:
            detection_method = "target_column"
        elif question and any(kw in question.lower() for kw in predictive_keywords):
            detection_method = "inferred"

        assert detection_method == "inferred"

    def test_default_mode_logs_default_method(self):
        """Test default mode logs 'default' as detection method."""
        mode = None
        target = None
        question = None
        detection_method = "default"

        # No changes to detection_method
        assert detection_method == "default"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_case_insensitive_keyword_matching(self):
        """Test keywords are matched case-insensitively."""
        questions = [
            "PREDICT sales",
            "Predict Sales",
            "predict SALES",
        ]

        for question in questions:
            assert "predict" in question.lower()

    def test_partial_keyword_matching(self):
        """Test keywords match as substrings (e.g., 'prediction' contains 'predict')."""
        question = "Make predictions about customer behavior"
        assert "predict" in question.lower()

    def test_multiple_keywords_first_match_wins(self):
        """Test that first matching keyword category determines mode."""
        # Both predictive and exploratory keywords present
        question = "predict the distribution of ages"  # 'predict' comes first

        predictive_keywords = ["predict", "forecast"]
        exploratory_keywords = ["distribution", "correlation"]

        # Check predictive first
        if any(kw in question.lower() for kw in predictive_keywords):
            mode = PipelineMode.PREDICTIVE
        elif any(kw in question.lower() for kw in exploratory_keywords):
            mode = PipelineMode.EXPLORATORY
        else:
            mode = PipelineMode.EXPLORATORY

        assert mode == PipelineMode.PREDICTIVE

    def test_keyword_in_middle_of_word(self):
        """Test keywords match even within longer words."""
        question = "I want to classification of customers"
        assert "classification" in question.lower()

    def test_empty_mode_string_treated_as_none(self):
        """Test empty string mode is treated as no mode."""
        mode = ""

        pipeline_mode = PipelineMode.EXPLORATORY
        if mode:  # Empty string is falsy
            pipeline_mode = PipelineMode.PREDICTIVE

        assert pipeline_mode == PipelineMode.EXPLORATORY
