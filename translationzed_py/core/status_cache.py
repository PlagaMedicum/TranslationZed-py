from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import xxhash

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.atomic_io import write_bytes_atomic
from translationzed_py.core.model import Entry, Status

_MAGIC = b"TZC1"
_HEADER_V1 = struct.Struct("<4sI")
_HEADER_V2 = struct.Struct("<4sQI")
_RECORD = struct.Struct("<HBBI")


@dataclass(frozen=True, slots=True)
class CacheEntry:
    status: Status
    value: str | None


def _hash_key(key: str) -> int:
    # xxhash64 truncated to 16 bits
    return int(xxhash.xxh64(key.encode("utf-8")).intdigest()) & 0xFFFF


def _cache_path(root: Path, file_path: Path) -> Path:
    cfg = _load_app_config(root)
    rel = file_path.relative_to(root)
    rel_cache = rel.parent / f"{rel.stem}{cfg.cache_ext}"
    return root / cfg.cache_dir / rel_cache


def cache_path(root: Path, file_path: Path) -> Path:
    return _cache_path(root, file_path)


def _parse_rows(
    data: bytes, *, offset: int, count: int
) -> list[tuple[int, Status, str | None]] | None:
    rows: list[tuple[int, Status, str | None]] = []
    for _ in range(count):
        if offset + _RECORD.size > len(data):
            return None
        key_hash, status_byte, flags, value_len = _RECORD.unpack_from(data, offset)
        offset += _RECORD.size
        value: str | None = None
        if flags & 0x1:
            end = offset + value_len
            if end > len(data):
                return None
            raw = data[offset:end]
            offset = end
            value = raw.decode("utf-8", errors="replace")
        try:
            status = Status(status_byte)
        except ValueError:
            continue
        rows.append((key_hash, status, value))
    return rows


def _read_rows_any(data: bytes) -> tuple[int, list[tuple[int, Status, str | None]]] | None:
    if not data:
        return None
    if data.startswith(_MAGIC):
        # v2 header: magic + u64 last_opened + u32 count
        if len(data) >= _HEADER_V2.size:
            magic, last_opened, count = _HEADER_V2.unpack_from(data, 0)
            if magic == _MAGIC:
                rows = _parse_rows(data, offset=_HEADER_V2.size, count=count)
                if rows is not None:
                    return last_opened, rows
        # v1 header: magic + u32 count
        if len(data) >= _HEADER_V1.size:
            magic, count = _HEADER_V1.unpack_from(data, 0)
            if magic == _MAGIC:
                rows = _parse_rows(data, offset=_HEADER_V1.size, count=count)
                if rows is not None:
                    return 0, rows
        return None

    # --- legacy (status-only) format ---
    if len(data) < 4:
        return None
    (count,) = struct.unpack_from("<I", data, 0)
    expected = 4 + (count * struct.calcsize("<HB"))
    if len(data) < expected:
        return None
    offset = 4
    rows: list[tuple[int, Status, str | None]] = []
    for _ in range(count):
        key_hash, status_byte = struct.unpack_from("<HB", data, offset)
        offset += struct.calcsize("<HB")
        try:
            status = Status(status_byte)
        except ValueError:
            continue
        rows.append((key_hash, status, None))
    return 0, rows


def read(root: Path, file_path: Path) -> dict[int, CacheEntry]:
    """
    Read per-file cache, returning a mapping { key_hash: CacheEntry }.
    Missing or corrupt files are ignored.
    """
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
        parsed = _read_rows_any(data)
        if not parsed:
            return {}
        _, rows = parsed
        out: dict[int, CacheEntry] = {}
        for key_hash, status, value in rows:
            out[key_hash] = CacheEntry(status, value)
        return out
    except (OSError, struct.error):
        return {}


def write(
    root: Path,
    file_path: Path,
    entries: list[Entry],
    *,
    changed_keys: set[str] | None = None,
    last_opened: int | None = None,
) -> None:
    """
    Write current in-memory statuses and (optional) draft translations into
    per-file cache. Values are stored only for keys in `changed_keys`.
    """
    status_file = _cache_path(root, file_path)
    changed_keys = changed_keys or set()
    rows: list[tuple[int, Status, str | None]] = []
    for e in entries:
        include = e.status != Status.UNTOUCHED or e.key in changed_keys
        if not include:
            continue
        value = e.value if e.key in changed_keys else None
        rows.append((_hash_key(e.key), e.status, value))
    if not rows:
        if status_file.exists():
            status_file.unlink()
        return
    if last_opened is None and status_file.exists():
        last_opened = read_last_opened_from_path(status_file)
    if last_opened is None:
        last_opened = 0
    _write_rows(status_file, rows, last_opened)


def read_last_opened_from_path(path: Path) -> int:
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    parsed = _read_rows_any(data)
    if not parsed:
        return 0
    last_opened, _ = parsed
    return int(last_opened or 0)


def touch_last_opened(root: Path, file_path: Path, last_opened: int) -> bool:
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
    except OSError:
        return False
    parsed = _read_rows_any(data)
    if not parsed:
        return False
    _, rows = parsed
    _write_rows(status_file, rows, last_opened)
    return True


def _write_rows(
    status_file: Path,
    rows: list[tuple[int, Status, str | None]],
    last_opened: int,
) -> None:
    buf = bytearray()
    buf += _HEADER_V2.pack(_MAGIC, int(last_opened), len(rows))
    for key_hash, status, value in rows:
        if value is None:
            buf += _RECORD.pack(key_hash, status.value, 0, 0)
        else:
            raw = value.encode("utf-8")
            buf += _RECORD.pack(key_hash, status.value, 1, len(raw))
            buf += raw
    write_bytes_atomic(status_file, bytes(buf))
