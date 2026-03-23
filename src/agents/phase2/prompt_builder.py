from src.models.handoffs import StrategyToCodeGenHandoff, AnalysisType
from src.models.state import AnalysisState
from src.prompts import (
    FORECASTING_CODEGEN_PROMPT,
    COMPARATIVE_CODEGEN_PROMPT,
    DIAGNOSTIC_CODEGEN_PROMPT,
    SEGMENTATION_CODEGEN_PROMPT,
    DIMENSIONALITY_CODEGEN_PROMPT,
)


class PromptBuilder:
    """Helper for building LLM prompts for code generation."""

    @staticmethod
    def build_generation_prompt(
        strategy: StrategyToCodeGenHandoff, state: AnalysisState
    ) -> str:
        """Build prompt for LLM code generation."""

        # Select mode-specific instruction
        mode_instruction = ""
        stype = strategy.analysis_type
        if stype == AnalysisType.TIME_SERIES:
            mode_instruction = FORECASTING_CODEGEN_PROMPT
        elif stype == AnalysisType.COMPARATIVE:
            mode_instruction = COMPARATIVE_CODEGEN_PROMPT
        elif stype == AnalysisType.CAUSAL:  # Diagnostic
            mode_instruction = DIAGNOSTIC_CODEGEN_PROMPT
        elif stype == AnalysisType.CLUSTERING:
            mode_instruction = SEGMENTATION_CODEGEN_PROMPT
        elif stype == AnalysisType.DIMENSIONALITY:
            mode_instruction = DIMENSIONALITY_CODEGEN_PROMPT

        preprocessing_lines = []
        for step in strategy.preprocessing_steps:
            cols = str(step.target_columns)
            # Force include Gender if Geography is present to handle common omission
            if "Geography" in cols and "Gender" not in cols:
                cols = cols.replace("]", ", 'Gender']")
            # Concise format: keep actionable info, drop verbose rationale
            # to reduce token usage without losing accuracy.
            params_str = f", params={step.parameters}" if step.parameters else ""
            preprocessing_lines.append(
                f"  {step.order}. {step.step_type.upper()}: "
                f"{step.method} on {cols}{params_str}"
            )
        preprocessing = "\n".join(preprocessing_lines)

        # Append Safety Net to Preprocessing Prompt to ensure it's seen as a step
        preprocessing += """
   99. SAFETY NET: Execute `X = X.select_dtypes(include=[np.number])` AFTER encoding and BEFORE splitting.
"""

        models = "\n".join(
            [
                f"  - {m.model_name} ({m.import_path})"
                + (f", hyperparams={m.hyperparameters}" if m.hyperparameters else "")
                for m in strategy.models_to_train
            ]
        )

        # Helper to identify encoding needs
        onehot_cols = []
        for step in strategy.preprocessing_steps:
            # Robust check for one-hot encoding variations (onehot, one_hot, dummy)
            method_norm = str(step.method).lower().replace("_", "").replace("-", "")
            if step.step_type == "encoding" and method_norm in [
                "onehot",
                "getdummies",
                "dummy",
                "onehotencoding",
            ]:
                onehot_cols.extend(step.target_columns)

        onehot_instruction = ""
        if onehot_cols:
            onehot_instruction = """
CRITICAL: You must use the DYNAMIC PREPROCESSING LOGIC defined in your system prompt to encode categorical variables.
Do NOT rely on the list above alone. Check `X` dynamically:
- If nunique > 20: Drop
- If nunique <= 20: One-Hot Encode
"""

        # FORCE SAFETY NET IN ALL CASES
        safety_net = """
        CRITICAL SAFETY STEP:
        After One-Hot Encoding and BEFORE splitting, you MUST execute this exact line:
        `X = X.select_dtypes(include=[np.number])`
        This ensures any remaining high-cardinality string columns (like Surname) that were not encoded are dropped, preventing training errors.
        """

        # INCORPORATE FEEDBACK (Fix for infinite recursion)
        feedback_section = ""
        if state.analysis_validation_reports:
            latest_report = state.analysis_validation_reports[-1]

            # Use pre-formatted feedback when available (ValidationReport property)
            from src.models.validation import ValidationReport

            if isinstance(latest_report, ValidationReport):
                feedback_text = latest_report.formatted_feedback
            elif isinstance(latest_report, dict):
                issues_list = latest_report.get("issues", [])
                suggestions_list = latest_report.get("suggestions", [])
                parts = [
                    f"- Issue: {i.message if hasattr(i, 'message') else str(i)}"
                    for i in issues_list
                ]
                parts.extend([f"- Suggestion: {s}" for s in suggestions_list])
                feedback_text = "\n".join(parts)
            elif hasattr(latest_report, "issues"):
                # Generic object fallback (e.g. duck-typed report)
                issues_list = latest_report.issues
                suggestions_list = getattr(latest_report, "suggestions", [])
                parts = [
                    f"- Issue: {i.message if hasattr(i, 'message') else str(i)}"
                    for i in issues_list
                ]
                parts.extend([f"- Suggestion: {s}" for s in suggestions_list])
                feedback_text = "\n".join(parts)
            else:
                feedback_text = ""

            if feedback_text:
                feedback_section = f"""
IMPORTANT: The previous attempt to generate this code FAILED validation.
Refine the code to address these specific issues:
{feedback_text}
"""
                if (
                    "metrics" in feedback_text.lower()
                    or "compute required evaluation metrics" in feedback_text.lower()
                ):
                    feedback_section += "\nCRITICAL: You previously failed to compute specific metrics. You MUST write Python code to calculate accuracy, F1, etc. using sklearn and store them in `evaluation_results`."

        return f"""{mode_instruction}

Generate analysis notebook cells based on this strategy:
{safety_net}

{feedback_section}

ANALYSIS TYPE: {strategy.analysis_type.value}
OBJECTIVE: {strategy.analysis_objective}
TARGET COLUMN: {strategy.target_column or "None (exploratory)"}
FEATURE COLUMNS: {strategy.feature_columns}

PREPROCESSING PIPELINE:
{preprocessing if preprocessing else "  No preprocessing required"}

MODELS TO TRAIN:
{models if models else "  No models (exploratory analysis)"}

EVALUATION METRICS: {strategy.evaluation_metrics}
VALIDATION: {strategy.validation_strategy.method if strategy.validation_strategy else "train_test_split"}

VISUALIZATIONS REQUIRED: {[v.viz_type for v in strategy.result_visualizations]}

CONCLUSION POINTS: {strategy.conclusion_points}

CSV PATH: {state.csv_path}

Generate complete analysis code that:
1. Use existing `df` variable (DO NOT reload CSV). Create a copy: `df_analysis = df.copy()`.
2. Implements all preprocessing steps
3. Trains all specified models
4. Evaluates with all metrics AND POPULATES the `evaluation_results` dictionary.
   CRITICAL: You MUST write the code to iterate over models, predict on X_test, compute metrics (accuracy, precision, recall, f1, etc), and store them in `evaluation_results[model_name]`.
   Do NOT leave this section empty.
5. Creates all visualizations
6. Writes conclusions

{onehot_instruction}

Return as JSON with the specified format."""
