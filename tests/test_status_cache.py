import struct
import tempfile
from pathlib import Path

import xxhash

from translationzed_py.core import parse
from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import (
    CacheEntry,
    migrate_all,
    read,
    read_last_opened_from_path,
    write,
)


def test_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)  # proper ParsedFile
        # mutate frozen dataclass safely
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)

        write(root, path, pf.entries)
        cache_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
        assert cache_path.read_bytes().startswith(b"TZC5")
        assert list(read(root, path).values()) == [
            CacheEntry(Status.TRANSLATED, None, None)
        ]


def test_roundtrip_with_value_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
        object.__setattr__(pf.entries[0], "value", "Hello!")

        write(
            root,
            path,
            pf.entries,
            changed_keys={"GREETING"},
            original_values={"GREETING": "Hi"},
        )
        entry = list(read(root, path).values())[0]
        assert entry.status == Status.TRANSLATED
        assert entry.value == "Hello!"
        assert entry.original == "Hi"


def test_read_migrates_legacy_cache_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
        write(root, path, pf.entries)

        current_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
        legacy_path = root / ".tzp-cache" / "EN" / "dummy.bin"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.replace(legacy_path)

        cache = read(root, path)
        assert list(cache.values()) == [CacheEntry(Status.TRANSLATED, None, None)]
        assert current_path.exists()
        assert not legacy_path.exists()


def test_write_skips_empty_cache():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        write(root, path, pf.entries, changed_keys=set())
        cache_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
        assert not cache_path.exists()
        assert not (root / ".tzp" / "cache").exists()


def test_last_opened_written():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
        write(root, path, pf.entries, last_opened=123)
        cache_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
        assert read_last_opened_from_path(cache_path) == 123


def test_legacy_status_mapping_v3():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        cache_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        key_a = "HELLO"
        key_b = "REVIEW"
        hash_a = int(xxhash.xxh64(key_a.encode("utf-8")).intdigest()) & 0xFFFF
        hash_b = int(xxhash.xxh64(key_b.encode("utf-8")).intdigest()) & 0xFFFF

        header = struct.pack("<4sQI", b"TZC2", 0, 2)
        rec_a = struct.pack("<HBBII", hash_a, 1, 0, 0, 0)  # legacy TRANSLATED
        rec_b = struct.pack("<HBBII", hash_b, 3, 0, 0, 0)  # legacy FOR_REVIEW
        cache_path.write_bytes(header + rec_a + rec_b)

        cache = read(root, path)
        assert cache[hash_a].status == Status.TRANSLATED
        assert cache[hash_b].status == Status.FOR_REVIEW

        data = cache_path.read_bytes()
        assert data.startswith(b"TZC3")


def test_migrate_all_upgrades_u16_cache(tmp_path):
    root = tmp_path / "root"
    (root / "EN").mkdir(parents=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    path = root / "EN" / "dummy.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")

    cache_path = root / ".tzp" / "cache" / "EN" / "dummy.bin"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    key = "HELLO"
    key_hash = int(xxhash.xxh64(key.encode("utf-8")).intdigest()) & 0xFFFF
    header = struct.pack("<4sQI", b"TZC3", 0, 1)
    rec = struct.pack("<HBBII", key_hash, 2, 1, 2, 0) + b"Yo"
    cache_path.write_bytes(header + rec)

    migrated = migrate_all(root)
    assert migrated == 1
    data = cache_path.read_bytes()
    assert data.startswith(b"TZC5")
