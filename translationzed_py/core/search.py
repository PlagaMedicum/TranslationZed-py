from __future__ import annotations

import enum
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


class SearchField(enum.IntEnum):
    KEY = 0
    SOURCE = 1
    TRANSLATION = 2


@dataclass(frozen=True, slots=True)
class SearchRow:
    file: Path
    row: int
    key: str
    source: str
    value: str


@dataclass(frozen=True, slots=True)
class Match:
    file: Path
    row: int
    preview: str = ""


def _matches_literal(text: str, query: str) -> bool:
    if query in text:
        return True
    parts = [part for part in query.split() if part]
    # Phrase composition mode: allow non-contiguous token matches in order,
    # but only for meaningful multi-token queries.
    if len(parts) < 2 or sum(len(part) for part in parts) < 4:
        return False
    pos = 0
    for part in parts:
        found = text.find(part, pos)
        if found < 0:
            return False
        pos = found + len(part)
    return True


def _find_literal_span(text: str, query: str) -> tuple[int, int]:
    if not text:
        return (0, 0)
    direct = text.find(query)
    if direct >= 0:
        return (direct, len(query))
    parts = [part for part in query.split() if part]
    if not parts:
        return (0, 0)
    pos = 0
    first_start = -1
    first_len = 0
    for idx, part in enumerate(parts):
        found = text.find(part, pos)
        if found < 0:
            break
        if idx == 0:
            first_start = found
            first_len = len(part)
        pos = found + len(part)
    if first_start >= 0:
        return (first_start, first_len)
    return (0, min(len(text), max(1, len(query))))


def _compact_one_line(text: str) -> str:
    return " ".join(text.replace("\r", "\n").replace("\t", " ").split())


def _build_preview(text: str, *, start: int, length: int, width: int) -> str:
    if not text:
        return ""
    width = max(24, width)
    start = max(0, min(start, len(text)))
    length = max(1, length)
    left = max(0, start - width // 3)
    right = min(len(text), start + max(width - (start - left), length + 8))
    snippet = _compact_one_line(text[left:right])
    if left > 0 and snippet:
        snippet = f"…{snippet}"
    if right < len(text) and snippet:
        snippet = f"{snippet}…"
    if len(snippet) <= width:
        return snippet
    return snippet[: max(1, width - 1)].rstrip() + "…"


def iter_matches(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
    include_preview: bool = False,
    preview_chars: int = 96,
) -> Iterable[Match]:
    if not query:
        return
    if is_regex:
        try:
            flags = re.MULTILINE
            if not case_sensitive:
                flags |= re.IGNORECASE
            matcher = re.compile(query, flags)
        except re.error:
            return
        query_text = query
    else:
        matcher = None
        query_text = query
        if not case_sensitive:
            query_text = query.lower()

    for row in rows:
        if field is SearchField.KEY:
            text = row.key
        elif field is SearchField.SOURCE:
            text = row.source
        else:
            text = row.value
        text = text or ""
        if matcher:
            hit = matcher.search(text)
            if hit:
                preview = ""
                if include_preview:
                    preview = _build_preview(
                        text,
                        start=hit.start(),
                        length=max(1, hit.end() - hit.start()),
                        width=preview_chars,
                    )
                yield Match(row.file, row.row, preview)
        else:
            target = text if case_sensitive else text.lower()
            if _matches_literal(target, query_text):
                preview = ""
                if include_preview:
                    start, length = _find_literal_span(target, query_text)
                    preview = _build_preview(
                        text,
                        start=start,
                        length=length,
                        width=preview_chars,
                    )
                yield Match(row.file, row.row, preview)


def search(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
    include_preview: bool = False,
    preview_chars: int = 96,
) -> list[Match]:
    return list(
        iter_matches(
            rows,
            query,
            field,
            is_regex,
            case_sensitive=case_sensitive,
            include_preview=include_preview,
            preview_chars=preview_chars,
        )
    )
