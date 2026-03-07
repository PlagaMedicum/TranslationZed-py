"""Internal TM query execution engine extracted from TMStore orchestration."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from difflib import SequenceMatcher

from .tm_query_contracts import (
    TMCandidateMetrics,
    TMCapReason,
    TMExplainability,
    TMExplainabilityBand,
    TMExplainabilityTieBreak,
    TMFuzzyCallbacks,
    TMFuzzyRuntime,
    TMQueryCallbacks,
    TMQueryRuntime,
    TMScoredCandidate,
)
from .tm_query_policy import allow_oversized_candidate, compute_candidate_length_band
from .tm_query_scoring import (
    passes_token_gate,
    score_candidate,
    sort_scored_candidates,
    validate_sorted_explainability_order,
)


def query_conn(
    conn: sqlite3.Connection,
    source_text: str,
    *,
    source_locale: str,
    target_locale: str,
    limit: int,
    min_score: int | None,
    origins: Iterable[str] | None,
    normalized_source: str | None,
    runtime: TMQueryRuntime,
    callbacks: TMQueryCallbacks,
    fuzzy_candidates_fn: Callable[
        [sqlite3.Connection, str, str, str, Iterable[str]],
        list[tuple[sqlite3.Row, int, int, TMExplainability]],
    ],
    match_cls: type,
) -> list[object]:
    """Run deterministic TM query path with exact+fuzzy composition."""
    source_locale_norm = callbacks.normalize_locale(source_locale)
    target_locale_norm = callbacks.normalize_locale(target_locale)
    origin_list = callbacks.normalize_origins(origins)
    if not origin_list:
        return []
    if min_score is None:
        min_score = runtime.min_fuzzy_score
    min_score = max(runtime.min_fuzzy_score, min(100, int(min_score)))
    norm = (
        normalized_source
        if normalized_source is not None
        else callbacks.normalize_text(source_text)
    )
    if not norm:
        return []
    origin_clause, origin_params = _origin_clause(origin_list)
    exact_rows = conn.execute(
        f"""
        SELECT
            source_text,
            target_text,
            origin,
            tm_name,
            tm_path,
            file_path,
            key,
            row_status,
            updated_at
        FROM tm_entries
        WHERE source_locale = ? AND target_locale = ? AND source_norm = ?
          AND ({runtime.import_visible_sql})
          AND {origin_clause}
        ORDER BY CASE origin WHEN 'project' THEN 0 ELSE 1 END, updated_at DESC
        """,
        (source_locale_norm, target_locale_norm, norm, *origin_params),
    ).fetchall()
    matches: list[object] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    fuzzy_reserved = (
        runtime.short_query_reserved_slots
        if len(norm) <= runtime.short_query_len
        else runtime.fuzzy_reserved_slots
    )
    max_exact = max(1, limit - fuzzy_reserved)
    for row in exact_rows:
        dedup_key = (
            row["source_text"],
            row["target_text"],
            row["origin"],
            row["tm_name"],
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        origin_priority = 0 if row["origin"] == runtime.project_origin else 1
        matches.append(
            match_cls(
                source_text=row["source_text"],
                target_text=row["target_text"],
                score=100,
                origin=row["origin"],
                tm_name=row["tm_name"],
                tm_path=row["tm_path"],
                file_path=row["file_path"],
                key=row["key"],
                updated_at=row["updated_at"],
                raw_score=100,
                row_status=row["row_status"],
                explainability=_build_exact_explainability(
                    query_norm=norm,
                    updated_at=int(row["updated_at"]),
                    origin_priority=origin_priority,
                ),
            )
        )
        if len(matches) >= max_exact:
            break
    if len(norm) > runtime.max_fuzzy_source_len:
        return matches
    candidates = fuzzy_candidates_fn(
        conn,
        norm,
        source_locale_norm,
        target_locale_norm,
        origin_list,
    )
    for cand, score, raw_score, explainability in candidates:
        if cand["source_norm"] == norm:
            continue
        dedup_key = (
            cand["source_text"],
            cand["target_text"],
            cand["origin"],
            cand["tm_name"],
        )
        if dedup_key in seen:
            continue
        if score < min_score:
            continue
        seen.add(dedup_key)
        matches.append(
            match_cls(
                source_text=cand["source_text"],
                target_text=cand["target_text"],
                score=score,
                origin=cand["origin"],
                tm_name=cand["tm_name"],
                tm_path=cand["tm_path"],
                file_path=cand["file_path"],
                key=cand["key"],
                updated_at=cand["updated_at"],
                raw_score=raw_score,
                row_status=cand["row_status"],
                explainability=explainability,
            )
        )
        if len(matches) >= limit:
            break
    return matches


def fuzzy_candidates(
    conn: sqlite3.Connection,
    norm: str,
    source_locale: str,
    target_locale: str,
    origins: Iterable[str],
    *,
    runtime: TMFuzzyRuntime,
    callbacks: TMFuzzyCallbacks,
) -> list[tuple[sqlite3.Row, int, int, TMExplainability]]:
    """Collect and score fuzzy TM candidates with deterministic ordering."""
    query_token_seq = callbacks.query_tokens_cached(norm)
    query_tokens = set(query_token_seq)
    query_token_count = len(query_tokens)
    use_en_stemming = source_locale == "EN"
    origin_list = callbacks.normalize_origins(origins)
    if not origin_list:
        return []
    origin_clause, origin_params = _origin_clause(origin_list)
    query_len = len(norm)
    prefix = norm[:8] if norm else ""
    band = compute_candidate_length_band(
        query_len=query_len,
        query_token_count=query_token_count,
        max_fuzzy_candidates=runtime.max_fuzzy_candidates,
        fuzzy_bucket_candidates=runtime.fuzzy_bucket_candidates,
        short_query_len=runtime.short_query_len,
        short_query_max_candidates=runtime.short_query_max_candidates,
        short_query_bucket_candidates=runtime.short_query_bucket_candidates,
        multi_token_len_padding=runtime.multi_token_len_padding,
    )
    rows: list[sqlite3.Row] = []
    seen_rows: set[tuple[object, ...]] = set()

    def _select_rows(
        where_sql: str,
        order_sql: str,
        where_params: tuple[object, ...],
        *,
        order_params: tuple[object, ...] = (),
        limit: int,
    ) -> list[sqlite3.Row]:
        """Query rows in one bucket pass."""
        return conn.execute(
            f"""
            SELECT
                source_text, source_norm, target_text, origin, file_path, key
                , row_status, updated_at, tm_name, tm_path
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ?
              AND {where_sql}
              AND ({runtime.import_visible_sql})
              AND {origin_clause}
            ORDER BY {order_sql}
            LIMIT ?
            """,
            (
                source_locale,
                target_locale,
                *where_params,
                *origin_params,
                *order_params,
                limit,
            ),
        ).fetchall()

    def _append_unique(candidates: list[sqlite3.Row]) -> None:
        """Append unique candidates while preserving retrieval order."""
        for row in candidates:
            row_key = (
                row["source_text"],
                row["target_text"],
                row["origin"],
                row["tm_name"],
                row["tm_path"],
                row["file_path"],
                row["key"],
            )
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            rows.append(row)
            if len(rows) >= band.max_candidates:
                return

    prefix_rows = _select_rows(
        "source_prefix = ? AND source_len BETWEEN ? AND ?",
        "ABS(source_len - ?) ASC, updated_at DESC",
        (prefix, band.min_len, band.max_len),
        order_params=(query_len,),
        limit=band.bucket_candidates,
    )
    fallback_rows = _select_rows(
        "source_len BETWEEN ? AND ?",
        "ABS(source_len - ?) ASC, updated_at DESC",
        (band.min_len, band.max_len),
        order_params=(query_len,),
        limit=band.bucket_candidates,
    )
    token_rows: list[sqlite3.Row] = []
    if query_tokens:
        # Query by longest token first to keep phrase neighbors visible even
        # when source_prefix diverges ("drop one" -> "drop-all").
        token = max(query_tokens, key=len)
        if len(token) >= 3:
            token_rows = _select_rows(
                "instr(source_norm, ?) > 0 AND source_len BETWEEN ? AND ?",
                (
                    "CASE WHEN source_norm = ? THEN 0 "
                    "WHEN source_norm LIKE ? THEN 1 "
                    "WHEN source_norm LIKE ? THEN 2 "
                    "WHEN source_norm LIKE ? THEN 3 "
                    "ELSE 4 END, ABS(source_len - ?) ASC, updated_at DESC"
                ),
                (
                    token,
                    band.min_len,
                    band.max_len,
                ),
                order_params=(
                    token,
                    f"{token} %",
                    f"% {token} %",
                    f"% {token}",
                    query_len,
                ),
                limit=band.bucket_candidates,
            )
    if query_len <= runtime.short_query_len:
        # For tiny queries, prefix-only retrieval is too strict.
        if token_rows:
            _append_unique(token_rows)
        if len(rows) < band.max_candidates:
            _append_unique(prefix_rows)
        if len(rows) < band.max_candidates:
            _append_unique(fallback_rows)
    else:
        _append_unique(prefix_rows)
        if len(rows) < band.max_candidates and token_rows:
            _append_unique(token_rows)
        if len(rows) < band.max_candidates:
            _append_unique(fallback_rows)
    scored: list[TMScoredCandidate] = []
    for row in rows:
        cand_norm = row["source_norm"]
        cand_len = len(cand_norm)
        ratio = SequenceMatcher(None, norm, cand_norm, autojunk=False).ratio()
        composed = callbacks.contains_composed_phrase_cached(
            cand_norm,
            norm,
            use_en_stemming,
        )
        overlap = 0.0
        exact_overlap = 0.0
        token_count_delta = 999
        if query_tokens:
            cand_tokens = set(callbacks.query_tokens_cached(cand_norm))
            token_count_delta = abs(len(cand_tokens) - query_token_count)
            if cand_tokens:
                overlap = callbacks.soft_token_overlap(
                    query_tokens,
                    cand_tokens,
                    use_en_stemming,
                )
                exact_overlap = callbacks.exact_token_overlap(query_tokens, cand_tokens)
                if not passes_token_gate(
                    query_token_count=query_token_count,
                    overlap=overlap,
                    ratio=ratio,
                    composed=composed,
                ):
                    continue
            elif not composed:
                continue
        oversized_guard_applied = cand_len > band.max_len_base
        oversized_guard_passed = allow_oversized_candidate(
            candidate_len=cand_len,
            max_len_base=band.max_len_base,
            overlap=overlap,
            composed=composed,
            ratio=ratio,
        )
        if not oversized_guard_passed:
            continue
        metrics = TMCandidateMetrics(
            candidate_len=cand_len,
            ratio=ratio,
            overlap=overlap,
            exact_overlap=exact_overlap,
            composed=composed,
            token_count_delta=token_count_delta,
        )
        score_decision = score_candidate(
            query_norm=norm,
            candidate_norm=cand_norm,
            query_token_count=query_token_count,
            metrics=metrics,
        )
        cap_reason: TMCapReason = "none"
        if score_decision.fuzzy_capped_to_99:
            cap_reason = "fuzzy_to_99"
        elif score_decision.composed_floor_applied:
            cap_reason = "composed_floor"
        origin_priority = 0 if row["origin"] == runtime.project_origin else 1
        decision_notes: list[str] = []
        if band.query_is_long_multi:
            decision_notes.append("long_multi_band")
        if composed:
            decision_notes.append("composed_phrase_match")
        if oversized_guard_applied and oversized_guard_passed:
            decision_notes.append("oversized_guard_passed")
        if score_decision.composed_floor_applied:
            decision_notes.append("composed_floor_applied")
        if score_decision.fuzzy_capped_to_99:
            decision_notes.append("fuzzy_capped_to_99")
        explainability = TMExplainability(
            score=score_decision.score,
            raw_score=score_decision.raw_score,
            ratio=metrics.ratio,
            overlap=metrics.overlap,
            exact_overlap=metrics.exact_overlap,
            token_bonus=score_decision.token_bonus,
            composed_phrase=metrics.composed,
            long_multi_triggered=band.query_is_long_multi,
            band=TMExplainabilityBand(
                min_base=band.min_len_base,
                max_base=band.max_len_base,
                min_effective=band.min_len,
                max_effective=band.max_len,
            ),
            oversized_guard_applied=oversized_guard_applied,
            oversized_guard_passed=(
                oversized_guard_passed if oversized_guard_applied else None
            ),
            cap_reason=cap_reason,
            tie_break=TMExplainabilityTieBreak(
                token_count_delta=max(0, metrics.token_count_delta),
                origin_priority=origin_priority,
                updated_at=int(row["updated_at"]),
            ),
            decision_notes=tuple(decision_notes),
        )
        scored.append(
            TMScoredCandidate(
                row=row,
                score=score_decision.score,
                raw_score=score_decision.raw_score,
                token_count_delta=metrics.token_count_delta,
                explainability=explainability,
            )
        )
    sorted_scored = sort_scored_candidates(
        scored=scored,
        query_token_count=query_token_count,
        query_len=query_len,
        project_origin=runtime.project_origin,
    )
    validate_sorted_explainability_order(
        scored=sorted_scored,
        query_token_count=query_token_count,
        query_len=query_len,
        project_origin=runtime.project_origin,
    )
    return [
        (item.row, item.score, item.raw_score, item.explainability)
        for item in sorted_scored
    ]


def _build_exact_explainability(
    *,
    query_norm: str,
    updated_at: int,
    origin_priority: int,
) -> TMExplainability:
    """Build explainability payload for exact source-norm TM matches."""
    query_len = len(query_norm)
    token_count = len([token for token in query_norm.split(" ") if token])
    overlap = 1.0 if token_count > 0 else 0.0
    return TMExplainability(
        score=100,
        raw_score=100,
        ratio=1.0,
        overlap=overlap,
        exact_overlap=overlap,
        token_bonus=0,
        composed_phrase=False,
        long_multi_triggered=False,
        band=TMExplainabilityBand(
            min_base=query_len,
            max_base=query_len,
            min_effective=query_len,
            max_effective=query_len,
        ),
        oversized_guard_applied=False,
        oversized_guard_passed=None,
        cap_reason="none",
        tie_break=TMExplainabilityTieBreak(
            token_count_delta=0,
            origin_priority=origin_priority,
            updated_at=updated_at,
        ),
        decision_notes=("exact_match",),
    )


def _origin_clause(origins: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Build origin SQL clause and bound parameters."""
    if len(origins) == 1:
        return "origin = ?", (origins[0],)
    return "origin IN (?, ?)", (origins[0], origins[1])
