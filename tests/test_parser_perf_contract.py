"""Parser legacy-vs-fast perf/equivalence contracts on generated 2k/20k corpora."""

from __future__ import annotations

import gc
import os
import statistics
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import translationzed_py.core.parser as parser_module
from tests.fixtures.perf_generated.builders import build_translation_file
from translationzed_py.core import parse


def _median_ms(repeats: int, fn: Callable[[], object]) -> float:
    values: list[float] = []
    for _ in range(max(1, repeats)):
        gc.collect()
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(values))


@contextmanager
def _use_offset_builder(builder: Callable[[str, str], list[int]]):
    original = parser_module._build_offset_map
    parser_module._build_offset_map = builder  # type: ignore[assignment]
    try:
        yield
    finally:
        parser_module._build_offset_map = original  # type: ignore[assignment]


def _entry_snapshot(parsed: Any) -> list[tuple[Any, ...]]:
    return [
        (
            entry.key,
            entry.value,
            int(entry.status),
            entry.span,
            entry.segments,
            entry.gaps,
            entry.raw,
            entry.key_hash,
        )
        for entry in parsed.entries
    ]


def _parse_with_builder(path: Path, builder: Callable[[str, str], list[int]]):
    with _use_offset_builder(builder):
        return parse(path, encoding="utf-8")


@pytest.mark.parametrize("entries", [2_000, 20_000])
def test_parser_fast_path_matches_legacy_output(entries: int, tmp_path: Path) -> None:
    """Verify parse output is identical when switching offset-map builder."""
    path = tmp_path / f"parser_{entries}.txt"
    build_translation_file(path, entries=entries)

    legacy = _parse_with_builder(path, parser_module._build_offset_map_legacy)
    optimized = _parse_with_builder(path, parser_module._build_offset_map)

    assert _entry_snapshot(optimized) == _entry_snapshot(legacy)


def test_parser_speedup_contract_20k(tmp_path: Path, perf_recorder) -> None:
    """Verify parser offset-map phase improves by configured speedup target."""
    entries = 20_000
    repeats = int(os.getenv("TZP_PERF_PARSE_REPEATS", "7"))
    target_speedup_percent = float(
        os.getenv("TZP_PERF_PARSE_SPEEDUP_20K_PERCENT", "45")
    )
    path = tmp_path / "parser_20k.txt"
    build_translation_file(path, entries=entries)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    expected_len = len(raw)

    legacy_ms = _median_ms(
        repeats,
        lambda: parser_module._build_offset_map_legacy(text, "utf-8"),
    )
    optimized_ms = _median_ms(
        repeats,
        lambda: parser_module._ensure_offset_map(
            text,
            "utf-8",
            expected_len=expected_len,
        ),
    )

    speedup_percent = (
        ((legacy_ms - optimized_ms) / legacy_ms) * 100.0 if legacy_ms > 0.0 else 0.0
    )
    target_ms = legacy_ms * (1.0 - (target_speedup_percent / 100.0))
    perf_recorder(
        "parser offset-map speedup contract (20k)",
        optimized_ms,
        target_ms,
        (
            f"legacy={legacy_ms:.2f}ms speedup={speedup_percent:.2f}% "
            f"target={target_speedup_percent:.2f}% entries={entries}"
        ),
    )
    assert speedup_percent >= target_speedup_percent
