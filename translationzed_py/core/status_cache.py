from __future__ import annotations

import struct
from pathlib import Path

import xxhash

from translationzed_py.core.model import Entry, Status


def _hash_key(key: str) -> int:
    # xxhash64 truncated to 16 bits
    return int(xxhash.xxh64(key.encode("utf-8")).intdigest()) & 0xFFFF


def _cache_path(root: Path, file_path: Path) -> Path:
    rel = file_path.relative_to(root)
    rel_cache = rel.parent / f"{rel.name}.tzstatus.bin"
    return root / ".tzp-cache" / rel_cache


def read(root: Path, file_path: Path) -> dict[int, Status]:
    """
    Read per-file cache, returning a mapping { key_hash: Status }.
    Missing or corrupt files are ignored.
    """
    status_file = _cache_path(root, file_path)
    try:
        data = status_file.read_bytes()
        (count,) = struct.unpack_from("<I", data, 0)
        expected = 4 + (count * struct.calcsize("<HB"))
        if len(data) < expected:
            return {}
        offset = 4
        out: dict[int, Status] = {}
        for _ in range(count):
            key_hash, status_byte = struct.unpack_from("<HB", data, offset)
            offset += struct.calcsize("<HB")
            try:
                out[key_hash] = Status(status_byte)
            except ValueError:
                # unknown status code → skip
                continue
        return out
    except (OSError, struct.error):
        return {}


def write(root: Path, file_path: Path, entries: list[Entry]) -> None:
    """
    Write current in-memory statuses for `entries` into per-file cache.
    """
    status_file = _cache_path(root, file_path)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[int, Status]] = []
    for e in entries:
        rows.append((_hash_key(e.key), e.status))
    buf = bytearray()
    buf += struct.pack("<I", len(rows))
    for key_hash, status in rows:
        buf += struct.pack("<HB", key_hash, status.value)
    # atomic replace
    tmp = status_file.with_name(status_file.name + ".tmp")
    tmp.write_bytes(buf)
    tmp.replace(status_file)
