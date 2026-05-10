"""Helpers for parsing LLM textual output."""

from __future__ import annotations

import re

# Matches ```lang ... ``` blocks. ``lang`` is optional; the first capture
# group is the inner content with surrounding whitespace stripped.
_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\s*(.*?)\s*```", re.DOTALL)


def extract_fenced(text: str) -> str:
    """Return the contents of the first ```lang ... ``` block in ``text``.

    Falls back to the trimmed input when no fenced block is present, so
    callers can use the result regardless of whether the LLM wrapped its
    output in a Markdown code fence.
    """
    if not text:
        return ""
    cleaned = text.strip()
    match = _FENCE_RE.search(cleaned)
    return match.group(1).strip() if match else cleaned


def extract_json_bounded(text: str) -> str:
    """Slice from the first ``{`` or ``[`` to the matching last ``}``/``]``.

    Used by the LLM provider when an LLM emits prose around its JSON
    payload without using fences. Returns the trimmed input if no JSON
    boundary characters are found.
    """
    if not text:
        return ""
    cleaned = text.strip()
    start = next((i for i, c in enumerate(cleaned) if c in "{["), -1)
    end = next((i for i in range(len(cleaned) - 1, -1, -1) if cleaned[i] in "}]"), -1)
    if start != -1 and end != -1 and start <= end:
        return cleaned[start : end + 1]
    return cleaned
