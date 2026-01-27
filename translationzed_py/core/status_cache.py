from __future__ import annotations

import struct
from pathlib import Path

import xxhash

from translationzed_py.core.model import ParsedFile, Status


def _hash_key(key: str) -> int:
    # xxhash64 truncated to 16 bits
    return int(xxhash.xxh64(key.encode("utf-8")).intdigest()) & 0xFFFF


def read(locale_dir: Path) -> dict[int, Status]:
    """
    Read .tzstatus.bin from locale_dir, returning a mapping
    { key_hash: Status }. Missing or corrupt files are ignored.
    """
    status_file = locale_dir / ".tzstatus.bin"
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


def write(locale_dir: Path, files: list[ParsedFile]) -> None:
    """
    Write current in-memory statuses for all entries in `files` into
    .tzstatus.bin inside locale_dir.
    """
    status_file = locale_dir / ".tzstatus.bin"
    entries: list[tuple[int, Status]] = []
    for pf in files:
        for e in pf.entries:
            entries.append((_hash_key(e.key), e.status))
    buf = bytearray()
    buf += struct.pack("<I", len(entries))
    for key_hash, status in entries:
        buf += struct.pack("<HB", key_hash, status.value)
    # atomic replace
    tmp = status_file.with_name(".tzstatus.bin.tmp")
    tmp.write_bytes(buf)
    tmp.replace(status_file)
