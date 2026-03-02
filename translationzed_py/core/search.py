"""Provide search helpers for keys, source text, and translations."""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from operator import attrgetter
from pathlib import Path


class SearchField(enum.IntEnum):
    """Identify which entry field is used during matching."""

    KEY = 0
    SOURCE = 1
    TRANSLATION = 2


@dataclass(frozen=True, slots=True)
class SearchRow:
    """Store normalized searchable text for one translation row."""

    file: Path
    row: int
    key: str
    source: str
    value: str
    key_fold: str = field(init=False, repr=False, compare=False)
    source_fold: str = field(init=False, repr=False, compare=False)
    value_fold: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Precompute lowercase fields for case-insensitive search."""
        object.__setattr__(self, "key_fold", (self.key or "").lower())
        object.__setattr__(self, "source_fold", (self.source or "").lower())
        object.__setattr__(self, "value_fold", (self.value or "").lower())


@dataclass(frozen=True, slots=True)
class Match:
    """Describe one search hit and optional preview snippet."""

    file: Path
    row: int
    preview: str = ""


@dataclass(frozen=True, slots=True)
class _LiteralQueryPlan:
    query: str
    parts: tuple[str, ...]
    composed_enabled: bool


@dataclass(frozen=True, slots=True)
class SearchQueryPlan:
    """Store precomputed query data for repeated match scans."""

    matcher: re.Pattern[str] | None
    query_text: str
    literal_plan: _LiteralQueryPlan | None


def _build_literal_query_plan(query: str) -> _LiteralQueryPlan:
    parts = tuple(part for part in query.split() if part)
    total_chars = sum(len(part) for part in parts)
    return _LiteralQueryPlan(
        query=query,
        parts=parts,
        composed_enabled=len(parts) >= 2 and total_chars >= 4,
    )


def prepare_search_plan(
    query: str,
    *,
    is_regex: bool,
    case_sensitive: bool,
) -> SearchQueryPlan | None:
    """Return reusable query plan state, or ``None`` for empty/invalid input."""
    if not query:
        return None
    if is_regex:
        try:
            flags = re.MULTILINE
            if not case_sensitive:
                flags |= re.IGNORECASE
            matcher = re.compile(query, flags)
        except re.error:
            return None
        return SearchQueryPlan(matcher=matcher, query_text=query, literal_plan=None)
    query_text = query if case_sensitive else query.lower()
    return SearchQueryPlan(
        matcher=None,
        query_text=query_text,
        literal_plan=_build_literal_query_plan(query_text),
    )


def _matches_literal(
    text: str, query: str, *, plan: _LiteralQueryPlan | None = None
) -> bool:
    literal_plan = plan or _build_literal_query_plan(query)
    if literal_plan.query in text:
        return True
    # Phrase composition mode: allow non-contiguous token matches in order,
    # but only for meaningful multi-token queries.
    if not literal_plan.composed_enabled:
        return False
    pos = 0
    for part in literal_plan.parts:
        found = text.find(part, pos)
        if found < 0:
            return False
        pos = found + len(part)
    return True


def _match_literal_index(
    text: str,
    query: str,
    *,
    plan: _LiteralQueryPlan,
) -> tuple[int, int]:
    direct = text.find(query)
    if direct >= 0:
        return (direct, len(query))
    if not plan.composed_enabled:
        return (-1, 0)
    pos = 0
    first_start = -1
    first_len = 0
    for idx, part in enumerate(plan.parts):
        found = text.find(part, pos)
        if found < 0:
            return (-1, 0)
        if idx == 0:
            first_start = found
            first_len = len(part)
        pos = found + len(part)
    return (first_start, first_len)


def _find_literal_span(
    text: str, query: str, *, plan: _LiteralQueryPlan | None = None
) -> tuple[int, int]:
    literal_plan = plan or _build_literal_query_plan(query)
    if not text:
        return (0, 0)
    direct, direct_len = _match_literal_index(
        text,
        literal_plan.query,
        plan=literal_plan,
    )
    if direct >= 0:
        return (direct, direct_len)
    if not literal_plan.parts:
        return (0, 0)
    pos = 0
    first_start = -1
    first_len = 0
    for idx, part in enumerate(literal_plan.parts):
        found = text.find(part, pos)
        if found < 0:
            break
        if idx == 0:
            first_start = found
            first_len = len(part)
        pos = found + len(part)
    if first_start >= 0:
        return (first_start, first_len)
    return (0, min(len(text), max(1, len(literal_plan.query))))


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


def _row_accessors(
    field: SearchField,
) -> tuple[
    Callable[[SearchRow], str],
    Callable[[SearchRow], str],
]:
    if field is SearchField.KEY:
        return attrgetter("key"), attrgetter("key_fold")
    if field is SearchField.SOURCE:
        return attrgetter("source"), attrgetter("source_fold")
    return attrgetter("value"), attrgetter("value_fold")


def _iter_matches_with_plan(
    rows: Iterable[SearchRow],
    *,
    plan: SearchQueryPlan,
    field: SearchField,
    case_sensitive: bool,
    include_preview: bool,
    preview_chars: int,
) -> Iterable[Match]:
    raw_get, norm_get = _row_accessors(field)
    matcher = plan.matcher
    if matcher is not None:
        build_preview = _build_preview
        for row in rows:
            text = raw_get(row) or ""
            hit = matcher.search(text)
            if not hit:
                continue
            preview = ""
            if include_preview:
                preview = build_preview(
                    text,
                    start=hit.start(),
                    length=max(1, hit.end() - hit.start()),
                    width=preview_chars,
                )
            yield Match(row.file, row.row, preview)
        return

    literal_plan = plan.literal_plan or _build_literal_query_plan(plan.query_text)
    query_text = plan.query_text
    build_preview = _build_preview
    match_index = _match_literal_index
    direct_query = literal_plan.query
    composed_enabled = literal_plan.composed_enabled
    query_parts = literal_plan.parts

    if case_sensitive:
        if not include_preview:
            if not composed_enabled:
                for row in rows:
                    text = raw_get(row) or ""
                    if direct_query in text:
                        yield Match(row.file, row.row)
                return
            for row in rows:
                text = raw_get(row) or ""
                if direct_query in text:
                    yield Match(row.file, row.row)
                    continue
                pos = 0
                for part in query_parts:
                    found = text.find(part, pos)
                    if found < 0:
                        break
                    pos = found + len(part)
                else:
                    yield Match(row.file, row.row)
            return
        for row in rows:
            text = raw_get(row) or ""
            start, length = match_index(text, query_text, plan=literal_plan)
            if start < 0:
                continue
            preview = build_preview(
                text,
                start=start,
                length=length,
                width=preview_chars,
            )
            yield Match(row.file, row.row, preview)
        return

    if not include_preview:
        if not composed_enabled:
            for row in rows:
                target = norm_get(row)
                if direct_query in target:
                    yield Match(row.file, row.row)
            return
        for row in rows:
            target = norm_get(row)
            if direct_query in target:
                yield Match(row.file, row.row)
                continue
            pos = 0
            for part in query_parts:
                found = target.find(part, pos)
                if found < 0:
                    break
                pos = found + len(part)
            else:
                yield Match(row.file, row.row)
        return

    for row in rows:
        raw_text = raw_get(row) or ""
        target = norm_get(row)
        start, length = match_index(target, query_text, plan=literal_plan)
        if start < 0:
            continue
        preview = build_preview(
            raw_text,
            start=start,
            length=length,
            width=preview_chars,
        )
        yield Match(row.file, row.row, preview)


def iter_matches(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
    include_preview: bool = False,
    preview_chars: int = 96,
    prepared_plan: SearchQueryPlan | None = None,
) -> Iterable[Match]:
    """Yield matches for a query across rows with literal or regex mode."""
    plan = prepared_plan
    if plan is None:
        plan = prepare_search_plan(
            query,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
        )
    if plan is None:
        return
    yield from _iter_matches_with_plan(
        rows,
        plan=plan,
        field=field,
        case_sensitive=case_sensitive,
        include_preview=include_preview,
        preview_chars=preview_chars,
    )


def search(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    is_regex: bool,
    *,
    case_sensitive: bool = False,
    include_preview: bool = False,
    preview_chars: int = 96,
    prepared_plan: SearchQueryPlan | None = None,
) -> list[Match]:
    """Collect and return all matches from :func:`iter_matches`."""
    plan = prepared_plan
    if plan is None:
        plan = prepare_search_plan(
            query,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
        )
    if plan is None:
        return []
    return list(
        _iter_matches_with_plan(
            rows,
            plan=plan,
            field=field,
            case_sensitive=case_sensitive,
            include_preview=include_preview,
            preview_chars=preview_chars,
        )
    )
