import gc
import os
import time
from pathlib import Path

from translationzed_py.core import SearchField, SearchRow, parse, parse_lazy, search
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parse_utils import _hash_key_u64
from translationzed_py.core.status_cache import (
    read as read_cache,
)
from translationzed_py.core.status_cache import (
    read_has_drafts_from_path as read_has_drafts,
)
from translationzed_py.core.status_cache import (
    write as write_cache,
)


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


def _write_entries_with_long(path: Path, count: int, long_len: int) -> None:
    lines = [f'KEY_{idx:05d} = "Value {idx}"' for idx in range(count - 1)]
    long_value = "A" * max(1, long_len)
    lines.append(f'KEY_{count - 1:05d} = "{long_value}"')
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


def test_perf_parse_eager(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_EAGER_ENTRIES", "4000"))
    budget_ms = _budget_ms("TZP_PERF_EAGER_MS", 2000.0)
    path = tmp_path / "Eager.txt"
    _write_entries(path, count)

    gc.collect()
    start = time.perf_counter()
    pf = parse(path, encoding="utf-8")
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert len(pf.entries) == count
    perf_recorder("parse eager", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("parse eager", elapsed_ms, budget_ms)


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
    cache_path = root / ".tzp" / "cache" / "EN" / "ui.bin"
    assert cache_path.exists()
    perf_recorder("cache write", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("cache write", elapsed_ms, budget_ms)


def test_perf_cache_read(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_CACHE_READ_ENTRIES", "8000"))
    budget_ms = _budget_ms("TZP_PERF_CACHE_READ_MS", 1500.0)
    root = tmp_path / "root"
    file_path = root / "EN" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    entries = _make_entries(count)
    changed_keys = {entry.key for entry in entries}
    write_cache(root, file_path, entries, changed_keys=changed_keys)

    gc.collect()
    start = time.perf_counter()
    cache_map = read_cache(root, file_path)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert len(cache_map) == count
    perf_recorder("cache read", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("cache read", elapsed_ms, budget_ms)


def test_perf_cache_header_scan(tmp_path: Path, perf_recorder) -> None:
    files = int(os.getenv("TZP_PERF_CACHE_HEADER_FILES", "300"))
    budget_ms = _budget_ms("TZP_PERF_CACHE_HEADER_MS", 800.0)
    root = tmp_path / "root"
    entry = _make_entries(1)
    changed_keys = {entry[0].key}
    for idx in range(files):
        file_path = root / "EN" / f"file_{idx}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        write_cache(root, file_path, entry, changed_keys=changed_keys)
    cache_root = root / ".tzp" / "cache" / "EN"
    paths = list(cache_root.rglob("*.bin"))
    assert len(paths) == files

    gc.collect()
    start = time.perf_counter()
    hits = 0
    for path in paths:
        if read_has_drafts(path):
            hits += 1
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert hits == files
    perf_recorder("cache header scan", elapsed_ms, budget_ms, f"files={files}")
    _assert_budget("cache header scan", elapsed_ms, budget_ms)


def test_perf_lazy_prefetch(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_PREFETCH_ENTRIES", "8000"))
    window = int(os.getenv("TZP_PERF_PREFETCH_WINDOW", "400"))
    budget_ms = _budget_ms("TZP_PERF_PREFETCH_MS", 800.0)
    path = tmp_path / "Large.txt"
    _write_entries(path, count)
    pf = parse_lazy(path, encoding="utf-8")
    assert hasattr(pf.entries, "prefetch")
    window = max(1, min(window, count))

    gc.collect()
    start = time.perf_counter()
    pf.entries.prefetch(0, window - 1)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    perf_recorder(
        "lazy prefetch", elapsed_ms, budget_ms, f"entries={count} window={window}"
    )
    _assert_budget("lazy prefetch", elapsed_ms, budget_ms)


def test_perf_lazy_preview(tmp_path: Path, perf_recorder) -> None:
    length = int(os.getenv("TZP_PERF_PREVIEW_LEN", "200000"))
    limit = int(os.getenv("TZP_PERF_PREVIEW_LIMIT", "200"))
    budget_ms = _budget_ms("TZP_PERF_PREVIEW_MS", 50.0)
    path = tmp_path / "Preview.txt"
    long_value = "A" * max(1, length)
    path.write_text(f'KEY = "{long_value}"\n', encoding="utf-8")
    pf = parse_lazy(path, encoding="utf-8")
    entries = pf.entries
    assert hasattr(entries, "preview_at")

    gc.collect()
    start = time.perf_counter()
    preview = entries.preview_at(0, limit)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert preview == long_value[:limit]
    perf_recorder(
        "lazy preview",
        elapsed_ms,
        budget_ms,
        f"len={length} limit={limit}",
    )
    _assert_budget("lazy preview", elapsed_ms, budget_ms)


def test_perf_max_value_length(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_MAXLEN_ENTRIES", "20000"))
    long_len = int(os.getenv("TZP_PERF_MAXLEN_VALUE", "10000"))
    budget_ms = _budget_ms("TZP_PERF_MAXLEN_MS", 200.0)
    path = tmp_path / "MaxLen.txt"
    _write_entries_with_long(path, count, long_len)
    pf = parse_lazy(path, encoding="utf-8")
    entries = pf.entries
    assert hasattr(entries, "max_value_length")

    gc.collect()
    start = time.perf_counter()
    max_len = entries.max_value_length()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert max_len >= long_len
    perf_recorder(
        "max value length",
        elapsed_ms,
        budget_ms,
        f"entries={count} max_len={max_len}",
    )
    _assert_budget("max value length", elapsed_ms, budget_ms)


def test_perf_hash_index(tmp_path: Path, perf_recorder) -> None:
    count = int(os.getenv("TZP_PERF_HASH_INDEX_ENTRIES", "20000"))
    budget_ms = _budget_ms("TZP_PERF_HASH_INDEX_MS", 800.0)
    path = tmp_path / "Large.txt"
    _write_entries(path, count)
    pf = parse_lazy(path, encoding="utf-8")
    assert hasattr(pf.entries, "index_by_hash")

    gc.collect()
    start = time.perf_counter()
    index = pf.entries.index_by_hash(bits=64)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert index
    perf_recorder("hash index", elapsed_ms, budget_ms, f"entries={count}")
    _assert_budget("hash index", elapsed_ms, budget_ms)
