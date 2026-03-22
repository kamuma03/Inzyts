"""
Shared validation utilities for Phase 1 and Phase 2 validators.

Extracted from profile_validator.py and analysis_validator.py to
eliminate code duplication across validation agents.
"""

import ast
from typing import List, Optional, Tuple


def validate_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Python syntax, ignoring Jupyter magic commands.

    Args:
        code: Python source code string (may contain Jupyter magics).

    Returns:
        (is_valid, error_message) tuple. error_message is None when valid.
    """
    # Remove Jupyter magic commands for parsing
    lines = code.split("\n")
    clean_lines = [
        line
        for line in lines
        if not line.strip().startswith("%") and not line.strip().startswith("!")
    ]
    clean_code = "\n".join(clean_lines)

    try:
        ast.parse(clean_code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def count_visualizations(code: str, patterns: List[str], cap: int = 5) -> int:
    """
    Count visualization calls in code based on provided patterns.

    Args:
        code: Python source code string.
        patterns: List of string patterns to search for (e.g. "plt.show()", "sns.").
        cap: Maximum count to return per cell. Defaults to 5.

    Returns:
        Number of distinct visualization patterns found, capped at *cap*.
    """
    count = 0
    for pattern in patterns:
        count += code.count(pattern)
    return min(count, cap)


def lint_line(line: str, i: int, lines: List[str]) -> float:
    """
    Check a single line for PEP8 issues and return a penalty score.

    Checks performed:
    - PEP8-001: Line length (max 100 chars) - weight: 1.0
    - PEP8-002: Trailing whitespace - weight: 0.1
    - PEP8-003: Indentation consistency (4 spaces) - weight: 0.5
    - PEP8-004: Operator spacing - weight: 0.2
    - PEP8-005: Function definition spacing - weight: 0.3
    - PEP8-006: Import organization - weight: 0.2

    Args:
        line: The source line to check.
        i: Zero-based line index within the cell.
        lines: All lines in the cell (needed for context checks).

    Returns:
        Cumulative penalty score for the line.
    """
    penalty = 0.0

    # PEP8-001: Line length (max 100 chars)
    if len(line) > 100:
        penalty += 1.0

    # PEP8-002: Trailing whitespace
    if line.rstrip() != line:
        penalty += 0.1

    # PEP8-003: Indentation consistency (must be multiple of 4)
    if line and line[0] == " ":
        leading_spaces = len(line) - len(line.lstrip(" "))
        if leading_spaces % 4 != 0:
            penalty += 0.5

    # PEP8-004: Operator spacing
    stripped = line.strip()
    if "=" in stripped and not any(
        op in stripped for op in ["==", "!=", "<=", ">="]
    ):
        parts = stripped.split("=")
        if len(parts) == 2:
            if parts[0] and parts[0][-1] not in " \t":
                penalty += 0.2
            if parts[1] and parts[1][0] not in " \t":
                penalty += 0.2

    # PEP8-005: Function definition spacing
    if line.strip().startswith("def "):
        if i > 2:
            prev_lines = lines[i - 2 : i]
            if not all(not l.strip() for l in prev_lines):
                penalty += 0.3

    # PEP8-006: Import organization
    if line.strip().startswith("import ") or line.strip().startswith("from "):
        if i > 10:  # Lenient check
            penalty += 0.2

    return penalty


def calculate_pep8_score(cells, lint_fn=None) -> float:
    """
    Calculate comprehensive PEP8 compliance score across notebook cells.

    Uses the full lint_line() checks by default. Callers may supply a
    custom *lint_fn* to override the per-line scoring logic.

    Args:
        cells: Sequence of NotebookCell objects (must have .cell_type and .source).
        lint_fn: Optional callable(line, index, all_lines) -> float penalty.
                 Defaults to :func:`lint_line`.

    Returns:
        Float score in [0.0, 1.0] where 1.0 means perfect compliance.
    """
    if lint_fn is None:
        lint_fn = lint_line

    total_issues = 0.0
    total_lines = 0

    for cell in cells:
        if cell.cell_type == "code":
            lines = cell.source.split("\n")
            total_lines += len(lines)

            for i, line in enumerate(lines):
                total_issues += lint_fn(line, i, lines)

    if total_lines == 0:
        return 1.0

    # Normalize score
    return max(0.0, 1.0 - (total_issues / max(total_lines, 1)))
