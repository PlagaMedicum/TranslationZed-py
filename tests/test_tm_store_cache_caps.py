"""Deterministic fixed-cap cache behavior tests for TM fuzzy-query helpers."""

from __future__ import annotations

import translationzed_py.core.tm_store as tm_store_module


def test_token_cache_is_hard_capped_and_lru_eviction_is_deterministic() -> None:
    """Verify token cache capacity and LRU eviction order are deterministic."""
    tm_store_module.clear_query_caches()

    cap = tm_store_module._TOKEN_CACHE_CAP
    for idx in range(cap):
        tm_store_module._query_tokens_cached(f"token {idx:05d}")

    stats = tm_store_module.query_cache_stats()["token"]
    assert stats.currsize == cap

    before = tm_store_module.query_cache_stats()["token"]
    tm_store_module._query_tokens_cached("token 00000")
    touched = tm_store_module.query_cache_stats()["token"]
    assert touched.hits == before.hits + 1

    tm_store_module._query_tokens_cached("brand-new token")
    inserted = tm_store_module.query_cache_stats()["token"]
    assert inserted.currsize == cap

    tm_store_module._query_tokens_cached("token 00001")
    after = tm_store_module.query_cache_stats()["token"]
    assert after.misses == inserted.misses + 1


def test_stem_phrase_and_match_caches_respect_hard_caps() -> None:
    """Verify stem/phrase/token-match helper caches never exceed configured caps."""
    tm_store_module.clear_query_caches()

    stem_cap = tm_store_module._STEM_CACHE_CAP
    for idx in range(stem_cap + 100):
        tm_store_module._stem_token_cached(f"running{idx:05d}")

    phrase_cap = tm_store_module._PHRASE_MATCH_CACHE_CAP
    for idx in range(phrase_cap + 100):
        tm_store_module._contains_composed_phrase_cached(
            f"alpha beta {idx:05d}",
            "alpha beta",
            True,
        )

    match_cap = tm_store_module._TOKEN_MATCH_CACHE_CAP
    for idx in range(match_cap + 100):
        tm_store_module._token_matches_cached(
            f"query{idx:05d}",
            f"candidate{idx:05d}",
            True,
        )

    stats = tm_store_module.query_cache_stats()
    assert stats["stem"].currsize == stem_cap
    assert stats["phrase"].currsize == phrase_cap
    assert stats["token_match"].currsize == match_cap
