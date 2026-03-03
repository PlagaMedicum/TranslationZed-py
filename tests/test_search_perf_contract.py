"""Search Wave-2 perf contract tests on deterministic 20k workloads."""

from __future__ import annotations

import gc
import os
import re
import statistics
import time
from collections.abc import Callable
from pathlib import Path

from tests.fixtures.perf_generated.builders import build_translation_file
from translationzed_py.core import SearchField, parse
from translationzed_py.core.search import Match, SearchRow, iter_matches
from translationzed_py.core.search_replace_service import SearchReplaceService


def _median_ms(repeats: int, fn: Callable[[], object]) -> float:
    values: list[float] = []
    for _ in range(max(1, repeats)):
        gc.collect()
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(values))


def _legacy_matches_literal(text: str, query: str) -> bool:
    if query in text:
        return True
    parts = [part for part in query.split() if part]
    if len(parts) < 2:
        return False
    total_chars = sum(len(part) for part in parts)
    if total_chars < 4:
        return False
    pos = 0
    for part in parts:
        found = text.find(part, pos)
        if found < 0:
            return False
        pos = found + len(part)
    return True


def _legacy_search_matches(
    rows: list[SearchRow],
    *,
    query: str,
    field: SearchField,
    is_regex: bool,
    case_sensitive: bool,
) -> list[Match]:
    if not query:
        return []
    if field is SearchField.KEY:
        attr = "key"
    elif field is SearchField.SOURCE:
        attr = "source"
    else:
        attr = "value"

    if is_regex:
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        try:
            matcher = re.compile(query, flags)
        except re.error:
            return []
        matches: list[Match] = []
        for row in rows:
            if matcher.search(getattr(row, attr) or ""):
                matches.append(Match(row.file, row.row))
        return matches

    query_text = query if case_sensitive else query.lower()
    matches = []
    for row in rows:
        text = getattr(row, attr) or ""
        target = text if case_sensitive else text.lower()
        if _legacy_matches_literal(target, query_text):
            matches.append(Match(row.file, row.row))
    return matches


def _rows_for_search_perf(path: Path, entries: int) -> list[SearchRow]:
    build_translation_file(path, entries=entries)
    parsed = parse(path, encoding="utf-8")
    return [
        SearchRow(path, row, entry.key, entry.key, entry.value)
        for row, entry in enumerate(parsed.entries)
    ]


def test_search_wave2_speedup_contract_20k(tmp_path: Path, perf_recorder) -> None:
    """Verify optimized search reaches configured 20k median speedup target."""
    repeats = int(os.getenv("TZP_PERF_SEARCH_REPEATS", "9"))
    target_speedup_percent = float(
        os.getenv("TZP_PERF_SEARCH_SPEEDUP_20K_PERCENT", "30")
    )
    rows = _rows_for_search_perf(tmp_path / "search_20k.txt", entries=20_000)
    field = SearchField.TRANSLATION
    queries = (
        "value token 19999",
        "quoted inner value 00011",
        "tail 00017",
        "multi alpha beta",
        "zzz notfound",
    )
    service = SearchReplaceService()
    prepared_plans = {
        query: service.prepare_search_plan(
            query=query,
            use_regex=False,
            case_sensitive=False,
        )
        for query in queries
    }
    assert all(plan is not None for plan in prepared_plans.values())

    for query in queries:
        expected = _legacy_search_matches(
            rows,
            query=query,
            field=field,
            is_regex=False,
            case_sensitive=False,
        )
        optimized = list(
            iter_matches(
                rows,
                query,
                field,
                False,
                case_sensitive=False,
                prepared_plan=prepared_plans[query],
            )
        )
        assert optimized == expected

    def _legacy_pack() -> int:
        total = 0
        for query in queries:
            total += len(
                _legacy_search_matches(
                    rows,
                    query=query,
                    field=field,
                    is_regex=False,
                    case_sensitive=False,
                )
            )
        return total

    def _optimized_pack() -> int:
        total = 0
        for query in queries:
            total += len(
                list(
                    iter_matches(
                        rows,
                        query,
                        field,
                        False,
                        case_sensitive=False,
                        prepared_plan=prepared_plans[query],
                    )
                )
            )
        return total

    legacy_ms = _median_ms(
        repeats,
        _legacy_pack,
    )
    optimized_ms = _median_ms(
        repeats,
        _optimized_pack,
    )
    speedup_percent = (
        ((legacy_ms - optimized_ms) / legacy_ms) * 100.0 if legacy_ms > 0.0 else 0.0
    )
    target_ms = legacy_ms * (1.0 - (target_speedup_percent / 100.0))
    perf_recorder(
        "search wave2 speedup contract (20k)",
        optimized_ms,
        target_ms,
        (
            f"legacy={legacy_ms:.2f}ms speedup={speedup_percent:.2f}% "
            f"target={target_speedup_percent:.2f}% entries=20000"
        ),
    )
    assert speedup_percent >= target_speedup_percent
