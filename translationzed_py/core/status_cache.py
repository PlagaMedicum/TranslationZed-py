"""Status cache module."""

from __future__ import annotations

import contextlib
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import xxhash

from translationzed_py.core.app_config import (
    LEGACY_CACHE_DIR,
)
from translationzed_py.core.app_config import (
    load as _load_app_config,
)
from translationzed_py.core.atomic_io import write_bytes_atomic
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.project_scanner import LocaleMeta

_MAGIC_V1 = b"TZC1"
_MAGIC_V2 = b"TZC2"
_MAGIC_V3 = b"TZC3"
_MAGIC_V4 = b"TZC4"
_MAGIC_V5 = b"TZC5"
_HEADER_V1 = struct.Struct("<4sI")
_HEADER_V2 = struct.Struct("<4sQI")
_HEADER_V5 = struct.Struct("<4sQII")
_RECORD_V2 = struct.Struct("<HBBI")
_RECORD_V3 = struct.Struct("<HBBII")
_RECORD_V4 = struct.Struct("<QBBII")

_FLAG_HAS_DRAFTS = 0x1


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Represent CacheEntry."""

    status: Status
    value: str | None
    original: str | None = None


class CacheMap(dict[int, CacheEntry]):
    """Represent CacheMap."""

    __slots__ = ("hash_bits", "legacy_status", "last_opened", "magic", "has_drafts")

    def __init__(
        self,
        *args: object,
        hash_bits: int = 64,
        legacy_status: bool = False,
        last_opened: int = 0,
        magic: bytes = b"",
        has_drafts: bool = False,
        **kwargs: object,
    ) -> None:
        """Initialize the instance."""
        super().__init__(*args, **kwargs)
        self.hash_bits = hash_bits
        self.legacy_status = legacy_status
        self.last_opened = last_opened
        self.magic = magic
        self.has_drafts = has_drafts


_LEGACY_STATUS_MAP = {
    0: Status.UNTOUCHED,
    1: Status.TRANSLATED,
    2: Status.PROOFREAD,
    3: Status.FOR_REVIEW,
}


@dataclass(frozen=True, slots=True)
class _CacheRows:
    """Represent CacheRows."""

    last_opened: int
    rows: list[tuple[int, Status, str | None, str | None]]
    legacy_status: bool
    hash_bits: int
    magic: bytes
    has_drafts: bool


def _status_from_byte(status_byte: int, *, legacy: bool) -> Status | None:
    """Execute status from byte."""
    if legacy:
        return _LEGACY_STATUS_MAP.get(status_byte)
    try:
        return Status(status_byte)
    except ValueError:
        return None


def _hash_key(key: str, *, bits: int = 64, key_hash: int | None = None) -> int:
    """Execute hash key."""
    digest = (
        int(key_hash)
        if key_hash is not None
        else int(xxhash.xxh64(key.encode("utf-8")).intdigest())
    )
    if bits == 16:
        return digest & 0xFFFF
    return digest & 0xFFFFFFFFFFFFFFFF


def _cache_path(root: Path, file_path: Path) -> Path:
    """Execute cache path."""
    cfg = _load_app_config(root)
    rel = file_path.relative_to(root)
    rel_cache = rel.parent / f"{rel.stem}{cfg.cache_ext}"
    return root / cfg.cache_dir / rel_cache


def _legacy_cache_path(root: Path, file_path: Path) -> Path:
    """Execute legacy cache path."""
    cfg = _load_app_config(root)
    rel = file_path.relative_to(root)
    rel_cache = rel.parent / f"{rel.stem}{cfg.cache_ext}"
    legacy = root / LEGACY_CACHE_DIR / rel_cache
    current = root / cfg.cache_dir / rel_cache
    return legacy if legacy != current else current


def _read_cache_path(root: Path, file_path: Path) -> Path:
    """Read cache path."""
    current = _cache_path(root, file_path)
    if current.exists():
        return current
    legacy = _legacy_cache_path(root, file_path)
    if legacy.exists():
        return legacy
    return current


def _cache_roots(root: Path) -> tuple[Path, ...]:
    """Execute cache roots."""
    cfg = _load_app_config(root)
    current = root / cfg.cache_dir
    legacy = root / LEGACY_CACHE_DIR
    if legacy == current:
        return (current,)
    return (current, legacy)


def cache_path(root: Path, file_path: Path) -> Path:
    """Execute cache path."""
    return _cache_path(root, file_path)


def _original_path_from_cache(root: Path, cache_path: Path) -> Path | None:
    """Execute original path from cache."""
    cfg = _load_app_config(root)
    rel: Path | None = None
    for cache_root in _cache_roots(root):
        try:
            rel = cache_path.relative_to(cache_root)
            break
        except ValueError:
            continue
    if rel is None:
        return None
    if not rel.parts:
        return None
    if rel.name == cfg.en_hash_filename:
        return None
    return (root / rel).with_suffix(cfg.translation_ext)


def legacy_cache_paths(root: Path) -> list[Path]:
    """Execute legacy cache paths."""
    cfg = _load_app_config(root)
    cache_roots = _cache_roots(root)
    out: list[Path] = []
    seen: set[Path] = set()
    for cache_root in cache_roots:
        if not cache_root.exists():
            continue
        for cache_path in cache_root.rglob(f"*{cfg.cache_ext}"):
            if cache_path in seen:
                continue
            seen.add(cache_path)
            if cache_path.name == cfg.en_hash_filename:
                continue
            try:
                with cache_path.open("rb") as handle:
                    head = handle.read(4)
            except OSError:
                continue
            if not head:
                continue
            if head in {_MAGIC_V4, _MAGIC_V5}:
                continue
            out.append(cache_path)
    return out


def _migrate_cache_path(
    root: Path, cache_path: Path, locales: dict[str, LocaleMeta]
) -> bool:
    """Execute migrate cache path."""
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
        key_hash = getattr(entry, "key_hash", None)
        key16 = _hash_key(entry.key, bits=16, key_hash=key_hash)
        rec = legacy_map.get(key16)
        if rec is None:
            continue
        rows.append(
            (
                _hash_key(entry.key, bits=64, key_hash=key_hash),
                rec.status,
                rec.value,
                rec.original,
            )
        )
    if not rows:
        return False
    _write_rows(cache_path, rows, parsed.last_opened, hash_bits=64)
    return True


def migrate_paths(root: Path, locales: dict[str, LocaleMeta], paths: list[Path]) -> int:
    """Execute migrate paths."""
    cfg = _load_app_config(root)
    migrated = 0
    for cache_path in paths:
        if cache_path.name == cfg.en_hash_filename:
            continue
        if _migrate_cache_path(root, cache_path, locales):
            migrated += 1
    return migrated


def migrate_all(root: Path, locales: dict[str, LocaleMeta] | None = None) -> int:
    """Execute migrate all."""
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
    """Parse rows v2."""
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
    """Parse rows v3."""
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
    """Parse rows v4."""
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
    """Read rows any."""
    if not data:
        return None
    if data.startswith(_MAGIC_V5):
        if len(data) >= _HEADER_V5.size:
            magic, last_opened, count, flags = _HEADER_V5.unpack_from(data, 0)
            if magic == _MAGIC_V5:
                parsed_rows = _parse_rows_v4(
                    data, offset=_HEADER_V5.size, count=count, legacy=False
                )
                if parsed_rows is not None:
                    return _CacheRows(
                        last_opened,
                        parsed_rows,
                        False,
                        64,
                        magic,
                        bool(flags & _FLAG_HAS_DRAFTS),
                    )
        return None
    if data.startswith(_MAGIC_V4):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V4:
                parsed_rows = _parse_rows_v4(
                    data, offset=_HEADER_V2.size, count=count, legacy=False
                )
                if parsed_rows is not None:
                    has_drafts = any(
                        value is not None for _, _, value, _ in parsed_rows
                    )
                    return _CacheRows(
                        last_opened, parsed_rows, False, 64, magic, has_drafts
                    )
        return None
    if data.startswith(_MAGIC_V3):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V3:
                parsed_rows = _parse_rows_v3(
                    data, offset=_HEADER_V2.size, count=count, legacy=False
                )
                if parsed_rows is not None:
                    has_drafts = any(
                        value is not None for _, _, value, _ in parsed_rows
                    )
                    return _CacheRows(
                        last_opened, parsed_rows, False, 16, magic, has_drafts
                    )
        return None
    if data.startswith(_MAGIC_V2):
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC_V2:
                parsed_rows = _parse_rows_v3(
                    data, offset=_HEADER_V2.size, count=count, legacy=True
                )
                if parsed_rows is not None:
                    has_drafts = any(
                        value is not None for _, _, value, _ in parsed_rows
                    )
                    return _CacheRows(
                        last_opened, parsed_rows, True, 16, magic, has_drafts
                    )
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
                    has_drafts = any(
                        value is not None for _, _, value, _ in parsed_rows
                    )
                    return _CacheRows(
                        last_opened, parsed_rows, True, 16, magic, has_drafts
                    )
        # v1 header: magic + u32 count
        if len(data) >= _HEADER_V1.size:
            magic, count = _HEADER_V1.unpack_from(data, 0)
            if magic == _MAGIC_V1:
                parsed_rows = _parse_rows_v2(
                    data, offset=_HEADER_V1.size, count=count, legacy=True
                )
                if parsed_rows is not None:
                    has_drafts = any(
                        value is not None for _, _, value, _ in parsed_rows
                    )
                    return _CacheRows(0, parsed_rows, True, 16, magic, has_drafts)
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
    has_drafts = any(value is not None for _, _, value, _ in legacy_rows)
    return _CacheRows(0, legacy_rows, True, 16, _MAGIC_V1, has_drafts)


def read(root: Path, file_path: Path) -> CacheMap:
    """
    Read per-file cache, returning a mapping { key_hash: CacheEntry }.

    Missing or corrupt files are ignored.
    """
    status_file = _read_cache_path(root, file_path)
    current_status_file = _cache_path(root, file_path)
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
            has_drafts=parsed.has_drafts,
        )
        for key_hash, status, value, original in parsed.rows:
            out[key_hash] = CacheEntry(status, value, original)
        if (
            parsed.legacy_status
            and parsed.hash_bits == 16
            and parsed.magic != _MAGIC_V3
        ):
            upgrade_target = (
                current_status_file
                if status_file != current_status_file
                else status_file
            )
            with contextlib.suppress(OSError):
                _write_rows(
                    upgrade_target,
                    parsed.rows,
                    parsed.last_opened,
                    hash_bits=16,
                    magic=_MAGIC_V3,
                )
                if status_file != upgrade_target:
                    status_file.unlink(missing_ok=True)
        elif status_file != current_status_file:
            with contextlib.suppress(OSError):
                _write_rows(
                    current_status_file,
                    parsed.rows,
                    parsed.last_opened,
                    hash_bits=parsed.hash_bits,
                )
                status_file.unlink(missing_ok=True)
        return out
    except (OSError, struct.error):
        return CacheMap()


def write(
    root: Path,
    file_path: Path,
    entries: Iterable[Entry],
    *,
    changed_keys: set[str] | None = None,
    last_opened: int | None = None,
    original_values: dict[str, str] | None = None,
    force_original: set[str] | None = None,
) -> None:
    """Write in-memory statuses/drafts to per-file cache for changed keys."""
    status_file = _cache_path(root, file_path)
    legacy_status_file = _legacy_cache_path(root, file_path)
    read_status_file = _read_cache_path(root, file_path)
    changed_keys = changed_keys or set()
    rows: list[tuple[int, Status, str | None, str | None]] = []
    original_values = original_values or {}
    force_original = force_original or set()
    existing: CacheMap | dict[int, CacheEntry] = {}
    existing_hash_bits = 64
    if changed_keys:
        existing = read(root, file_path)
        existing_hash_bits = getattr(existing, "hash_bits", 64)
    for e in entries:
        include = e.status != Status.UNTOUCHED or e.key in changed_keys
        if not include:
            continue
        key_hash = getattr(e, "key_hash", None)
        value = e.value if e.key in changed_keys else None
        original: str | None = None
        if e.key in changed_keys:
            prev = existing.get(
                _hash_key(e.key, bits=existing_hash_bits, key_hash=key_hash)
            )
            if prev and prev.original is not None and e.key not in force_original:
                original = prev.original
            else:
                original = original_values.get(e.key)
        rows.append(
            (_hash_key(e.key, bits=64, key_hash=key_hash), e.status, value, original)
        )
    if not rows:
        if status_file.exists():
            status_file.unlink()
        if legacy_status_file != status_file and legacy_status_file.exists():
            legacy_status_file.unlink()
        return
    if last_opened is None and read_status_file.exists():
        last_opened = read_last_opened_from_path(read_status_file)
    if last_opened is None:
        last_opened = 0
    _write_rows(status_file, rows, last_opened, hash_bits=64)
    if legacy_status_file != status_file and legacy_status_file.exists():
        with contextlib.suppress(OSError):
            legacy_status_file.unlink()


def read_last_opened_from_path(path: Path) -> int:
    """Read last opened from path."""
    try:
        with path.open("rb") as handle:
            data = handle.read(_HEADER_V5.size)
    except OSError:
        return 0
    if len(data) < _HEADER_V1.size:
        return 0
    if data.startswith(_MAGIC_V5):
        if len(data) >= _HEADER_V5.size:
            magic, last_opened, _count, _flags = _HEADER_V5.unpack_from(data, 0)
            if magic == _MAGIC_V5:
                return int(last_opened or 0)
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


def read_has_drafts_from_path(path: Path) -> bool:
    """Read has drafts from path."""
    try:
        with path.open("rb") as handle:
            data = handle.read(_HEADER_V5.size)
    except OSError:
        return False
    if len(data) < _HEADER_V1.size:
        return False
    if data.startswith(_MAGIC_V5):
        if len(data) >= _HEADER_V5.size:
            magic, _last_opened, _count, flags = _HEADER_V5.unpack_from(data, 0)
            if magic == _MAGIC_V5:
                return bool(flags & _FLAG_HAS_DRAFTS)
        return False
    # fallback for legacy formats: parse full file to determine draft presence
    try:
        full = path.read_bytes()
    except OSError:
        return False
    parsed = _read_rows_any(full)
    if not parsed:
        return False
    return parsed.has_drafts


def touch_last_opened(root: Path, file_path: Path, last_opened: int) -> bool:
    """Execute touch last opened."""
    status_file = _read_cache_path(root, file_path)
    current_status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
    except OSError:
        return False
    parsed = _read_rows_any(data)
    if not parsed:
        return False
    magic = parsed.magic
    if parsed.hash_bits == 64 and magic != _MAGIC_V5:
        magic = _MAGIC_V5
    _write_rows(
        current_status_file,
        parsed.rows,
        last_opened,
        hash_bits=parsed.hash_bits,
        magic=magic,
    )
    if status_file != current_status_file:
        with contextlib.suppress(OSError):
            status_file.unlink(missing_ok=True)
    return True


def _write_rows(
    status_file: Path,
    rows: list[tuple[int, Status, str | None, str | None]],
    last_opened: int,
    *,
    hash_bits: int,
    magic: bytes | None = None,
) -> None:
    """Write rows."""
    buf = bytearray()
    if magic is None:
        magic = _MAGIC_V5 if hash_bits == 64 else _MAGIC_V3
    if magic == _MAGIC_V5:
        flags = (
            _FLAG_HAS_DRAFTS if any(value is not None for _, _, value, _ in rows) else 0
        )
        buf += _HEADER_V5.pack(magic, int(last_opened), len(rows), flags)
    else:
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
