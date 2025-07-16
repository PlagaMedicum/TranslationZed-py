from __future__ import annotations

from pathlib import Path

from .model import ParsedFile


def save(pf: ParsedFile, new_entries: dict[str, str]) -> None:
    """Patch raw bytes and overwrite file atomically."""
    buf = bytearray(pf.raw_bytes())
    for e in pf.entries:
        if e.key in new_entries:
            b = new_entries[e.key].encode("utf-8").replace(b'"', b'\\"')
            start, end = e.span
            buf[start:end] = b'"' + b + b'"'
    tmp = Path(str(pf.path) + ".tmp")
    tmp.write_bytes(buf)
    tmp.replace(pf.path)
