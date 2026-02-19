"""Test module for tm perf autoderived."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from translationzed_py.core import parse_lazy
from translationzed_py.core.project_scanner import scan_root_with_errors
from translationzed_py.core.tm_store import TMStore
from translationzed_py.core.tmx_io import write_tmx


def _budget_ms(env_name: str, default_ms: float) -> float:
    raw = os.getenv(env_name, "")
    if not raw:
        return default_ms
    try:
        return float(raw)
    except ValueError:
        return default_ms


def _perf_fixture_root() -> Path:
    return Path(__file__).parent / "fixtures" / "perf_root"


def _derive_tm_stress_size() -> int:
    root = _perf_fixture_root()
    locales, errors = scan_root_with_errors(root)
    assert not errors
    be = locales.get("BE")
    assert be is not None

    counts: list[int] = []
    for path in sorted((root / "BE").glob("*.txt")):
        if path.name == "language.txt":
            continue
        parsed = parse_lazy(path, encoding=be.charset)
        counts.append(len(parsed.entries))
    assert counts
    return max(counts)


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default_value: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default_value
    try:
        return int(raw)
    except ValueError:
        return default_value


def test_tm_query_perf_autoderived_from_committed_perf_fixtures(
    tmp_path: Path, perf_recorder
) -> None:
    """Verify tm query perf autoderived from committed perf fixtures."""
    count = max(100, _derive_tm_stress_size())
    budget_ms = _budget_ms("TZP_PERF_TM_QUERY_MS", 1200.0)
    root = tmp_path / "tm_perf"
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    store = TMStore(root)
    try:
        rows = [
            ("anchor", "Drop all", "Пакід. усё"),
            ("neighbor", "Drop one", "Скінуць шт."),
            ("hyphen", "Drop-all", "Пакінуць усё"),
        ]
        rows.extend(
            (
                f"noise_{idx:05d}",
                f"Random token {idx:05d}",
                f"Noise tr {idx:05d}",
            )
            for idx in range(max(0, count - len(rows)))
        )
        store.upsert_project_entries(
            rows,
            source_locale="EN",
            target_locale="BE",
            file_path=str(file_path),
            updated_at=1,
        )

        start = time.perf_counter()
        matches = store.query(
            "Drop all",
            source_locale="EN",
            target_locale="BE",
            limit=20,
            min_score=5,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        perf_recorder(
            "tm query (auto-derived prod max)",
            elapsed_ms,
            budget_ms,
            f"entries={count}",
        )
        assert elapsed_ms <= budget_ms
        sources = {item.source_text for item in matches}
        assert "Drop all" in sources
        assert "Drop one" in sources
    finally:
        store.close()


def test_tm_import_query_perf_autoderived_from_committed_perf_fixtures(
    tmp_path: Path, perf_recorder
) -> None:
    """Verify tm import query perf autoderived from committed perf fixtures."""
    count = max(100, _derive_tm_stress_size())
    import_budget_ms = _budget_ms("TZP_PERF_TM_IMPORT_MS", 2200.0)
    query_budget_ms = _budget_ms("TZP_PERF_TM_IMPORT_QUERY_MS", 1200.0)
    root = tmp_path / "tm_import_perf"
    root.mkdir(parents=True, exist_ok=True)
    tm_path = root / ".tzp" / "tms" / "bulk.tmx"
    tm_path.parent.mkdir(parents=True, exist_ok=True)

    pairs = [
        ("Drop all", "Пакід. усё"),
        ("Drop one", "Скінуць шт."),
        ("Drop-all", "Пакінуць усё"),
    ]
    pairs.extend(
        (
            f"Random token {idx:05d}",
            f"Noise tr {idx:05d}",
        )
        for idx in range(max(0, count - len(pairs)))
    )
    write_tmx(tm_path, pairs, source_locale="EN", target_locale="BE")

    store = TMStore(root)
    try:
        start = time.perf_counter()
        imported = store.replace_import_tm(
            tm_path,
            source_locale="EN",
            target_locale="BE",
            source_locale_raw="EN",
            target_locale_raw="BE",
            tm_name="bulk",
        )
        import_elapsed_ms = (time.perf_counter() - start) * 1000.0
        perf_recorder(
            "tm import load (auto-derived prod max)",
            import_elapsed_ms,
            import_budget_ms,
            f"segments={count}",
        )
        assert import_elapsed_ms <= import_budget_ms
        assert imported == count

        start = time.perf_counter()
        matches = store.query(
            "Drop all",
            source_locale="EN",
            target_locale="BE",
            limit=20,
            min_score=5,
            origins=["import"],
        )
        query_elapsed_ms = (time.perf_counter() - start) * 1000.0
        perf_recorder(
            "tm import query (auto-derived prod max)",
            query_elapsed_ms,
            query_budget_ms,
            f"entries={count}",
        )
        assert query_elapsed_ms <= query_budget_ms
        sources = {item.source_text for item in matches}
        assert "Drop all" in sources
        assert "Drop one" in sources
    finally:
        store.close()


@pytest.mark.skipif(
    not _env_flag("TZP_PERF_TM_HEAVY"),
    reason="set TZP_PERF_TM_HEAVY=1 to enable heavy TM stress profile",
)
def test_tm_import_query_perf_heavy_stress_profile(
    tmp_path: Path, perf_recorder
) -> None:
    """Verify heavy-lane TM import/query profile on scaled corpora."""
    base_count = max(100, _derive_tm_stress_size())
    multiplier = max(2, _env_int("TZP_PERF_TM_HEAVY_MULTIPLIER", 3))
    count = base_count * multiplier
    import_budget_ms = _budget_ms("TZP_PERF_TM_IMPORT_HEAVY_MS", 7000.0)
    query_budget_ms = _budget_ms("TZP_PERF_TM_IMPORT_QUERY_HEAVY_MS", 3500.0)
    root = tmp_path / "tm_import_perf_heavy"
    root.mkdir(parents=True, exist_ok=True)
    tm_path = root / ".tzp" / "tms" / "bulk-heavy.tmx"
    tm_path.parent.mkdir(parents=True, exist_ok=True)

    pairs = [
        ("Drop all", "Пакід. усё"),
        ("Drop one", "Скінуць шт."),
        ("Drop-all", "Пакінуць усё"),
    ]
    pairs.extend(
        (
            f"Heavy random token {idx:06d}",
            f"Heavy noise tr {idx:06d}",
        )
        for idx in range(max(0, count - len(pairs)))
    )
    write_tmx(tm_path, pairs, source_locale="EN", target_locale="BE")

    store = TMStore(root)
    try:
        start = time.perf_counter()
        imported = store.replace_import_tm(
            tm_path,
            source_locale="EN",
            target_locale="BE",
            source_locale_raw="EN",
            target_locale_raw="BE",
            tm_name="bulk-heavy",
        )
        import_elapsed_ms = (time.perf_counter() - start) * 1000.0
        perf_recorder(
            "tm import load (heavy auto-derived stress)",
            import_elapsed_ms,
            import_budget_ms,
            f"segments={count}",
        )
        assert import_elapsed_ms <= import_budget_ms
        assert imported == count

        start = time.perf_counter()
        matches = store.query(
            "Drop all",
            source_locale="EN",
            target_locale="BE",
            limit=20,
            min_score=5,
            origins=["import"],
        )
        query_elapsed_ms = (time.perf_counter() - start) * 1000.0
        perf_recorder(
            "tm import query (heavy auto-derived stress)",
            query_elapsed_ms,
            query_budget_ms,
            f"entries={count}",
        )
        assert query_elapsed_ms <= query_budget_ms
        sources = {item.source_text for item in matches}
        assert "Drop all" in sources
        assert "Drop one" in sources
    finally:
        store.close()
