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


def iter_matches(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
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
    else:
        matcher = None
        if not case_sensitive:
            query = query.lower()

    for row in rows:
        if field is SearchField.KEY:
            text = row.key
        elif field is SearchField.SOURCE:
            text = row.source
        else:
            text = row.value
        text = text or ""
        if matcher:
            if matcher.search(text):
                yield Match(row.file, row.row)
        else:
            target = text if case_sensitive else text.lower()
            if _matches_literal(target, query):
                yield Match(row.file, row.row)


def search(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
) -> list[Match]:
    return list(
        iter_matches(
            rows,
            query,
            field,
            is_regex,
            case_sensitive=case_sensitive,
        )
    )
