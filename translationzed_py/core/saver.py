from __future__ import annotations

from pathlib import Path

from .model import Entry, ParsedFile
from .status_cache import write as _write_status_cache


def save(
    pf: ParsedFile,
    new_entries: dict[str, str],
    *,
    encoding: str = "utf-8",
    locale_dir: Path | None = None,
    all_files: list[ParsedFile] | None = None,
) -> None:
    """Patch raw bytes and overwrite file atomically."""
    buf = bytearray(pf.raw_bytes())

    encoded: dict[str, tuple[str, bytes, int]] = {}
    for key, value in new_entries.items():
        literal = b'"' + value.encode(encoding).replace(b'"', b'\\"') + b'"'
        encoded[key] = (value, literal, len(literal))

    replacements: list[tuple[int, int, bytes]] = []
    for e in pf.entries:
        if e.key in encoded:
            _, literal, _ = encoded[e.key]
            replacements.append((e.span[0], e.span[1], literal))

    # apply from end → start to keep original spans valid during the write
    for start, end, literal in sorted(replacements, key=lambda item: item[0], reverse=True):
        buf[start:end] = literal

    tmp = Path(str(pf.path) + ".tmp")
    tmp.write_bytes(buf)
    tmp.replace(pf.path)

    # refresh in-memory spans and cached raw bytes after a successful write
    shift = 0
    new_list: list[Entry] = []
    for e in pf.entries:
        start, end = e.span
        if e.key in encoded:
            value, _, literal_len = encoded[e.key]
            new_start = start + shift
            new_end = new_start + literal_len
            shift += literal_len - (end - start)
            new_list.append(Entry(e.key, value, e.status, (new_start, new_end)))
        else:
            new_start = start + shift
            new_end = end + shift
            new_list.append(Entry(e.key, e.value, e.status, (new_start, new_end)))
    pf.entries = new_list
    pf._raw = buf
    pf.dirty = False

    # persist status cache for this locale
    if locale_dir is not None and all_files is not None:
        _write_status_cache(locale_dir, all_files)
