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

    def _split_by_segments(value: str, seg_lens: tuple[int, ...]) -> list[str]:
        if not seg_lens:
            return [value]
        remaining = value
        parts: list[str] = []
        for i, seg_len in enumerate(seg_lens):
            if i == len(seg_lens) - 1:
                parts.append(remaining)
            else:
                parts.append(remaining[:seg_len])
                remaining = remaining[seg_len:]
        return parts

    def _encode_literal(text: str) -> bytes:
        return b'"' + text.encode(encoding).replace(b'"', b'\\"') + b'"'

    replacements: list[tuple[int, int, bytes]] = []
    changed_by_index: dict[int, tuple[str, tuple[int, ...], int]] = {}
    for idx, e in enumerate(pf.entries):
        if e.key not in new_entries:
            continue
        new_value = new_entries[e.key]
        parts = _split_by_segments(new_value, e.segments)
        literals = [_encode_literal(p) for p in parts]
        region = literals[0]
        for gap, literal in zip(e.gaps, literals[1:]):
            region += gap + literal
        replacements.append((e.span[0], e.span[1], region))
        changed_by_index[idx] = (new_value, tuple(len(p) for p in parts), len(region))

    # apply from end → start to keep original spans valid during the write
    for start, end, literal in sorted(replacements, key=lambda item: item[0], reverse=True):
        buf[start:end] = literal

    tmp = Path(str(pf.path) + ".tmp")
    tmp.write_bytes(buf)
    tmp.replace(pf.path)

    # refresh in-memory spans and cached raw bytes after a successful write
    shift = 0
    new_list: list[Entry] = []
    for idx, e in enumerate(pf.entries):
        start, end = e.span
        if idx in changed_by_index:
            value, seg_lens, region_len = changed_by_index[idx]
            new_start = start + shift
            new_end = new_start + region_len
            shift += region_len - (end - start)
            new_list.append(
                Entry(
                    e.key,
                    value,
                    e.status,
                    (new_start, new_end),
                    seg_lens,
                    e.gaps,
                )
            )
        else:
            new_start = start + shift
            new_end = end + shift
            new_list.append(
                Entry(
                    e.key,
                    e.value,
                    e.status,
                    (new_start, new_end),
                    e.segments,
                    e.gaps,
                )
            )
    pf.entries = new_list
    pf._raw = buf
    pf.dirty = False

    # persist status cache for this locale
    if locale_dir is not None and all_files is not None:
        _write_status_cache(locale_dir, all_files)
