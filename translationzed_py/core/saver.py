"""Persist translation edits back to locale files atomically."""

from __future__ import annotations

from collections.abc import Mapping

from .atomic_io import write_bytes_atomic
from .model import Entry, ParsedFile, Status
from .tzp_comment_policy import (
    TZP_COMMENT_PREFIX_DEFAULT,
    build_tzp_comment_write_plan,
    parse_tzp_status_comment,
)


def save(
    pf: ParsedFile,
    new_entries: dict[str, str],
    *,
    encoding: str = "utf-8",
    write_tzp_status_comments: bool = False,
    tzp_comment_prefix: str = TZP_COMMENT_PREFIX_DEFAULT,
    status_by_key: Mapping[str, Status] | None = None,
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

    def _normalize_encoding(enc: str, raw: bytes | bytearray) -> str:
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

    def _line_end_index(raw: bytearray, start: int) -> int:
        idx = start
        while idx < len(raw):
            if raw[idx] == 0x0A:
                return idx
            idx += 1
        return len(raw)

    def _first_comment_start(tail: bytes) -> int:
        best = -1
        for marker in (b"--", b"//", b"/*"):
            pos = tail.find(marker)
            if pos < 0:
                continue
            if best < 0 or pos < best:
                best = pos
        return best

    def _append_comment(prefix: bytes, rendered: bytes) -> bytes:
        if not prefix:
            return b" " + rendered
        if prefix.endswith((b" ", b"\t")):
            return prefix + rendered
        return prefix + b" " + rendered

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
        for gap, literal in zip(e.gaps, literals[1:], strict=False):
            region += gap + literal
        replacements.append((e.span[0], e.span[1], region))
        changed_by_index[idx] = (
            new_value,
            tuple(len(p) for p in parts),
            len(region),
            False,
        )

    comment_replacements = 0
    if write_tzp_status_comments:
        for e in pf.entries:
            if e.raw:
                continue
            desired_status_raw = status_by_key.get(e.key) if status_by_key else None
            desired_status = (
                desired_status_raw
                if isinstance(desired_status_raw, Status)
                else e.status
            )
            tail_start = e.span[1]
            tail_end = _line_end_index(buf, tail_start)
            tail = bytes(buf[tail_start:tail_end])
            comment_start = _first_comment_start(tail)
            prefix = tail
            existing_comment_text: str | None = None
            if comment_start >= 0:
                existing_comment_bytes = tail[comment_start:]
                existing_comment_text = existing_comment_bytes.decode(
                    literal_encoding,
                    errors="ignore",
                )
                if parse_tzp_status_comment(existing_comment_text) is None:
                    # Never mutate user-authored comments in this packet.
                    continue
                prefix = tail[:comment_start]
            plan = build_tzp_comment_write_plan(
                existing_comment=existing_comment_text,
                desired_status=desired_status,
                comment_prefix=tzp_comment_prefix,
            )
            if plan.action == "noop":
                continue
            if plan.action == "remove":
                next_tail = prefix
            else:
                assert plan.rendered_comment is not None
                rendered = plan.rendered_comment.encode(literal_encoding)
                if comment_start >= 0:
                    next_tail = prefix + rendered
                else:
                    next_tail = _append_comment(prefix, rendered)
            if next_tail == tail:
                continue
            replacements.append((tail_start, tail_end, next_tail))
            comment_replacements += 1

    # apply from end → start to keep original spans valid during the write
    for start, end, literal in sorted(
        replacements, key=lambda item: item[0], reverse=True
    ):
        buf[start:end] = literal

    write_bytes_atomic(pf.path, bytes(buf))

    if comment_replacements:
        # Comment write-back can shift spans outside edited value regions.
        # Re-parse once to keep in-memory spans and statuses authoritative.
        from .parser import parse as _parse
        from .parser import parse_lazy as _parse_lazy

        refresh_lazy = hasattr(pf.entries, "prefetch")
        refreshed = (
            _parse_lazy(pf.path, encoding=encoding)
            if refresh_lazy
            else _parse(pf.path, encoding=encoding)
        )
        pf.entries = refreshed.entries
        pf._raw = bytearray(refreshed.raw_bytes())
        pf.dirty = False
        return

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
                    e.key_hash,
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
                    e.key_hash,
                )
            )
    pf.entries = new_list
    pf._raw = buf
    pf.dirty = False
