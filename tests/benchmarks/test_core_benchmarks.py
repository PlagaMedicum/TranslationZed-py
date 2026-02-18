from __future__ import annotations

from pathlib import Path

from translationzed_py.core import SearchField, SearchRow, parse, parse_lazy, search


def _perf_file(name: str) -> Path:
    """Return a committed benchmark fixture file path."""
    return Path(__file__).resolve().parents[1] / "fixtures" / "perf_root" / "BE" / name


def test_bench_parse_lazy_survivalguide(benchmark) -> None:
    """Benchmark lazy parse throughput on the large fixture."""
    path = _perf_file("SurvivalGuide_BE.txt")

    def _run() -> int:
        parsed = parse_lazy(path, encoding="utf-8")
        return len(parsed.entries)

    count = benchmark(_run)
    assert count > 0


def test_bench_parse_eager_recorded_media(benchmark) -> None:
    """Benchmark eager parse throughput on the large fixture."""
    path = _perf_file("Recorded_Media_BE.txt")

    def _run() -> int:
        parsed = parse(path, encoding="utf-8")
        return len(parsed.entries)

    count = benchmark(_run)
    assert count > 0


def test_bench_search_translation_survivalguide(benchmark) -> None:
    """Benchmark translation-column search speed on prepared rows."""
    path = _perf_file("SurvivalGuide_BE.txt")
    parsed = parse(path, encoding="utf-8")
    rows = [
        SearchRow(path, row, entry.key, "", entry.value)
        for row, entry in enumerate(parsed.entries)
    ]

    def _run() -> int:
        matches = search(rows, "item", SearchField.TRANSLATION, False)
        return len(matches)

    count = benchmark(_run)
    assert count >= 0
