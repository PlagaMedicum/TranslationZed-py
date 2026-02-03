from __future__ import annotations

import contextlib
import struct
from dataclasses import dataclass
from pathlib import Path

import xxhash

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.atomic_io import write_bytes_atomic
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.project_scanner import LocaleMeta

_MAGIC_V1 = b"TZC1"
_MAGIC_V2 = b"TZC2"
_MAGIC_V3 = b"TZC3"
_MAGIC_V4 = b"TZC4"
_HEADER_V1 = struct.Struct("<4sI")
_HEADER_V2 = struct.Struct("<4sQI")
_RECORD_V2 = struct.Struct("<HBBI")
_RECORD_V3 = struct.Struct("<HBBII")
_RECORD_V4 = struct.Struct("<QBBII")


@dataclass(frozen=True, slots=True)
class CacheEntry:
    status: Status
    value: str | None
    original: str | None = None


class CacheMap(dict[int, CacheEntry]):
    __slots__ = ("hash_bits", "legacy_status", "last_opened", "magic")

    def __init__(
        self,
        *args: object,
        hash_bits: int = 64,
        legacy_status: bool = False,
        last_opened: int = 0,
        magic: bytes = b"",
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.hash_bits = hash_bits
        self.legacy_status = legacy_status
        self.last_opened = last_opened
        self.magic = magic


_LEGACY_STATUS_MAP = {
    0: Status.UNTOUCHED,
    1: Status.TRANSLATED,
    2: Status.PROOFREAD,
    3: Status.FOR_REVIEW,
}


@dataclass(frozen=True, slots=True)
class _CacheRows:
    last_opened: int
    rows: list[tuple[int, Status, str | None, str | None]]
    legacy_status: bool
    hash_bits: int
    magic: bytes


def _status_from_byte(status_byte: int, *, legacy: bool) -> Status | None:
    if legacy:
        return _LEGACY_STATUS_MAP.get(status_byte)
    try:
        return Status(status_byte)
    except ValueError:
        return None


def _hash_key(key: str, *, bits: int = 64) -> int:
    digest = int(xxhash.xxh64(key.encode("utf-8")).intdigest())
    if bits == 16:
        return digest & 0xFFFF
    return digest & 0xFFFFFFFFFFFFFFFF


def _cache_path(root: Path, file_path: Path) -> Path:
    cfg = _load_app_config(root)
    rel = file_path.relative_to(root)
    rel_cache = rel.parent / f"{rel.stem}{cfg.cache_ext}"
    return root / cfg.cache_dir / rel_cache


def cache_path(root: Path, file_path: Path) -> Path:
    return _cache_path(root, file_path)


def _original_path_from_cache(root: Path, cache_path: Path) -> Path | None:
    cfg = _load_app_config(root)
    cache_root = root / cfg.cache_dir
    try:
        rel = cache_path.relative_to(cache_root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    if rel.name == cfg.en_hash_filename:
        return None
    return (root / rel).with_suffix(cfg.translation_ext)


def legacy_cache_paths(root: Path) -> list[Path]:
    cfg = _load_app_config(root)
    cache_root = root / cfg.cache_dir
    if not cache_root.exists():
        return []
    out: list[Path] = []
    for cache_path in cache_root.rglob(f"*{cfg.cache_ext}"):
        if cache_path.name == cfg.en_hash_filename:
            continue
        try:
            with cache_path.open("rb") as handle:
                head = handle.read(4)
        except OSError:
            continue
        if not head:
            continue
        if head == _MAGIC_V4:
            continue
        out.append(cache_path)
    return out


def _migrate_cache_path(
    root: Path, cache_path: Path, locales: dict[str, LocaleMeta]
) -> bool:
    try:
        data = cache_path.read_bytes()
    except OSError:
        return False
    parsed = _read_rows_any(data)
    if not parsed or parsed.hash_bits == 64:
        return False
    original = _original_path_from_cache(root, cache_path)
    if not original or not original.exists():
        return False
    try:
        rel = original.relative_to(root)
    except ValueError:
        return False
    if not rel.parts:
        return False
    locale = rel.parts[0]
    meta = locales.get(locale)
    if not meta:
        return False
    try:
        from translationzed_py.core import parse

        pf = parse(original, encoding=meta.charset)
    except Exception:
        return False
    legacy_map = {
        key_hash: CacheEntry(status, value, original_value)
        for key_hash, status, value, original_value in parsed.rows
    }
    rows: list[tuple[int, Status, str | None, str | None]] = []
    for entry in pf.entries:
        key16 = _hash_key(entry.key, bits=16)
        rec = legacy_map.get(key16)
        if rec is None:
            continue
        rows.append(
            (_hash_key(entry.key, bits=64), rec.status, rec.value, rec.original)
        )
    if not rows:
        return False
    _write_rows(cache_path, rows, parsed.last_opened, hash_bits=64)
    return True


def migrate_paths(root: Path, locales: dict[str, LocaleMeta], paths: list[Path]) -> int:
    cfg = _load_app_config(root)
    migrated = 0
    for cache_path in paths:
        if cache_path.name == cfg.en_hash_filename:
            continue
        if _migrate_cache_path(root, cache_path, locales):
            migrated += 1
    return migrated


def migrate_all(root: Path, locales: dict[str, LocaleMeta] | None = None) -> int:
    if locales is None:
        from translationzed_py.core.project_scanner import scan_root

        locales = scan_root(root)
    paths = legacy_cache_paths(root)
    if not paths:
        return 0
    return migrate_paths(root, locales, paths)


def _parse_rows_v2(
    data: bytes, *, offset: int, count: int, legacy: bool
) -> list[tuple[int, Status, str | None, str | None]] | None:
    rows: list[tuple[int, Status, str | None, str | None]] = []
    for _ in range(count):
        if offset + _RECORD_V2.size > len(data):
            return None
        key_hash, status_byte, flags, value_len = _RECORD_V2.unpack_from(data, offset)
        offset += _RECORD_V2.size
        value: str | None = None
        if flags & 0x1:
            end = offset + value_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            value = raw.decode("utf-8", errors="replace")
        status = _status_from_byte(status_byte, legacy=legacy)
        if status is None:
            continue
        rows.append((key_hash, status, value, None))
    return rows


def _parse_rows_v3(
    data: bytes, *, offset: int, count: int, legacy: bool
) -> list[tuple[int, Status, str | None, str | None]] | None:
    rows: list[tuple[int, Status, str | None, str | None]] = []
    for _ in range(count):
        if offset + _RECORD_V3.size > len(data):
            return None
        key_hash, status_byte, flags, value_len, original_len = _RECORD_V3.unpack_from(
            data, offset
        )
        offset += _RECORD_V3.size
        value: str | None = None
        original: str | None = None
        if flags & 0x1:
            end = offset + value_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            value = raw.decode("utf-8", errors="replace")
        if flags & 0x2:
            end = offset + original_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            original = raw.decode("utf-8", errors="replace")
        status = _status_from_byte(status_byte, legacy=legacy)
        if status is None:
            continue
        rows.append((key_hash, status, value, original))
    return rows


def _parse_rows_v4(
    data: bytes, *, offset: int, count: int, legacy: bool
) -> list[tuple[int, Status, str | None, str | None]] | None:
    rows: list[tuple[int, Status, str | None, str | None]] = []
    for _ in range(count):
        if offset + _RECORD_V4.size > len(data):
            return None
        key_hash, status_byte, flags, value_len, original_len = _RECORD_V4.unpack_from(
            data, offset
        )
        offset += _RECORD_V4.size
        value: str | None = None
        original: str | None = None
        if flags & 0x1:
            end = offset + value_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            value = raw.decode("utf-8", errors="replace")
        if flags & 0x2:
            end = offset + original_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            original = raw.decode("utf-8", errors="replace")
        status = _status_from_byte(status_byte, legacy=legacy)
        if status is None:
            continue
        rows.append((key_hash, status, value, original))
    return rows


def _read_rows_any(data: bytes) -> _CacheRows | None:
    if not data:
        return None
    if data.startswith(_MAGIC_V4):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V4:
                parsed_rows = _parse_rows_v4(
                    data, offset=_HEADER_V2.size, count=count, legacy=False
                )
                if parsed_rows is not None:
                    return _CacheRows(last_opened, parsed_rows, False, 64, magic)
        return None
    if data.startswith(_MAGIC_V3):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V3:
                parsed_rows = _parse_rows_v3(
                    data, offset=_HEADER_V2.size, count=count, legacy=False
                )
                if parsed_rows is not None:
                    return _CacheRows(last_opened, parsed_rows, False, 16, magic)
        return None
    if data.startswith(_MAGIC_V2):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V2:
                parsed_rows = _parse_rows_v3(
                    data, offset=_HEADER_V2.size, count=count, legacy=True
                )
                if parsed_rows is not None:
                    return _CacheRows(last_opened, parsed_rows, True, 16, magic)
        return None
    if data.startswith(_MAGIC_V1):
        # v2 header: magic + u64 last_opened + u32 count
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V1:
                parsed_rows = _parse_rows_v2(
                    data, offset=_HEADER_V2.size, count=count, legacy=True
                )
                if parsed_rows is not None:
                    return _CacheRows(last_opened, parsed_rows, True, 16, magic)
        # v1 header: magic + u32 count
        if len(data) >= _HEADER_V1.size:
            magic, count = _HEADER_V1.unpack_from(data, 0)
            if magic == _MAGIC_V1:
                parsed_rows = _parse_rows_v2(
                    data, offset=_HEADER_V1.size, count=count, legacy=True
                )
                if parsed_rows is not None:
                    return _CacheRows(0, parsed_rows, True, 16, magic)
        return None

    # --- legacy (status-only) format ---
    if len(data) < 4:
        return None
    (count,) = struct.unpack_from("<I", data, 0)
    expected = 4 + (count * struct.calcsize("<HB"))
    if len(data) < expected:
        return None
    offset = 4
    legacy_rows: list[tuple[int, Status, str | None, str | None]] = []
    for _ in range(count):
        key_hash, status_byte = struct.unpack_from("<HB", data, offset)
        offset += struct.calcsize("<HB")
        status = _status_from_byte(status_byte, legacy=True)
        if status is None:
            continue
        legacy_rows.append((key_hash, status, None, None))
    return _CacheRows(0, legacy_rows, True, 16, _MAGIC_V1)


def read(root: Path, file_path: Path) -> CacheMap:
    """
    Read per-file cache, returning a mapping { key_hash: CacheEntry }.
    Missing or corrupt files are ignored.
    """
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
        parsed = _read_rows_any(data)
        if not parsed:
            return CacheMap()
        out = CacheMap(
            hash_bits=parsed.hash_bits,
            legacy_status=parsed.legacy_status,
            last_opened=int(parsed.last_opened or 0),
            magic=parsed.magic,
        )
        for key_hash, status, value, original in parsed.rows:
            out[key_hash] = CacheEntry(status, value, original)
        if (
            parsed.legacy_status
            and parsed.hash_bits == 16
            and parsed.magic != _MAGIC_V3
        ):
            with contextlib.suppress(OSError):
                _write_rows(
                    status_file,
                    parsed.rows,
                    parsed.last_opened,
                    hash_bits=16,
                    magic=_MAGIC_V3,
                )
        return out
    except (OSError, struct.error):
        return CacheMap()


def write(
    root: Path,
    file_path: Path,
    entries: list[Entry],
    *,
    changed_keys: set[str] | None = None,
    last_opened: int | None = None,
    original_values: dict[str, str] | None = None,
    force_original: set[str] | None = None,
) -> None:
    """
    Write current in-memory statuses and (optional) draft translations into
    per-file cache. Values are stored only for keys in `changed_keys`.
    """
    status_file = _cache_path(root, file_path)
    changed_keys = changed_keys or set()
    rows: list[tuple[int, Status, str | None, str | None]] = []
    original_values = original_values or {}
    force_original = force_original or set()
    existing: CacheMap | dict[int, CacheEntry] = {}
    existing_hash_bits = 64
    if changed_keys and status_file.exists():
        existing = read(root, file_path)
        existing_hash_bits = getattr(existing, "hash_bits", 64)
    for e in entries:
        include = e.status != Status.UNTOUCHED or e.key in changed_keys
        if not include:
            continue
        value = e.value if e.key in changed_keys else None
        original: str | None = None
        if e.key in changed_keys:
            prev = existing.get(_hash_key(e.key, bits=existing_hash_bits))
            if prev and prev.original is not None and e.key not in force_original:
                original = prev.original
            else:
                original = original_values.get(e.key)
        rows.append((_hash_key(e.key, bits=64), e.status, value, original))
    if not rows:
        if status_file.exists():
            status_file.unlink()
        return
    if last_opened is None and status_file.exists():
        last_opened = read_last_opened_from_path(status_file)
    if last_opened is None:
        last_opened = 0
    _write_rows(status_file, rows, last_opened, hash_bits=64)


def read_last_opened_from_path(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            data = handle.read(_HEADER_V2.size)
    except OSError:
        return 0
    if len(data) < _HEADER_V1.size:
        return 0
    if data.startswith(_MAGIC_V4):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, _count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V4:
                return int(last_opened or 0)
        return 0
    if data.startswith(_MAGIC_V3):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, _count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V3:
                return int(last_opened or 0)
        return 0
    if data.startswith(_MAGIC_V2):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, _count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V2:
                return int(last_opened or 0)
        return 0
    if not data.startswith(_MAGIC_V1):
        return 0
    if len(data) >= _HEADER_V2.size:
        magic, last_opened, _count = _HEADER_V2.unpack_from(data, 0)
        if magic == _MAGIC_V1:
            return int(last_opened or 0)
    magic, _count = _HEADER_V1.unpack_from(data, 0)
    if magic != _MAGIC_V1:
        return 0
    return 0


def touch_last_opened(root: Path, file_path: Path, last_opened: int) -> bool:
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
    except OSError:
        return False
    parsed = _read_rows_any(data)
    if not parsed:
        return False
    _write_rows(
        status_file,
        parsed.rows,
        last_opened,
        hash_bits=parsed.hash_bits,
        magic=parsed.magic,
    )
    return True


def _write_rows(
    status_file: Path,
    rows: list[tuple[int, Status, str | None, str | None]],
    last_opened: int,
    *,
    hash_bits: int,
    magic: bytes | None = None,
) -> None:
    buf = bytearray()
    if magic is None:
        magic = _MAGIC_V4 if hash_bits == 64 else _MAGIC_V3
    buf += _HEADER_V2.pack(magic, int(last_opened), len(rows))
    for key_hash, status, value, original in rows:
        flags = 0
        raw_value = b""
        raw_original = b""
        if value is None:
            value_len = 0
        else:
            flags |= 0x1
            raw_value = value.encode("utf-8")
            value_len = len(raw_value)
        if original is None:
            original_len = 0
        else:
            flags |= 0x2
            raw_original = original.encode("utf-8")
            original_len = len(raw_original)
        if hash_bits == 16:
            buf += _RECORD_V3.pack(
                int(key_hash) & 0xFFFF,
                status.value,
                flags,
                value_len,
                original_len,
            )
        else:
            buf += _RECORD_V4.pack(
                int(key_hash) & 0xFFFFFFFFFFFFFFFF,
                status.value,
                flags,
                value_len,
                original_len,
            )
        if raw_value:
            buf += raw_value
        if raw_original:
            buf += raw_original
    write_bytes_atomic(status_file, bytes(buf))
