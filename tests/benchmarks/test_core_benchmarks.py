"""Test module for core benchmarks."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core import SearchField, SearchRow, parse, parse_lazy, search
from translationzed_py.core.search_replace_service import SearchReplaceService
from translationzed_py.core.tm_store import TMStore


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


def _build_synthetic_file(path: Path, entries: int = 20_000) -> None:
    lines = [f'K_{idx:05d} = "Value token {idx:05d}"' for idx in range(max(1, entries))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_bench_parse_lazy_synthetic_20k(benchmark, tmp_path: Path) -> None:
    """Benchmark lazy parse throughput on deterministic synthetic 20k fixture."""
    path = tmp_path / "synthetic_20k.txt"
    _build_synthetic_file(path, entries=20_000)

    def _run() -> int:
        parsed = parse_lazy(path, encoding="utf-8")
        return len(parsed.entries)

    count = benchmark(_run)
    assert count == 20_000


def test_bench_search_translation_synthetic_20k(benchmark, tmp_path: Path) -> None:
    """Benchmark translation-column search speed on synthetic 20k rows."""
    path = tmp_path / "synthetic_20k.txt"
    _build_synthetic_file(path, entries=20_000)
    parsed = parse(path, encoding="utf-8")
    rows = [
        SearchRow(path, row, entry.key, "", entry.value)
        for row, entry in enumerate(parsed.entries)
    ]
    service = SearchReplaceService()
    query = "value token 19999"
    prepared_plan = service.prepare_search_plan(
        query=query,
        use_regex=False,
        case_sensitive=False,
    )
    assert prepared_plan is not None

    def _run() -> int:
        matches = search(
            rows,
            query,
            SearchField.TRANSLATION,
            False,
            prepared_plan=prepared_plan,
        )
        return len(matches)

    count = benchmark(_run)
    assert count == 1


def test_bench_tm_query_synthetic_20k(benchmark, tmp_path: Path) -> None:
    """Benchmark TM query latency on synthetic 20k in-project corpus."""
    store = TMStore(tmp_path / "tm")
    try:
        rows = [
            ("anchor", "Drop all", "Пакінуць усё"),
            ("neighbor_a", "Drop one", "Скінуць адно"),
            ("neighbor_b", "Drop-all", "Скінуць-усё"),
        ]
        rows.extend(
            (
                f"k_{idx:05d}",
                f"Noise token {idx:05d}",
                f"Noise tr {idx:05d}",
            )
            for idx in range(len(rows), 20_000)
        )
        store.upsert_project_entries(
            rows,
            source_locale="EN",
            target_locale="BE",
            file_path="synthetic.txt",
            updated_at=1,
        )

        def _run() -> int:
            return len(
                store.query(
                    "Drop all",
                    source_locale="EN",
                    target_locale="BE",
                    limit=20,
                    min_score=5,
                )
            )

        count = benchmark(_run)
        assert count >= 1
    finally:
        store.close()
