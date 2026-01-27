from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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


def search(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
) -> list[Match]:
    if not query:
        return []
    if is_regex:
        try:
            matcher = re.compile(query, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return []
    else:
        matcher = None
        query = query.lower()

    matches: list[Match] = []
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
                matches.append(Match(row.file, row.row))
        else:
            if query in text.lower():
                matches.append(Match(row.file, row.row))
    return matches
