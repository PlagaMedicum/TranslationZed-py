from __future__ import annotations

from pathlib import Path

from .atomic_io import write_bytes_atomic
from .model import Entry, ParsedFile


def save(
    pf: ParsedFile,
    new_entries: dict[str, str],
    *,
    encoding: str = "utf-8",
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

    def _normalize_encoding(enc: str, raw: bytes) -> str:
        norm = enc.lower().replace("_", "-")
        if norm in {"utf-16", "utf16"}:
            if raw.startswith(b"\xff\xfe"):
                return "utf-16-le"
            if raw.startswith(b"\xfe\xff"):
                return "utf-16-be"
            return "utf-16-le"
        return enc

    literal_encoding = _normalize_encoding(encoding, buf)

    def _escape_literal(text: str) -> str:
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def _encode_literal(text: str) -> bytes:
        escaped = _escape_literal(text)
        return f'"{escaped}"'.encode(literal_encoding)

    replacements: list[tuple[int, int, bytes]] = []
    changed_by_index: dict[int, tuple[str, tuple[int, ...], int, bool]] = {}
    for idx, e in enumerate(pf.entries):
        if e.key not in new_entries:
            continue
        new_value = new_entries[e.key]
        if e.raw:
            region = new_value.encode(literal_encoding)
            replacements.append((0, len(buf), region))
            changed_by_index[idx] = (new_value, (len(new_value),), len(region), True)
            break
        parts = _split_by_segments(new_value, e.segments)
        literals = [_encode_literal(p) for p in parts]
        region = literals[0]
        for gap, literal in zip(e.gaps, literals[1:]):
            region += gap + literal
        replacements.append((e.span[0], e.span[1], region))
        changed_by_index[idx] = (
            new_value,
            tuple(len(p) for p in parts),
            len(region),
            False,
        )

    # apply from end → start to keep original spans valid during the write
    for start, end, literal in sorted(replacements, key=lambda item: item[0], reverse=True):
        buf[start:end] = literal

    write_bytes_atomic(pf.path, bytes(buf))

    # refresh in-memory spans and cached raw bytes after a successful write
    shift = 0
    new_list: list[Entry] = []
    for idx, e in enumerate(pf.entries):
        start, end = e.span
        if idx in changed_by_index:
            value, seg_lens, region_len, raw_entry = changed_by_index[idx]
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
                    raw_entry,
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
                    e.raw,
                )
            )
    pf.entries = new_list
    pf._raw = buf
    pf.dirty = False
