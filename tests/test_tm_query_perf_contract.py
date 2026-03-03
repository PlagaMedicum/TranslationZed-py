"""TM query bit-stability and perf contracts at synthetic 20k scale."""

from __future__ import annotations

import gc
import os
import statistics
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import translationzed_py.core.tm_store as tm_store_module
from tests.fixtures.perf_generated.builders import (
    build_tm_perf_query_pack,
    build_tm_query_pack,
    build_tm_rows,
)
from translationzed_py.core.tm_store import TMStore


def _median_ms(
    repeats: int,
    fn: Callable[[], object],
    *,
    setup: Callable[[], object] | None = None,
) -> float:
    values: list[float] = []
    for _ in range(max(1, repeats)):
        if setup is not None:
            setup()
        gc.collect()
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(values))


@contextmanager
def _legacy_tm_query_helpers() -> Iterator[None]:
    original_token = tm_store_module._query_tokens_cached
    original_stem = tm_store_module._stem_token_cached
    original_match = tm_store_module._token_matches_cached
    original_phrase = tm_store_module._contains_composed_phrase_cached

    tm_store_module._query_tokens_cached = tm_store_module._query_tokens
    tm_store_module._stem_token_cached = tm_store_module._stem_token
    tm_store_module._token_matches_cached = tm_store_module._token_matches_uncached
    tm_store_module._contains_composed_phrase_cached = (
        tm_store_module._contains_composed_phrase_uncached
    )
    try:
        yield
    finally:
        tm_store_module._query_tokens_cached = original_token
        tm_store_module._stem_token_cached = original_stem
        tm_store_module._token_matches_cached = original_match
        tm_store_module._contains_composed_phrase_cached = original_phrase


def _matches_snapshot(matches) -> list[tuple[object, ...]]:
    return [
        (
            item.source_text,
            item.target_text,
            item.score,
            item.origin,
            item.tm_name,
            item.tm_path,
            item.file_path,
            item.key,
            item.updated_at,
            item.raw_score,
            item.row_status,
        )
        for item in matches
    ]


def _build_store(root: Path, entries: int) -> TMStore:
    store = TMStore(root)
    rows = build_tm_rows(entries=entries)
    store.upsert_project_entries(
        rows,
        source_locale="EN",
        target_locale="BE",
        file_path="synthetic.txt",
        updated_at=1,
    )
    return store


def _run_legacy_pack(store: TMStore, queries: tuple[str, ...]) -> int:
    with _legacy_tm_query_helpers():
        total = 0
        for query in queries:
            total += len(
                TMStore._query_conn(
                    store._conn,
                    query,
                    source_locale="EN",
                    target_locale="BE",
                    limit=20,
                    min_score=5,
                    origins=None,
                )
            )
        return total


def _run_optimized_pack(store: TMStore, queries: tuple[str, ...]) -> int:
    total = 0
    for query in queries:
        total += len(
            store.query(
                query,
                source_locale="EN",
                target_locale="BE",
                limit=20,
                min_score=5,
            )
        )
    return total


def test_tm_query_optimized_path_is_bit_stable_vs_legacy(tmp_path: Path) -> None:
    """Verify optimized TM query path preserves ordered score/result output."""
    entries = 20_000
    store = _build_store(tmp_path / "tm_bit_stable", entries)
    try:
        for query in build_tm_query_pack():
            with _legacy_tm_query_helpers():
                legacy = store.query(
                    query,
                    source_locale="EN",
                    target_locale="BE",
                    limit=20,
                    min_score=5,
                )
            tm_store_module.clear_query_caches()
            optimized = store.query(
                query,
                source_locale="EN",
                target_locale="BE",
                limit=20,
                min_score=5,
            )
            assert _matches_snapshot(optimized) == _matches_snapshot(legacy)
    finally:
        store.close()


def test_tm_query_speedup_contract_20k(tmp_path: Path, perf_recorder) -> None:
    """Verify TM warm-cache query 20k median improves by configured target."""
    entries = 20_000
    repeats = int(os.getenv("TZP_PERF_TM_REPEATS", "7"))
    target_speedup_percent = float(os.getenv("TZP_PERF_TM_SPEEDUP_20K_PERCENT", "35"))
    queries = build_tm_perf_query_pack()

    store = _build_store(tmp_path / "tm_perf", entries)
    try:
        legacy_ms = _median_ms(repeats, lambda: _run_legacy_pack(store, queries))
        # Prewarm once so repeated measurements represent cache-hot runtime path.
        _run_optimized_pack(store, queries)
        optimized_ms = _median_ms(repeats, lambda: _run_optimized_pack(store, queries))
        speedup_percent = (
            ((legacy_ms - optimized_ms) / legacy_ms) * 100.0 if legacy_ms > 0.0 else 0.0
        )
        target_ms = legacy_ms * (1.0 - (target_speedup_percent / 100.0))
        perf_recorder(
            "tm warm-cache speedup contract (20k)",
            optimized_ms,
            target_ms,
            (
                f"legacy={legacy_ms:.2f}ms speedup={speedup_percent:.2f}% "
                f"target={target_speedup_percent:.2f}% entries={entries}"
            ),
        )
        assert speedup_percent >= target_speedup_percent
    finally:
        store.close()


def test_tm_query_cold_cache_speedup_contract_20k(
    tmp_path: Path, perf_recorder
) -> None:
    """Verify TM cold-cache query 20k median improves by configured target."""
    entries = 20_000
    repeats = int(os.getenv("TZP_PERF_TM_COLD_REPEATS", "7"))
    target_speedup_percent = float(
        os.getenv("TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT", "3")
    )
    queries = build_tm_perf_query_pack()

    store = _build_store(tmp_path / "tm_perf_cold", entries)
    try:
        legacy_ms = _median_ms(repeats, lambda: _run_legacy_pack(store, queries))
        optimized_ms = _median_ms(
            repeats,
            lambda: _run_optimized_pack(store, queries),
            setup=store.clear_runtime_caches,
        )
        speedup_percent = (
            ((legacy_ms - optimized_ms) / legacy_ms) * 100.0 if legacy_ms > 0.0 else 0.0
        )
        target_ms = legacy_ms * (1.0 - (target_speedup_percent / 100.0))
        perf_recorder(
            "tm cold-cache speedup contract (20k)",
            optimized_ms,
            target_ms,
            (
                f"legacy={legacy_ms:.2f}ms speedup={speedup_percent:.2f}% "
                f"target={target_speedup_percent:.2f}% entries={entries}"
            ),
        )
        assert speedup_percent >= target_speedup_percent
    finally:
        store.close()
