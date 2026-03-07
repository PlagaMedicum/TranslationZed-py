"""Scoring and ordering helpers for TM fuzzy candidates."""

from __future__ import annotations

from .tm_query_contracts import (
    TMCandidateMetrics,
    TMScoredCandidate,
    TMScoreDecision,
)


def passes_token_gate(
    *,
    query_token_count: int,
    overlap: float,
    ratio: float,
    composed: bool,
) -> bool:
    """Return whether candidate passes overlap gates before scoring."""
    if query_token_count == 1:
        return overlap >= 0.5 or composed
    return overlap >= 0.34 or ratio >= 0.75 or composed


def score_candidate(
    *,
    query_norm: str,
    candidate_norm: str,
    query_token_count: int,
    metrics: TMCandidateMetrics,
) -> TMScoreDecision:
    """Build final score preserving legacy fuzzy caps and composed boost."""
    raw_score = int(round(metrics.ratio * 100))
    token_bonus = int(round((metrics.overlap * 6.0) + (metrics.exact_overlap * 4.0)))
    score = min(100, raw_score + token_bonus)
    composed_floor_applied = False
    if metrics.composed:
        composed_floor = 90 if query_token_count > 1 else 85
        if score < composed_floor:
            composed_floor_applied = True
        score = max(score, composed_floor)
    fuzzy_capped_to_99 = False
    if score >= 100 and candidate_norm != query_norm:
        score = 99
        fuzzy_capped_to_99 = True
    return TMScoreDecision(
        score=score,
        raw_score=raw_score,
        token_bonus=token_bonus,
        composed_floor_applied=composed_floor_applied,
        fuzzy_capped_to_99=fuzzy_capped_to_99,
    )


def _candidate_sort_key(
    *,
    item: TMScoredCandidate,
    query_token_count: int,
    query_len: int,
    project_origin: str,
) -> tuple[int, ...]:
    """Build ranking key from scoring fields used by legacy ordering."""
    len_delta = abs(len(item.row["source_norm"]) - query_len)
    origin_priority = 0 if item.row["origin"] == project_origin else 1
    updated_at = -int(item.row["updated_at"])
    if query_token_count > 1:
        return (
            item.token_count_delta,
            -item.score,
            len_delta,
            origin_priority,
            updated_at,
        )
    return (-item.score, len_delta, origin_priority, updated_at)


def _explainability_sort_key(
    *,
    item: TMScoredCandidate,
    query_token_count: int,
    query_len: int,
) -> tuple[int, ...]:
    """Build expected ranking key from explainability tie-break payload."""
    tie_break = item.explainability.tie_break
    len_delta = abs(len(item.row["source_norm"]) - query_len)
    updated_at = -int(tie_break.updated_at)
    if query_token_count > 1:
        return (
            tie_break.token_count_delta,
            -item.explainability.score,
            len_delta,
            tie_break.origin_priority,
            updated_at,
        )
    return (
        -item.explainability.score,
        len_delta,
        tie_break.origin_priority,
        updated_at,
    )


def validate_sorted_explainability_order(
    *,
    scored: list[TMScoredCandidate],
    query_token_count: int,
    query_len: int,
    project_origin: str,
) -> None:
    """Fail fast when explainability metadata diverges from ranking decisions."""
    prev_key: tuple[int, ...] | None = None
    for index, item in enumerate(scored):
        expected_key = _candidate_sort_key(
            item=item,
            query_token_count=query_token_count,
            query_len=query_len,
            project_origin=project_origin,
        )
        explain_key = _explainability_sort_key(
            item=item,
            query_token_count=query_token_count,
            query_len=query_len,
        )
        if item.raw_score != item.explainability.raw_score:
            raise ValueError(
                "TM explainability determinism guard failed: "
                f"raw_score mismatch at index {index}"
            )
        if expected_key != explain_key:
            raise ValueError(
                "TM explainability determinism guard failed: "
                f"sort-key mismatch at index {index}"
            )
        if prev_key is not None and explain_key < prev_key:
            raise ValueError(
                "TM explainability determinism guard failed: "
                "non-monotonic explainability sort order"
            )
        prev_key = explain_key


def sort_scored_candidates(
    *,
    scored: list[TMScoredCandidate],
    query_token_count: int,
    query_len: int,
    project_origin: str,
) -> list[TMScoredCandidate]:
    """Return candidates sorted with stable legacy tie-break semantics."""
    scored.sort(
        key=lambda item: _candidate_sort_key(
            item=item,
            query_token_count=query_token_count,
            query_len=query_len,
            project_origin=project_origin,
        )
    )
    return scored
