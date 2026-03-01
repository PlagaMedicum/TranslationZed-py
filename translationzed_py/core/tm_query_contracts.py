"""Internal data contracts for TM query orchestration."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TMLengthBand:
    """Represent computed fuzzy-candidate length bounds."""

    min_len_base: int
    max_len_base: int
    min_len: int
    max_len: int
    max_candidates: int
    bucket_candidates: int
    query_is_long_multi: bool


@dataclass(frozen=True, slots=True)
class TMCandidateMetrics:
    """Represent intermediate metrics for one fuzzy candidate."""

    candidate_len: int
    ratio: float
    overlap: float
    exact_overlap: float
    composed: bool
    token_count_delta: int


@dataclass(frozen=True, slots=True)
class TMScoredCandidate:
    """Represent scored fuzzy candidate row and ranking metadata."""

    row: sqlite3.Row
    score: int
    raw_score: int
    token_count_delta: int


@dataclass(frozen=True, slots=True)
class TMQueryRuntime:
    """Represent immutable query-level constants used during matching."""

    min_fuzzy_score: int
    short_query_len: int
    fuzzy_reserved_slots: int
    short_query_reserved_slots: int
    max_fuzzy_source_len: int
    project_origin: str
    import_visible_sql: str


@dataclass(frozen=True, slots=True)
class TMFuzzyRuntime:
    """Represent immutable constants used by fuzzy-candidate retrieval."""

    max_fuzzy_candidates: int
    fuzzy_bucket_candidates: int
    short_query_len: int
    short_query_max_candidates: int
    short_query_bucket_candidates: int
    multi_token_len_padding: int
    project_origin: str
    import_visible_sql: str


@dataclass(frozen=True, slots=True)
class TMQueryCallbacks:
    """Represent helper callbacks injected from tm_store for compatibility."""

    normalize_locale: Callable[[str], str]
    normalize_origins: Callable[[Iterable[str] | None], tuple[str, ...]]
    normalize_text: Callable[[str], str]


@dataclass(frozen=True, slots=True)
class TMFuzzyCallbacks:
    """Represent fuzzy helper callbacks injected from tm_store."""

    normalize_origins: Callable[[Iterable[str] | None], tuple[str, ...]]
    query_tokens_cached: Callable[[str], tuple[str, ...]]
    contains_composed_phrase_cached: Callable[[str, str, bool], bool]
    soft_token_overlap: Callable[[set[str], set[str], bool], float]
    exact_token_overlap: Callable[[set[str], set[str]], float]
