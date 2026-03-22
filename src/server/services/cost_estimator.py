import tiktoken
import pandas as pd
from pathlib import Path
from typing import Dict
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger()


# Pricing per 1M tokens (USD). Updated 2025-03.
# Keys are prefix-matched against the configured model name (longest match wins).
PRICING_TABLE = {
    # ── Anthropic Claude 4.x ──────────────────────────────────────────────
    "claude-opus-4":        {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4":      {"input":  3.0,  "output": 15.0},
    "claude-haiku-4":       {"input":  0.80, "output":  4.0},
    # ── Anthropic Claude 3.x (legacy) ────────────────────────────────────
    "claude-3-opus":        {"input": 15.0,  "output": 75.0},
    "claude-3-5-sonnet":    {"input":  3.0,  "output": 15.0},
    "claude-3-sonnet":      {"input":  3.0,  "output": 15.0},
    "claude-3-haiku":       {"input":  0.25, "output":  1.25},
    # ── OpenAI ────────────────────────────────────────────────────────────
    "gpt-4o":               {"input":  2.50, "output": 10.0},
    "gpt-4o-mini":          {"input":  0.15, "output":  0.60},
    "gpt-4-turbo":          {"input": 10.0,  "output": 30.0},
    "gpt-4":                {"input": 30.0,  "output": 60.0},
    "gpt-3.5-turbo":        {"input":  0.50, "output":  1.50},
    # ── Google Gemini ─────────────────────────────────────────────────────
    "gemini-2.0-flash":     {"input":  0.10, "output":  0.40},
    "gemini-1.5-pro":       {"input":  3.50, "output": 10.50},
    "gemini-1.5-flash":     {"input":  0.35, "output":  1.05},
    # ── Ollama (local) ────────────────────────────────────────────────────
    "ollama":               {"input":  0.0,  "output":  0.0},
}

# Default fallback when the model cannot be matched (gpt-4o rates as a middle-ground).
_DEFAULT_PRICING = {"input": 2.50, "output": 10.0}


def _lookup_pricing(model: str) -> dict:
    """Return the pricing entry for *model* using longest-prefix matching.

    Longest-prefix matching ensures that ``claude-sonnet-4-6`` correctly
    resolves to the ``claude-sonnet-4`` entry rather than a shorter,
    unrelated key.
    """
    model_lower = model.lower()
    best_key = ""
    best_match = None
    for key, pricing in PRICING_TABLE.items():
        if key in model_lower and len(key) > len(best_key):
            best_key = key
            best_match = pricing
    return best_match or _DEFAULT_PRICING


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Return the USD cost for the given token counts and model."""
    price = _lookup_pricing(model)
    return (prompt_tokens / 1_000_000) * price["input"] + (
        completion_tokens / 1_000_000
    ) * price["output"]


class CostEstimator:
    def __init__(self, model: str | None = None):
        # Default to configured provider/model if not specified
        if not model:
            provider = settings.llm.default_provider
            if provider == "anthropic":
                model = settings.llm.anthropic_model
            elif provider == "openai":
                model = settings.llm.openai_model
            elif provider == "gemini":
                model = settings.llm.gemini_model
            elif provider == "ollama":
                model = settings.llm.ollama_model
            else:
                model = "gpt-4"  # fallback

        self.model = model
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def estimate_csv_tokens(self, csv_path: str) -> int:
        """Estimate tokens for a CSV file by sampling."""
        if not Path(csv_path).exists():
            return 0

        try:
            # Read header and first 5 rows to estimate
            df = pd.read_csv(csv_path, nrows=5)
            text_representation = df.to_string()
            token_count = len(self.encoding.encode(text_representation))

            # Extrapolate
            with open(csv_path) as f:
                total_rows = sum(1 for _ in f) - 1
            if total_rows <= 0:
                return 0

            avg_tokens_per_row = token_count / 5
            total_estimate = (
                avg_tokens_per_row * total_rows
            ) + 1000  # Buffer for schema
            return int(total_estimate)
        except Exception as e:
            logger.warning(f"Token estimation failed for {csv_path}: {e}")
            return 0

    def estimate_job_cost(self, csv_path: str, mode: str) -> Dict[str, float]:
        """Return estimated input/output tokens and cost in USD."""
        data_tokens = self.estimate_csv_tokens(csv_path)

        # Heuristics based on mode
        if mode == "exploratory":
            # ~3 iterations, each sending sample data + receiving analysis
            prompt_tokens = data_tokens * 3 + 5000
            completion_tokens = 4000
        elif mode in ("predictive", "segmentation", "dimensionality"):
            # Iterative code generation — heavier prompts and verbose output
            prompt_tokens = data_tokens * 5 + 8000
            completion_tokens = 8000
        elif mode in ("forecasting", "diagnostic", "comparative"):
            # Extension + strategy phase: deeper context, more code output
            prompt_tokens = data_tokens * 6 + 10000
            completion_tokens = 10000
        else:
            # Unknown mode — fall back to a conservative estimate
            prompt_tokens = data_tokens * 4 + 6000
            completion_tokens = 6000

        price_conf = _lookup_pricing(self.model)

        cost_input = (prompt_tokens / 1_000_000) * price_conf["input"]
        cost_output = (completion_tokens / 1_000_000) * price_conf["output"]

        return {
            "estimated_cost_usd": round(cost_input + cost_output, 4),
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        }
