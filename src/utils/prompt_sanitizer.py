"""
Prompt sanitization utilities to prevent injection attacks.

Sanitizes user-provided text before embedding in LLM prompts to prevent
prompt injection, jailbreaking, and other adversarial inputs.
"""

import re
import unicodedata
from typing import Optional


# Patterns that indicate potential prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\s*(system|assistant|user)\s*>",
    r"IMPORTANT:\s*override",
    r"new\s+instruction",
    r"forget\s+(everything|all|previous)",
]

# Compile patterns for efficiency
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Maximum lengths for different input types
MAX_QUESTION_LENGTH = 2000
MAX_ANALYSIS_TYPE_LENGTH = 200
MAX_CUSTOM_INSTRUCTIONS_LENGTH = 5000


def sanitize_user_input(
    text: str, max_length: int = MAX_QUESTION_LENGTH, field_name: str = "input"
) -> str:
    """
    Sanitize user-provided text before embedding in LLM prompts.

    Args:
        text: The raw user input.
        max_length: Maximum allowed character count.
        field_name: Name of the field (for logging).

    Returns:
        Sanitized text safe for prompt embedding.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode NFC normalization — collapses homoglyphs and combining sequences
    #    so that visually identical but byte-different strings are treated equally.
    sanitized = unicodedata.normalize("NFC", text)

    # 2. Truncate to max length
    sanitized = sanitized[:max_length]

    # 3. Strip null bytes and control characters (except newlines/tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)

    # 4. Normalize whitespace
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)

    # 5. Replace potential injection patterns with a safe marker
    sanitized = _INJECTION_RE.sub("[filtered]", sanitized)

    return sanitized.strip()


def sanitize_question(question: Optional[str]) -> str:
    """Sanitize a user analysis question."""
    if not question:
        return ""
    return sanitize_user_input(question, MAX_QUESTION_LENGTH, "question")


def sanitize_analysis_type(analysis_type: Optional[str]) -> str:
    """Sanitize user-specified analysis type/mode."""
    if not analysis_type:
        return ""
    return sanitize_user_input(analysis_type, MAX_ANALYSIS_TYPE_LENGTH, "analysis_type")


def sanitize_custom_instructions(instructions: Optional[str]) -> str:
    """Sanitize user-provided custom instructions/templates."""
    if not instructions:
        return ""
    return sanitize_user_input(
        instructions, MAX_CUSTOM_INSTRUCTIONS_LENGTH, "custom_instructions"
    )
