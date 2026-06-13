"""Shared test factories.

`make_analysis_state` returns a ``make_analysis_state()`` whose every
declared field is pre-populated with the *real* AnalysisState default. This
fixes a sharp edge that caused a class of silent test breakages:

``make_analysis_state()`` only allows attributes that exist on the
*class*. Pydantic model fields live in ``model_fields`` (they're instance
attributes, not class attributes), so accessing e.g. ``state.csv_path`` on a
bare spec'd mock raises ``AttributeError`` unless that test happened to set it.
When production code changes which field it reads (e.g. extensions moving from
``csv_data`` to ``csv_path``), only the mocks that didn't set the new field
break — and they break inconsistently across files, so a partial local test run
misses them.

Pre-seeding every field with its real default means any field the code reads
returns a sane value instead of raising, so a contract change surfaces
consistently (or not at all) rather than in a scattered subset. Tests still
override whatever they need, including attaching mock sub-objects
(``state.profile_lock = MagicMock(spec=ProfileLock)``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.models.state import AnalysisState


def make_analysis_state(**overrides: Any) -> MagicMock:
    """Build a spec'd AnalysisState mock with all fields at their real defaults.

    Pass ``**overrides`` to set specific fields (data values or mock
    sub-objects). Any field not overridden returns its real AnalysisState
    default rather than raising AttributeError.
    """
    defaults = AnalysisState()
    state = MagicMock(spec=AnalysisState)
    for name in AnalysisState.model_fields:
        setattr(state, name, getattr(defaults, name))
    for key, value in overrides.items():
        setattr(state, key, value)
    return state
