from __future__ import annotations

from pathlib import Path

from .model import ParsedFile
from .status_cache import write as _write_status_cache


def save(
    pf: ParsedFile,
    new_entries: dict[str, str],
    *,
    locale_dir: Path | None = None,
    all_files: list[ParsedFile] | None = None,
) -> None:
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

    # persist status cache for this locale
    if locale_dir is not None and all_files is not None:
        _write_status_cache(locale_dir, all_files)
