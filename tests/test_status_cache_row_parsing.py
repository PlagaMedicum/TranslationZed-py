"""Test module for status cache row parsing and header behavior."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import (
    _HEADER_V1,
    _HEADER_V2,
    _MAGIC_V1,
    _MAGIC_V2,
    _MAGIC_V3,
    _MAGIC_V4,
    _MAGIC_V5,
    _RECORD_V2,
    _RECORD_V3,
    _RECORD_V4,
    _cache_path,
    _parse_rows_v2,
    _parse_rows_v3,
    _parse_rows_v4,
    _read_rows_any,
    _write_rows,
    read_has_drafts_from_path,
    read_last_opened_from_path,
    touch_last_opened,
)


def _init_cache_target(root: Path) -> Path:
    """Create a minimal project file used for per-file cache tests."""
    target = root / "EN" / "ui.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('HELLO = "Hi"\n', encoding="utf-8")
    return target


def test_parse_rows_v2_handles_valid_invalid_and_truncated_records() -> None:
    """Verify V2 row parser handles valid, skipped, and malformed records."""
    valid = _RECORD_V2.pack(11, 1, 0x1, 3) + b"abc"
    invalid = _RECORD_V2.pack(12, 255, 0x0, 0)
    rows = _parse_rows_v2(valid + invalid, offset=0, count=2, legacy=True)
    assert rows == [(11, Status.TRANSLATED, "abc", None)]

    assert (
        _parse_rows_v2(valid[: _RECORD_V2.size - 1], offset=0, count=1, legacy=True)
        is None
    )
    truncated_value = _RECORD_V2.pack(13, 1, 0x1, 5) + b"ab"
    assert _parse_rows_v2(truncated_value, offset=0, count=1, legacy=True) is None


def test_parse_rows_v3_handles_original_and_truncation_paths() -> None:
    """Verify V3 row parser decodes value/original and guards malformed input."""
    valid = _RECORD_V3.pack(21, 2, 0x3, 2, 3) + b"ok" + b"old"
    invalid = _RECORD_V3.pack(22, 255, 0x0, 0, 0)
    rows = _parse_rows_v3(valid + invalid, offset=0, count=2, legacy=False)
    assert rows == [(21, Status.TRANSLATED, "ok", "old")]

    assert (
        _parse_rows_v3(valid[: _RECORD_V3.size - 1], offset=0, count=1, legacy=False)
        is None
    )
    truncated_value = _RECORD_V3.pack(23, 1, 0x1, 4, 0) + b"ab"
    assert _parse_rows_v3(truncated_value, offset=0, count=1, legacy=False) is None
    truncated_original = _RECORD_V3.pack(24, 1, 0x2, 0, 4) + b"ab"
    assert _parse_rows_v3(truncated_original, offset=0, count=1, legacy=False) is None


def test_parse_rows_v4_handles_u64_keys_and_malformed_input() -> None:
    """Verify V4 row parser supports 64-bit keys and truncation checks."""
    valid = _RECORD_V4.pack(31, 3, 0x3, 3, 2) + b"new" + b"ol"
    invalid = _RECORD_V4.pack(32, 255, 0x0, 0, 0)
    rows = _parse_rows_v4(valid + invalid, offset=0, count=2, legacy=False)
    assert rows == [(31, Status.PROOFREAD, "new", "ol")]

    assert (
        _parse_rows_v4(valid[: _RECORD_V4.size - 1], offset=0, count=1, legacy=False)
        is None
    )
    truncated_value = _RECORD_V4.pack(33, 1, 0x1, 4, 0) + b"ab"
    assert _parse_rows_v4(truncated_value, offset=0, count=1, legacy=False) is None
    truncated_original = _RECORD_V4.pack(34, 1, 0x2, 0, 4) + b"ab"
    assert _parse_rows_v4(truncated_original, offset=0, count=1, legacy=False) is None


def test_read_rows_any_parses_all_supported_header_versions(tmp_path: Path) -> None:
    """Verify generic row reader supports V5/V4/V3/V2/V1 payload variants."""
    rows64 = [(1001, Status.TRANSLATED, "draft", "orig")]
    rows16 = [(42, Status.PROOFREAD, "x", None)]

    v5_path = tmp_path / "v5.bin"
    _write_rows(v5_path, rows64, 7, hash_bits=64, magic=_MAGIC_V5)
    parsed_v5 = _read_rows_any(v5_path.read_bytes())
    assert parsed_v5 is not None
    assert parsed_v5.magic == _MAGIC_V5
    assert parsed_v5.last_opened == 7
    assert parsed_v5.hash_bits == 64
    assert parsed_v5.has_drafts is True

    v4_path = tmp_path / "v4.bin"
    _write_rows(v4_path, rows64, 9, hash_bits=64, magic=_MAGIC_V4)
    parsed_v4 = _read_rows_any(v4_path.read_bytes())
    assert parsed_v4 is not None
    assert parsed_v4.magic == _MAGIC_V4
    assert parsed_v4.hash_bits == 64

    v3_path = tmp_path / "v3.bin"
    _write_rows(v3_path, rows16, 11, hash_bits=16, magic=_MAGIC_V3)
    parsed_v3 = _read_rows_any(v3_path.read_bytes())
    assert parsed_v3 is not None
    assert parsed_v3.magic == _MAGIC_V3
    assert parsed_v3.hash_bits == 16
    assert parsed_v3.legacy_status is False

    v2_path = tmp_path / "v2.bin"
    _write_rows(v2_path, rows16, 13, hash_bits=16, magic=_MAGIC_V2)
    parsed_v2 = _read_rows_any(v2_path.read_bytes())
    assert parsed_v2 is not None
    assert parsed_v2.magic == _MAGIC_V2
    assert parsed_v2.legacy_status is True

    v1_v2_header = _HEADER_V2.pack(_MAGIC_V1, 15, 1) + _RECORD_V2.pack(9, 1, 0, 0)
    parsed_v1_with_last_opened = _read_rows_any(v1_v2_header)
    assert parsed_v1_with_last_opened is not None
    assert parsed_v1_with_last_opened.last_opened == 15
    assert parsed_v1_with_last_opened.legacy_status is True

    v1_v1_header = _HEADER_V1.pack(_MAGIC_V1, 0)
    parsed_v1_header = _read_rows_any(v1_v1_header)
    assert parsed_v1_header is not None
    assert parsed_v1_header.last_opened == 0
    assert parsed_v1_header.rows == []


def test_header_readers_cover_legacy_and_short_payload_paths(tmp_path: Path) -> None:
    """Verify header readers support non-V5 payloads and short invalid files."""
    v4 = tmp_path / "legacy_v4.bin"
    _write_rows(
        v4, [(1, Status.TRANSLATED, "draft", None)], 22, hash_bits=64, magic=_MAGIC_V4
    )
    assert read_last_opened_from_path(v4) == 22
    assert read_has_drafts_from_path(v4) is True

    v3 = tmp_path / "legacy_v3.bin"
    _write_rows(
        v3, [(2, Status.TRANSLATED, None, None)], 33, hash_bits=16, magic=_MAGIC_V3
    )
    assert read_last_opened_from_path(v3) == 33
    assert read_has_drafts_from_path(v3) is False

    v2 = tmp_path / "legacy_v2.bin"
    _write_rows(
        v2, [(3, Status.TRANSLATED, None, None)], 44, hash_bits=16, magic=_MAGIC_V2
    )
    assert read_last_opened_from_path(v2) == 44

    short_v5 = tmp_path / "short_v5.bin"
    short_v5.write_bytes(_MAGIC_V5)
    assert read_last_opened_from_path(short_v5) == 0
    assert read_has_drafts_from_path(short_v5) is False


def test_touch_last_opened_upgrades_legacy_magic_and_rejects_invalid(
    tmp_path: Path,
) -> None:
    """Verify touching cache timestamps upgrades V4 magic and handles failures."""
    root = tmp_path / "root"
    target_file = _init_cache_target(root)
    status_file = _cache_path(root, target_file)
    status_file.parent.mkdir(parents=True, exist_ok=True)

    _write_rows(
        status_file,
        [(7, Status.FOR_REVIEW, "draft", None)],
        5,
        hash_bits=64,
        magic=_MAGIC_V4,
    )
    assert touch_last_opened(root, target_file, 99) is True
    data = status_file.read_bytes()
    assert data.startswith(_MAGIC_V5)
    assert read_last_opened_from_path(status_file) == 99

    status_file.write_bytes(b"invalid-cache")
    assert touch_last_opened(root, target_file, 111) is False
