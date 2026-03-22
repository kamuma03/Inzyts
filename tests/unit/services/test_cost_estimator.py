from unittest.mock import patch, MagicMock
from src.server.services.cost_estimator import CostEstimator, _lookup_pricing, PRICING_TABLE, _DEFAULT_PRICING


class TestCostEstimator:

    def test_default_model_selection(self):
        """Test that CostEstimator picks up default model from settings if not provided."""
        with patch("src.server.services.cost_estimator.settings") as mock_settings:
            mock_settings.llm.default_provider = "openai"
            mock_settings.llm.openai_model = "gpt-4-turbo"

            estimator = CostEstimator()
            assert estimator.model == "gpt-4-turbo"

    def test_explicit_model_selection(self):
        """Test that explicit model argument overrides defaults."""
        estimator = CostEstimator(model="claude-3-opus")
        assert estimator.model == "claude-3-opus"

    @patch("src.server.services.cost_estimator.Path.exists")
    @patch("src.server.services.cost_estimator.pd.read_csv")
    def test_pricing_lookup_exact_match(self, mock_read_csv, mock_exists):
        """Test pricing lookup for known models using mocked token estimation."""
        mock_exists.return_value = True

        estimator = CostEstimator(model="gpt-4o")
        estimator.encoding = MagicMock()
        estimator.estimate_csv_tokens = MagicMock(return_value=1000)

        # exploratory: prompt = data * 3 + 5000 = 8000, completion = 4000
        cost = estimator.estimate_job_cost("dummy.csv", mode="exploratory")

        # gpt-4o pricing from PRICING_TABLE: input $2.50/1M, output $10.0/1M
        expected_input = (8000 / 1_000_000) * 2.50
        expected_output = (4000 / 1_000_000) * 10.0

        assert cost["estimated_cost_usd"] == round(expected_input + expected_output, 4)
        assert cost["input_tokens"] == 8000
        assert cost["output_tokens"] == 4000

    def test_pricing_lookup_fuzzy_match(self):
        """Test pricing lookup for versioned models (longest-prefix match)."""
        estimator = CostEstimator(model="claude-3-sonnet-20240229")
        estimator.estimate_csv_tokens = MagicMock(return_value=0)

        # predictive: prompt = 0 * 5 + 8000 = 8000, completion = 8000
        cost = estimator.estimate_job_cost("dummy.csv", mode="predictive")

        # claude-3-sonnet: input $3.0, output $15.0
        expected_input = (8000 / 1_000_000) * 3.0
        expected_output = (8000 / 1_000_000) * 15.0

        assert cost["estimated_cost_usd"] == round(expected_input + expected_output, 4)

    def test_fallback_pricing(self):
        """Test fallback to default pricing for unknown models."""
        estimator = CostEstimator(model="unknown-super-model")
        estimator.estimate_csv_tokens = MagicMock(return_value=0)

        cost = estimator.estimate_job_cost("dummy.csv", mode="predictive")
        # predictive: 8000 input, 8000 output

        # _DEFAULT_PRICING: input $2.50, output $10.0
        expected_input = (8000 / 1_000_000) * _DEFAULT_PRICING["input"]
        expected_output = (8000 / 1_000_000) * _DEFAULT_PRICING["output"]

        assert cost["estimated_cost_usd"] == round(expected_input + expected_output, 4)

    @patch("src.server.services.cost_estimator.pd.read_csv")
    @patch("src.server.services.cost_estimator.Path.exists")
    @patch("builtins.open")
    def test_estimate_csv_tokens(self, mock_open, mock_exists, mock_read_csv):
        """Test token estimation logic using mocks."""
        mock_exists.return_value = True

        mock_df = MagicMock()
        mock_df.to_string.return_value = "col1,col2\n1,2"
        mock_read_csv.return_value = mock_df

        # 100 data rows + 1 header = 101 lines total
        mock_file = MagicMock()
        mock_file.__enter__.return_value = range(101)
        mock_open.return_value = mock_file

        estimator = CostEstimator(model="gpt-4")
        estimator.encoding = MagicMock()
        estimator.encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens

        # avg_tokens_per_row = 5 / 5 = 1.0
        # total_estimate = 1.0 * 100 + 1000 = 1100
        tokens = estimator.estimate_csv_tokens("dummy.csv")
        assert tokens == 1100

    def test_pricing_lookup_function(self):
        """Test the _lookup_pricing helper directly."""
        # Exact prefix match
        price = _lookup_pricing("gpt-4o")
        assert price["input"] == 2.50
        assert price["output"] == 10.0

        # Longest prefix match
        price = _lookup_pricing("claude-sonnet-4-6-20250101")
        assert price["input"] == 3.0

        # Unknown model returns default
        price = _lookup_pricing("totally-unknown-model")
        assert price == _DEFAULT_PRICING

    def test_all_modes(self):
        """Test cost estimation for all analysis modes."""
        estimator = CostEstimator(model="gpt-4o")
        estimator.estimate_csv_tokens = MagicMock(return_value=500)

        modes = ["exploratory", "predictive", "forecasting", "diagnostic", "comparative",
                 "segmentation", "dimensionality", "unknown_mode"]
        for mode in modes:
            cost = estimator.estimate_job_cost("dummy.csv", mode=mode)
            assert "estimated_cost_usd" in cost
            assert "input_tokens" in cost
            assert "output_tokens" in cost
            assert cost["estimated_cost_usd"] >= 0
