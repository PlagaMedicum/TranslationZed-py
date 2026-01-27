from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import xxhash

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.model import Entry, Status

_MAGIC = b"TZC1"
_HEADER = struct.Struct("<4sI")
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


def read(root: Path, file_path: Path) -> dict[int, CacheEntry]:
    """
    Read per-file cache, returning a mapping { key_hash: CacheEntry }.
    Missing or corrupt files are ignored.
    """
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
        if not data:
            return {}

        if data.startswith(_MAGIC):
            magic, count = _HEADER.unpack_from(data, 0)
            if magic != _MAGIC:
                return {}
            offset = _HEADER.size
            out: dict[int, CacheEntry] = {}
            for _ in range(count):
                if offset + _RECORD.size > len(data):
                    return {}
                key_hash, status_byte, flags, value_len = _RECORD.unpack_from(
                    data, offset
                )
                offset += _RECORD.size
                value: str | None = None
                if flags & 0x1:
                    end = offset + value_len
                    if end > len(data):
                        return {}
                    raw = data[offset:end]
                    offset = end
                    value = raw.decode("utf-8", errors="replace")
                try:
                    status = Status(status_byte)
                except ValueError:
                    continue
                out[key_hash] = CacheEntry(status, value)
            return out

        # --- legacy (status-only) format ---
        (count,) = struct.unpack_from("<I", data, 0)
        expected = 4 + (count * struct.calcsize("<HB"))
        if len(data) < expected:
            return {}
        offset = 4
        out: dict[int, CacheEntry] = {}
        for _ in range(count):
            key_hash, status_byte = struct.unpack_from("<HB", data, offset)
            offset += struct.calcsize("<HB")
            try:
                status = Status(status_byte)
            except ValueError:
                # unknown status code → skip
                continue
            out[key_hash] = CacheEntry(status, None)
        return out
    except (OSError, struct.error):
        return {}


def write(
    root: Path,
    file_path: Path,
    entries: list[Entry],
    *,
    changed_keys: set[str] | None = None,
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
    status_file.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray()
    buf += _HEADER.pack(_MAGIC, len(rows))
    for key_hash, status, value in rows:
        if value is None:
            buf += _RECORD.pack(key_hash, status.value, 0, 0)
        else:
            raw = value.encode("utf-8")
            buf += _RECORD.pack(key_hash, status.value, 1, len(raw))
            buf += raw
    # atomic replace
    tmp = status_file.with_name(status_file.name + ".tmp")
    tmp.write_bytes(buf)
    tmp.replace(status_file)
