"""Scoring and ordering helpers for TM fuzzy candidates."""

from __future__ import annotations

from .tm_query_contracts import TMCandidateMetrics, TMScoredCandidate


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
) -> tuple[int, int]:
    """Build final score preserving legacy fuzzy caps and composed boost."""
    raw_score = int(round(metrics.ratio * 100))
    token_bonus = int(round((metrics.overlap * 6.0) + (metrics.exact_overlap * 4.0)))
    score = min(100, raw_score + token_bonus)
    if metrics.composed:
        score = max(score, 90 if query_token_count > 1 else 85)
    if score >= 100 and candidate_norm != query_norm:
        score = 99
    return score, raw_score


def sort_scored_candidates(
    *,
    scored: list[TMScoredCandidate],
    query_token_count: int,
    query_len: int,
    project_origin: str,
) -> list[TMScoredCandidate]:
    """Return candidates sorted with stable legacy tie-break semantics."""
    if query_token_count > 1:
        scored.sort(
            key=lambda item: (
                item.token_count_delta,
                -item.score,
                abs(len(item.row["source_norm"]) - query_len),
                0 if item.row["origin"] == project_origin else 1,
                -item.row["updated_at"],
            )
        )
        return scored
    scored.sort(
        key=lambda item: (
            -item.score,
            abs(len(item.row["source_norm"]) - query_len),
            0 if item.row["origin"] == project_origin else 1,
            -item.row["updated_at"],
        )
    )
    return scored
