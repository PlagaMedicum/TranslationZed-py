"""Test module for status cache helper branches."""

from __future__ import annotations

import struct
from pathlib import Path

from translationzed_py.core.app_config import LEGACY_CACHE_DIR, load as _load_app_config
from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import (
    _HEADER_V2,
    _MAGIC_V1,
    _cache_path,
    _hash_key,
    _legacy_cache_path,
    _original_path_from_cache,
    _read_rows_any,
    _status_from_byte,
    _write_rows,
    legacy_cache_paths,
    read,
    read_has_drafts_from_path,
    read_last_opened_from_path,
    touch_last_opened,
    write,
)


def _init_target_file(root: Path) -> Path:
    """Provide a standard cache target file path under EN locale."""
    target = root / "EN" / "ui.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('HELLO = "Hi"\n', encoding="utf-8")
    return target


def test_status_and_hash_helpers_cover_invalid_and_masked_paths() -> None:
    """Verify status conversion and hash masking helpers."""
    assert _status_from_byte(2, legacy=False) is Status.TRANSLATED
    assert _status_from_byte(99, legacy=False) is None
    assert _status_from_byte(3, legacy=True) is Status.FOR_REVIEW
    assert _status_from_byte(255, legacy=True) is None

    digest = 0x1234_5678_9ABC_DEF0
    assert _hash_key("ignored", bits=64, key_hash=digest) == digest
    assert _hash_key("ignored", bits=16, key_hash=digest) == 0xDEF0


def test_legacy_cache_paths_filters_new_formats_and_special_files(
    tmp_path: Path,
) -> None:
    """Verify legacy cache discovery excludes modern and hash-cache files."""
    root = tmp_path / "root"
    cfg = _load_app_config(root)

    current_root = root / cfg.cache_dir / "EN"
    legacy_root = root / LEGACY_CACHE_DIR / "EN"
    current_root.mkdir(parents=True, exist_ok=True)
    legacy_root.mkdir(parents=True, exist_ok=True)

    include_path = legacy_root / f"legacy{cfg.cache_ext}"
    include_path.write_bytes(b"ABCDpayload")

    skip_modern = current_root / f"modern{cfg.cache_ext}"
    skip_modern.write_bytes(b"TZC4xxxx")

    skip_empty = current_root / f"empty{cfg.cache_ext}"
    skip_empty.write_bytes(b"")

    skip_hash = root / cfg.cache_dir / cfg.en_hash_filename
    skip_hash.parent.mkdir(parents=True, exist_ok=True)
    skip_hash.write_bytes(b"ABCD")

    paths = legacy_cache_paths(root)
    assert include_path in paths
    assert skip_modern not in paths
    assert skip_empty not in paths
    assert skip_hash not in paths


def test_read_rows_any_parses_v5_and_legacy_payloads(tmp_path: Path) -> None:
    """Verify row parser handles modern and legacy cache payload formats."""
    cache_file = tmp_path / "rows.bin"
    rows = [(0x1234, Status.TRANSLATED, "value", "original")]
    _write_rows(cache_file, rows, 77, hash_bits=64)

    parsed = _read_rows_any(cache_file.read_bytes())
    assert parsed is not None
    assert parsed.hash_bits == 64
    assert parsed.legacy_status is False
    assert parsed.last_opened == 77
    assert parsed.has_drafts is True
    assert parsed.rows[0][2] == "value"
    assert parsed.rows[0][3] == "original"

    legacy = struct.pack("<IHB", 1, 0x0042, 1)
    parsed_legacy = _read_rows_any(legacy)
    assert parsed_legacy is not None
    assert parsed_legacy.legacy_status is True
    assert parsed_legacy.hash_bits == 16
    assert parsed_legacy.rows[0][0] == 0x0042
    assert parsed_legacy.rows[0][1] is Status.TRANSLATED

    assert _read_rows_any(b"") is None
    assert _read_rows_any(b"\x01\x00\x00") is None


def test_last_opened_and_has_drafts_handle_multiple_header_styles(tmp_path: Path) -> None:
    """Verify header readers support V5 and fallback legacy V1 metadata."""
    v5_with_drafts = tmp_path / "with_drafts.bin"
    _write_rows(v5_with_drafts, [(1, Status.TRANSLATED, "x", None)], 123, hash_bits=64)
    assert read_last_opened_from_path(v5_with_drafts) == 123
    assert read_has_drafts_from_path(v5_with_drafts) is True

    v5_without_drafts = tmp_path / "without_drafts.bin"
    _write_rows(v5_without_drafts, [(1, Status.TRANSLATED, None, None)], 9, hash_bits=64)
    assert read_has_drafts_from_path(v5_without_drafts) is False

    v1_with_last_opened = tmp_path / "v1_header.bin"
    v1_with_last_opened.write_bytes(_HEADER_V2.pack(_MAGIC_V1, 17, 0))
    assert read_last_opened_from_path(v1_with_last_opened) == 17

    invalid = tmp_path / "invalid.bin"
    invalid.write_bytes(b"BAD!")
    assert read_last_opened_from_path(invalid) == 0
    assert read_has_drafts_from_path(invalid) is False


def test_touch_last_opened_migrates_from_legacy_to_current(tmp_path: Path) -> None:
    """Verify touch operation rewrites cache into current cache directory."""
    root = tmp_path / "root"
    file_path = _init_target_file(root)
    legacy_path = _legacy_cache_path(root, file_path)
    current_path = _cache_path(root, file_path)

    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(legacy_path, [(7, Status.PROOFREAD, "draft", None)], 1, hash_bits=16)

    assert touch_last_opened(root, file_path, 999) is True
    assert current_path.exists() is True
    assert read_last_opened_from_path(current_path) == 999
    assert legacy_path.exists() is False

    missing_file = root / "EN" / "missing.txt"
    assert touch_last_opened(root, missing_file, 5) is False


def test_original_path_resolution_and_empty_write_cleanup(tmp_path: Path) -> None:
    """Verify cache-to-original mapping and empty-write cleanup paths."""
    root = tmp_path / "root"
    file_path = _init_target_file(root)
    current_path = _cache_path(root, file_path)
    legacy_path = _legacy_cache_path(root, file_path)

    assert _original_path_from_cache(root, current_path) == file_path

    cfg = _load_app_config(root)
    en_hash_cache = root / cfg.cache_dir / cfg.en_hash_filename
    assert _original_path_from_cache(root, en_hash_cache) is None
    assert _original_path_from_cache(root, tmp_path / "outside.bin") is None

    current_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(b"current")
    legacy_path.write_bytes(b"legacy")

    write(root, file_path, [])
    assert current_path.exists() is False
    assert legacy_path.exists() is False

    current_path.write_bytes(b"not a cache")
    assert read(root, file_path) == {}
