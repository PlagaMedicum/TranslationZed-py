"""Shared Hypothesis profile helpers for fast/slow randomized lanes."""

from __future__ import annotations

import os

from hypothesis import settings

PROP_PROFILE_ENV = "TZP_PROP_PROFILE"
_FAST = "fast"
_SLOW = "slow"


def prop_profile() -> str:
    """Return normalized randomized profile from environment."""
    raw = str(os.environ.get(PROP_PROFILE_ENV, _FAST)).strip().lower()
    if raw == _SLOW:
        return _SLOW
    return _FAST


def prop_settings(
    *,
    fast_examples: int,
    slow_examples: int | None = None,
) -> settings:
    """Build profile-aware settings for standard property tests."""
    fast = max(1, int(fast_examples))
    slow = max(fast, int(slow_examples if slow_examples is not None else fast * 4))
    examples = slow if prop_profile() == _SLOW else fast
    return settings(max_examples=examples, deadline=None)


def stateful_prop_settings(
    *,
    fast_examples: int = 16,
    slow_examples: int | None = None,
    fast_steps: int = 16,
    slow_steps: int | None = None,
) -> settings:
    """Build profile-aware settings for stateful randomized tests."""
    fast_runs = max(1, int(fast_examples))
    slow_runs = max(fast_runs, int(slow_examples if slow_examples is not None else 64))
    fast_step_budget = max(1, int(fast_steps))
    slow_step_budget = max(
        fast_step_budget,
        int(slow_steps if slow_steps is not None else 64),
    )
    if prop_profile() == _SLOW:
        return settings(
            max_examples=slow_runs,
            stateful_step_count=slow_step_budget,
            deadline=None,
        )
    return settings(
        max_examples=fast_runs,
        stateful_step_count=fast_step_budget,
        deadline=None,
    )
