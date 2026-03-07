"""Unit tests for TM query scoring determinism guards."""

from __future__ import annotations

from typing import Any, cast

import pytest

from translationzed_py.core.tm_query_contracts import (
    TMExplainability,
    TMExplainabilityBand,
    TMExplainabilityTieBreak,
    TMScoredCandidate,
)
from translationzed_py.core.tm_query_scoring import (
    sort_scored_candidates,
    validate_sorted_explainability_order,
)


def _candidate(
    *,
    source_norm: str,
    score: int,
    raw_score: int,
    token_count_delta: int,
    origin: str = "project",
    updated_at: int = 1,
    tie_break_origin_priority: int | None = None,
    tie_break_updated_at: int | None = None,
    explainability_raw_score: int | None = None,
) -> TMScoredCandidate:
    row: dict[str, Any] = {
        "source_norm": source_norm,
        "origin": origin,
        "updated_at": updated_at,
    }
    origin_priority = 0 if origin == "project" else 1
    explainability = TMExplainability(
        score=score,
        raw_score=(
            raw_score if explainability_raw_score is None else explainability_raw_score
        ),
        ratio=0.8,
        overlap=0.5,
        exact_overlap=0.5,
        token_bonus=3,
        composed_phrase=False,
        long_multi_triggered=False,
        band=TMExplainabilityBand(
            min_base=1,
            max_base=32,
            min_effective=1,
            max_effective=48,
        ),
        oversized_guard_applied=False,
        oversized_guard_passed=None,
        cap_reason="none",
        tie_break=TMExplainabilityTieBreak(
            token_count_delta=token_count_delta,
            origin_priority=(
                origin_priority
                if tie_break_origin_priority is None
                else tie_break_origin_priority
            ),
            updated_at=(
                updated_at if tie_break_updated_at is None else tie_break_updated_at
            ),
        ),
        decision_notes=(),
    )
    return TMScoredCandidate(
        row=cast(Any, row),
        score=score,
        raw_score=raw_score,
        token_count_delta=token_count_delta,
        explainability=explainability,
    )


def test_validate_sorted_explainability_order_accepts_sorted_candidates() -> None:
    """Aligned explainability payload should pass after legacy sort."""
    scored = [
        _candidate(
            source_norm="drop all tokens",
            score=94,
            raw_score=90,
            token_count_delta=0,
            origin="project",
            updated_at=10,
        ),
        _candidate(
            source_norm="drop one token",
            score=99,
            raw_score=98,
            token_count_delta=1,
            origin="project",
            updated_at=20,
        ),
        _candidate(
            source_norm="drop one",
            score=90,
            raw_score=88,
            token_count_delta=1,
            origin="import",
            updated_at=30,
        ),
    ]
    ordered = sort_scored_candidates(
        scored=scored,
        query_token_count=2,
        query_len=len("drop all"),
        project_origin="project",
    )
    validate_sorted_explainability_order(
        scored=ordered,
        query_token_count=2,
        query_len=len("drop all"),
        project_origin="project",
    )
    assert [item.score for item in ordered] == [94, 99, 90]


def test_validate_sorted_explainability_order_rejects_raw_score_mismatch() -> None:
    """Guard should reject raw-score drift between score and explainability fields."""
    scored = [
        _candidate(
            source_norm="drop all",
            score=99,
            raw_score=98,
            explainability_raw_score=97,
            token_count_delta=0,
        )
    ]
    with pytest.raises(ValueError, match="raw_score mismatch"):
        validate_sorted_explainability_order(
            scored=scored,
            query_token_count=1,
            query_len=len("drop all"),
            project_origin="project",
        )


def test_validate_sorted_explainability_order_rejects_sort_key_mismatch() -> None:
    """Guard should reject tie-break values that diverge from ranking key fields."""
    scored = [
        _candidate(
            source_norm="drop all",
            score=99,
            raw_score=98,
            token_count_delta=0,
            tie_break_origin_priority=1,
        )
    ]
    with pytest.raises(ValueError, match="sort-key mismatch"):
        validate_sorted_explainability_order(
            scored=scored,
            query_token_count=1,
            query_len=len("drop all"),
            project_origin="project",
        )


def test_validate_sorted_explainability_order_rejects_non_monotonic_order() -> None:
    """Guard should reject candidate order that does not follow deterministic sort key."""
    scored = [
        _candidate(
            source_norm="drop all",
            score=80,
            raw_score=75,
            token_count_delta=0,
        ),
        _candidate(
            source_norm="drop",
            score=95,
            raw_score=90,
            token_count_delta=0,
        ),
    ]
    with pytest.raises(ValueError, match="non-monotonic"):
        validate_sorted_explainability_order(
            scored=scored,
            query_token_count=1,
            query_len=len("drop all"),
            project_origin="project",
        )
