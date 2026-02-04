import gc
import os
import time
from pathlib import Path

from translationzed_py.core import SearchField, SearchRow, parse, parse_lazy, search
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parse_utils import _hash_key_u64
from translationzed_py.core.status_cache import write as write_cache


def _budget_ms(env_name: str, default_ms: float) -> float:
    raw = os.getenv(env_name, "")
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = default_ms
        return value
    return default_ms


def _write_entries(path: Path, count: int) -> None:
    lines = [f'KEY_{idx:05d} = "Value {idx}"' for idx in range(count)]
    data = "\n".join(lines) + "\n"
    path.write_text(data, encoding="utf-8")


def _make_entries(count: int) -> list[Entry]:
    entries: list[Entry] = []
    for idx in range(count):
        key = f"KEY_{idx:05d}"
        value = f"Value {idx}"
        entries.append(
            Entry(
                key,
                value,
                Status.UNTOUCHED,
                (0, len(value)),
                (len(value),),
                (),
                False,
                _hash_key_u64(key),
            )
        )
    return entries


def _assert_budget(label: str, elapsed_ms: float, budget_ms: float) -> None:
    assert (
        elapsed_ms <= budget_ms
    ), f"{label} exceeded budget: {elapsed_ms:.1f}ms > {budget_ms:.1f}ms"


def test_perf_large_file_open(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_OPEN_ENTRIES", "8000"))
    budget_ms = _budget_ms("TZP_PERF_OPEN_MS", 2000.0)
    path = tmp_path / "Large.txt"
    _write_entries(path, count)

    # warm OS cache and code paths
    parse_lazy(path, encoding="utf-8")
    gc.collect()

    start = time.perf_counter()
    pf = parse_lazy(path, encoding="utf-8")
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert len(pf.entries) == count
    perf_recorder("large-file open", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("large-file open", elapsed_ms, budget_ms)


def test_perf_multi_file_search(tmp_path: Path, perf_recorder) -> None:
    files = int(os.getenv("TZP_PERF_SEARCH_FILES", "4"))
    count = int(os.getenv("TZP_PERF_SEARCH_ENTRIES", "3000"))
    budget_ms = _budget_ms("TZP_PERF_SEARCH_MS", 2000.0)
    paths: list[Path] = []
    for idx in range(files):
        path = tmp_path / f"Search_{idx}.txt"
        _write_entries(path, count)
        paths.append(path)

    gc.collect()
    start = time.perf_counter()
    total = 0
    for path in paths:
        pf = parse(path, encoding="utf-8")
        rows = (
            SearchRow(path, row, entry.key, "", entry.value)
            for row, entry in enumerate(pf.entries)
        )
        total += len(search(rows, "Value", SearchField.TRANSLATION, False))
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert total == files * count
    perf_recorder(
        "multi-file search",
        elapsed_ms,
        budget_ms,
        f"files={files} entries={count} matches={total}",
    )
    _assert_budget("multi-file search", elapsed_ms, budget_ms)


def test_perf_cache_write(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_CACHE_ENTRIES", "8000"))
    budget_ms = _budget_ms("TZP_PERF_CACHE_MS", 1500.0)
    root = tmp_path / "root"
    file_path = root / "EN" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    entries = _make_entries(count)
    changed_keys = {entry.key for entry in entries}

    gc.collect()
    start = time.perf_counter()
    write_cache(root, file_path, entries, changed_keys=changed_keys)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    cache_path = root / ".tzp-cache" / "EN" / "ui.bin"
    assert cache_path.exists()
    perf_recorder("cache write", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("cache write", elapsed_ms, budget_ms)
