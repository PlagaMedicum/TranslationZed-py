"""Policy helpers for TM fuzzy-query normalization and length bands."""

from __future__ import annotations

import re

from .tm_query_contracts import TMLengthBand

_LIST_PREFIX_RE = re.compile(r"(?m)^\s*(?:[-*]\s+|\d+[.)]\s+)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_PAIR_WRAPPER_RE = re.compile(r"(?<!\w)(\*\*|__|~~)([^`\n]+?)\1(?!\w)")
_SINGLE_WRAPPER_RE = re.compile(r"(?<!\w)(\*|_)([^`\n]+?)\1(?!\w)")


def strip_tm_wrappers(text: str) -> str:
    """Strip formatting wrappers while preserving semantic tokens."""
    cleaned = _LIST_PREFIX_RE.sub("", text)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    previous = ""
    while previous != cleaned:
        previous = cleaned
        cleaned = _PAIR_WRAPPER_RE.sub(r"\2", cleaned)
        cleaned = _SINGLE_WRAPPER_RE.sub(r"\2", cleaned)
    return cleaned


def normalize_for_match(text: str) -> str:
    """Normalize text used by TM ranking query paths."""
    return " ".join(strip_tm_wrappers(text).lower().split())


def compute_candidate_length_band(
    *,
    query_len: int,
    query_token_count: int,
    max_fuzzy_candidates: int,
    fuzzy_bucket_candidates: int,
    short_query_len: int,
    short_query_max_candidates: int,
    short_query_bucket_candidates: int,
    multi_token_len_padding: int,
) -> TMLengthBand:
    """Compute retrieval length band with adaptive long-query widening."""
    query_is_long_multi = query_token_count >= 8 and query_len >= 80
    min_len_base = max(1, int(query_len * 0.6))
    max_len_base = int(query_len * 1.4) if query_len > 5 else query_len + 10
    min_len = min_len_base
    max_len = max_len_base
    if query_is_long_multi:
        min_len = max(1, int(query_len * 0.5))
        max_len = max(max_len_base, int(query_len * 1.85))
    if query_token_count > 1:
        # Allow phrase-expansion neighbors ("make item" -> "make new item").
        max_len = max(
            max_len,
            query_len + max(multi_token_len_padding, query_token_count * 2),
        )
    max_candidates = max_fuzzy_candidates
    bucket_candidates = fuzzy_bucket_candidates
    if query_len <= short_query_len:
        min_len = 1
        max_len = max(max_len, 40)
        max_candidates = short_query_max_candidates
        bucket_candidates = short_query_bucket_candidates
    return TMLengthBand(
        min_len_base=min_len_base,
        max_len_base=max_len_base,
        min_len=min_len,
        max_len=max_len,
        max_candidates=max_candidates,
        bucket_candidates=bucket_candidates,
        query_is_long_multi=query_is_long_multi,
    )


def allow_oversized_candidate(
    *,
    candidate_len: int,
    max_len_base: int,
    overlap: float,
    composed: bool,
    ratio: float,
) -> bool:
    """Return whether oversized candidate should remain in fuzzy pool."""
    if candidate_len <= max_len_base:
        return True
    return overlap >= 0.55 or (composed and ratio >= 0.70)
