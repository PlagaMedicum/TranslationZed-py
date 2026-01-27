from __future__ import annotations

import struct
from pathlib import Path

import xxhash

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.atomic_io import write_bytes_atomic
from translationzed_py.core.project_scanner import list_translatable_files, scan_root

_MAGIC = b"ENH1"
_HEADER = struct.Struct("<4sI")
_HASH = struct.Struct("<Q")


def _hash_bytes(data: bytes) -> int:
    return int(xxhash.xxh64(data).intdigest())


def _cache_path(root: Path) -> Path:
    cfg = _load_app_config(root)
    return root / cfg.cache_dir / cfg.en_hash_filename


def compute(root: Path) -> dict[str, int]:
    locales = scan_root(root)
    if "EN" not in locales:
        return {}
    en_path = locales["EN"].path
    out: dict[str, int] = {}
    for path in list_translatable_files(en_path):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        out[rel] = _hash_bytes(data)
    return out


def read(root: Path) -> dict[str, int]:
    cache_path = _cache_path(root)
    try:
        data = cache_path.read_bytes()
    except OSError:
        return {}
    if not data or not data.startswith(_MAGIC):
        return {}
    try:
        magic, count = _HEADER.unpack_from(data, 0)
        if magic != _MAGIC:
            return {}
        offset = _HEADER.size
        out: dict[str, int] = {}
        for _ in range(count):
            if offset + 2 > len(data):
                return {}
            (path_len,) = struct.unpack_from("<H", data, offset)
            offset += 2
            end = offset + path_len
            if end > len(data):
                return {}
            path = data[offset:end].decode("utf-8", errors="replace")
            offset = end
            if offset + _HASH.size > len(data):
                return {}
            (hval,) = _HASH.unpack_from(data, offset)
            offset += _HASH.size
            out[path] = hval
        return out
    except struct.error:
        return {}


def write(root: Path, hashes: dict[str, int]) -> None:
    cache_path = _cache_path(root)
    if not hashes:
        if cache_path.exists():
            cache_path.unlink()
        return
    items = sorted(hashes.items())
    buf = bytearray()
    buf += _HEADER.pack(_MAGIC, len(items))
    for rel, hval in items:
        raw = rel.encode("utf-8")
        buf += struct.pack("<H", len(raw))
        buf += raw
        buf += _HASH.pack(hval)
    write_bytes_atomic(cache_path, bytes(buf))
