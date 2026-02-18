"""Test module for status-cache edge branches and guard-path behavior."""

from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace

from translationzed_py.core.model import Entry, Status
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.status_cache import (
    LEGACY_CACHE_DIR,
    _HEADER_V1,
    _HEADER_V2,
    _HEADER_V5,
    _MAGIC_V1,
    _MAGIC_V2,
    _MAGIC_V3,
    _MAGIC_V4,
    _MAGIC_V5,
    _cache_roots,
    _migrate_cache_path,
    _original_path_from_cache,
    _read_rows_any,
    cache_path,
    migrate_all,
    migrate_paths,
    read_has_drafts_from_path,
    read_last_opened_from_path,
    write,
)


def _cfg(
    *,
    cache_dir: str = ".tzp/cache",
    cache_ext: str = ".bin",
    translation_ext: str = ".txt",
    en_hash_filename: str = "en_hashes.bin",
) -> SimpleNamespace:
    """Create app-config-like object for monkeypatching status-cache helpers."""
    return SimpleNamespace(
        cache_dir=cache_dir,
        cache_ext=cache_ext,
        translation_ext=translation_ext,
        en_hash_filename=en_hash_filename,
    )


def _entry(key: str, value: str, status: Status) -> Entry:
    """Create minimal cache entry object for write() tests."""
    return Entry(key, value, status, (0, 0), (), (), False, None)


def test_cache_root_and_original_path_edge_cases(monkeypatch, tmp_path: Path) -> None:
    """Verify cache root/path helpers handle legacy-equals-current and empty rel paths."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(
        "translationzed_py.core.status_cache._load_app_config",
        lambda _root: _cfg(cache_dir=LEGACY_CACHE_DIR),
    )

    roots = _cache_roots(root)
    assert roots == (root / LEGACY_CACHE_DIR,)
    assert cache_path(root, root / "EN" / "ui.txt").name.endswith(".bin")
    assert _original_path_from_cache(root, root / LEGACY_CACHE_DIR) is None


def test_migrate_cache_path_guard_returns_cover_failure_conditions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Verify migration helper returns False for all guard/failure branches."""
    root = tmp_path / "root"
    root.mkdir()
    locale_dir = root / "EN"
    locale_dir.mkdir()
    source = locale_dir / "ui.txt"
    source.write_text('HELLO = "Hi"\n', encoding="utf-8")
    cache = root / ".tzp" / "cache" / "EN" / "ui.bin"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(b"cache")
    locales = {
        "EN": LocaleMeta(code="EN", path=locale_dir, display_name="EN", charset="utf-8")
    }

    parsed_16 = SimpleNamespace(hash_bits=16, last_opened=0, rows=[])

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", lambda _self: (_ for _ in ()).throw(OSError("x")))
        assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr(
        "translationzed_py.core.status_cache._read_rows_any",
        lambda _data: SimpleNamespace(hash_bits=64, rows=[]),
    )
    assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr("translationzed_py.core.status_cache._read_rows_any", lambda _data: parsed_16)
    monkeypatch.setattr(
        "translationzed_py.core.status_cache._original_path_from_cache",
        lambda _root, _cache: None,
    )
    assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr(
        "translationzed_py.core.status_cache._original_path_from_cache",
        lambda _root, _cache: root / "EN" / "missing.txt",
    )
    assert _migrate_cache_path(root, cache, locales) is False

    outside = tmp_path / "outside.txt"
    outside.write_text('OUT = "x"\n', encoding="utf-8")
    monkeypatch.setattr(
        "translationzed_py.core.status_cache._original_path_from_cache",
        lambda _root, _cache: outside,
    )
    assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr(
        "translationzed_py.core.status_cache._original_path_from_cache",
        lambda _root, _cache: root,
    )
    assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr(
        "translationzed_py.core.status_cache._original_path_from_cache",
        lambda _root, _cache: source,
    )
    monkeypatch.setattr(
        "translationzed_py.core.status_cache._read_rows_any",
        lambda _data: SimpleNamespace(
            hash_bits=16,
            last_opened=0,
            rows=[(123, Status.TRANSLATED, None, None)],
        ),
    )
    monkeypatch.setattr(
        "translationzed_py.core.parse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("parse-fail")),
    )
    assert _migrate_cache_path(root, cache, locales) is False

    monkeypatch.setattr(
        "translationzed_py.core.status_cache._read_rows_any",
        lambda _data: SimpleNamespace(
            hash_bits=16,
            last_opened=0,
            rows=[(999_999, Status.TRANSLATED, None, None)],
        ),
    )
    assert _migrate_cache_path(root, cache, locales) is False


def test_migrate_paths_and_all_cover_skip_and_empty_legacy_sets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Verify path migration skips hash cache files and handles empty legacy sets."""
    root = tmp_path / "root"
    root.mkdir()
    cfg = _cfg(en_hash_filename="hash.bin")
    calls: list[Path] = []

    monkeypatch.setattr("translationzed_py.core.status_cache._load_app_config", lambda _root: cfg)
    monkeypatch.setattr(
        "translationzed_py.core.status_cache._migrate_cache_path",
        lambda _root, path, _locales: calls.append(path) or False,
    )

    migrated = migrate_paths(
        root,
        {},
        [root / "hash.bin", root / "a.bin", root / "b.bin"],
    )
    assert migrated == 0
    assert calls == [root / "a.bin", root / "b.bin"]

    monkeypatch.setattr("translationzed_py.core.status_cache.legacy_cache_paths", lambda _root: [])
    monkeypatch.setattr("translationzed_py.core.project_scanner.scan_root", lambda _root: {"EN": object()})
    assert migrate_all(root, locales=None) == 0


def test_read_rows_any_truncated_magic_branches_and_legacy_status_skip() -> None:
    """Verify row parser returns None for truncated headers and skips invalid legacy statuses."""
    bad_v5 = _HEADER_V5.pack(_MAGIC_V5, 0, 1, 0)
    assert _read_rows_any(bad_v5) is None

    bad_v4 = _HEADER_V2.pack(_MAGIC_V4, 0, 1)
    bad_v3 = _HEADER_V2.pack(_MAGIC_V3, 0, 1)
    bad_v2 = _HEADER_V2.pack(_MAGIC_V2, 0, 1)
    assert _read_rows_any(bad_v4) is None
    assert _read_rows_any(bad_v3) is None
    assert _read_rows_any(bad_v2) is None

    # Force both V1 parsing attempts to fail and fall through to final `None`.
    bad_v1 = _HEADER_V2.pack(_MAGIC_V1, 2, 2)
    assert _read_rows_any(bad_v1) is None

    legacy_invalid_status = struct.pack("<IHB", 1, 0x1234, 255)
    parsed = _read_rows_any(legacy_invalid_status)
    assert parsed is not None
    assert parsed.rows == []


def test_readers_cover_header_fallback_and_oserror_paths(monkeypatch, tmp_path: Path) -> None:
    """Verify header readers hit OSError, short-header, unknown-magic, and fallback cases."""
    missing = tmp_path / "missing.bin"
    assert read_last_opened_from_path(missing) == 0
    assert read_has_drafts_from_path(missing) is False

    v5_short = tmp_path / "v5-short.bin"
    v5_short.write_bytes(_MAGIC_V5)
    assert read_last_opened_from_path(v5_short) == 0
    assert read_has_drafts_from_path(v5_short) is False

    v4_short = tmp_path / "v4-short.bin"
    v4_short.write_bytes(_MAGIC_V4)
    assert read_last_opened_from_path(v4_short) == 0

    v3_short = tmp_path / "v3-short.bin"
    v3_short.write_bytes(_MAGIC_V3)
    assert read_last_opened_from_path(v3_short) == 0

    v2_short = tmp_path / "v2-short.bin"
    v2_short.write_bytes(_MAGIC_V2)
    assert read_last_opened_from_path(v2_short) == 0

    unknown = tmp_path / "unknown.bin"
    unknown.write_bytes(b"NOPE")
    assert read_last_opened_from_path(unknown) == 0

    v1_header_only = tmp_path / "v1-header.bin"
    v1_header_only.write_bytes(_HEADER_V1.pack(_MAGIC_V1, 7))
    assert read_last_opened_from_path(v1_header_only) == 0

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", lambda _self: (_ for _ in ()).throw(OSError("boom")))
        assert read_has_drafts_from_path(unknown) is False

    unparsable = tmp_path / "unparsable.bin"
    unparsable.write_bytes(b"BAD-CACHE")
    assert read_has_drafts_from_path(unparsable) is False


def test_write_suppresses_legacy_unlink_oserror(monkeypatch, tmp_path: Path) -> None:
    """Verify write suppresses OSError when removing legacy cache file after write."""
    root = tmp_path / "root"
    file_path = root / "EN" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('HELLO = "Hi"\n', encoding="utf-8")

    legacy = root / LEGACY_CACHE_DIR / "EN" / "ui.bin"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"legacy")

    original_unlink = Path.unlink

    def _unlink(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == legacy:
            raise OSError("deny unlink")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _unlink)

    write(root, file_path, [_entry("HELLO", "Hi", Status.TRANSLATED)])
