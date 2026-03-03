"""Wave-2 search equivalence tests for optimized query-plan reuse."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from translationzed_py.core.search import (
    Match,
    SearchField,
    SearchRow,
    _build_preview,
    _find_literal_span,
    _matches_literal,
    iter_matches,
)
from translationzed_py.core.search_replace_service import (
    SearchReplaceService,
    search_across_files,
)


def _legacy_iter_matches(
    rows: list[SearchRow],
    *,
    query: str,
    field: SearchField,
    is_regex: bool,
    case_sensitive: bool,
    include_preview: bool,
    preview_chars: int = 96,
) -> list[Match]:
    if not query:
        return []
    if field is SearchField.KEY:
        attr = "key"
    elif field is SearchField.SOURCE:
        attr = "source"
    else:
        attr = "value"
    if is_regex:
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        try:
            matcher = re.compile(query, flags)
        except re.error:
            return []
        results: list[Match] = []
        for row in rows:
            text = getattr(row, attr) or ""
            hit = matcher.search(text)
            if not hit:
                continue
            preview = ""
            if include_preview:
                preview = _build_preview(
                    text,
                    start=hit.start(),
                    length=max(1, hit.end() - hit.start()),
                    width=preview_chars,
                )
            results.append(Match(row.file, row.row, preview))
        return results

    query_text = query if case_sensitive else query.lower()
    results = []
    for row in rows:
        text = getattr(row, attr) or ""
        target = text if case_sensitive else text.lower()
        if not _matches_literal(target, query_text):
            continue
        preview = ""
        if include_preview:
            start, length = _find_literal_span(target, query_text)
            preview = _build_preview(
                text,
                start=start,
                length=length,
                width=preview_chars,
            )
        results.append(Match(row.file, row.row, preview))
    return results


def _rows() -> list[SearchRow]:
    path = Path("BE/ui.txt")
    return [
        SearchRow(path, 0, "K_ZERO", "Alpha line one", "Value token 00000"),
        SearchRow(path, 1, "K_ONE", "Needle target", "Drop all"),
        SearchRow(path, 2, "K_TWO", "beta GAMMA", "Drop one"),
        SearchRow(path, 3, "K_THREE", "Combat <BR> Mechanics", "value token 00003"),
        SearchRow(path, 4, "REGEX_4", "xXx", "match-42"),
    ]


@pytest.mark.parametrize(
    ("query", "field", "is_regex", "case_sensitive", "include_preview"),
    [
        ("drop", SearchField.TRANSLATION, False, False, False),
        ("drop", SearchField.TRANSLATION, False, True, False),
        ("combat mechanics", SearchField.SOURCE, False, False, False),
        ("beta gamma", SearchField.SOURCE, False, False, True),
        (r"REGEX_\d", SearchField.KEY, True, True, False),
        (r"match-\d+", SearchField.TRANSLATION, True, True, True),
        ("(", SearchField.KEY, True, False, False),
    ],
)
def test_wave2_iter_matches_matches_legacy_reference(
    query: str,
    field: SearchField,
    is_regex: bool,
    case_sensitive: bool,
    include_preview: bool,
) -> None:
    """Verify optimized search iter matches legacy reference output."""
    rows = _rows()
    service = SearchReplaceService()
    prepared_plan = service.prepare_search_plan(
        query=query,
        use_regex=is_regex,
        case_sensitive=case_sensitive,
    )

    expected = _legacy_iter_matches(
        rows,
        query=query,
        field=field,
        is_regex=is_regex,
        case_sensitive=case_sensitive,
        include_preview=include_preview,
    )
    actual = list(
        iter_matches(
            rows,
            query,
            field,
            is_regex,
            case_sensitive=case_sensitive,
            include_preview=include_preview,
            prepared_plan=prepared_plan,
        )
    )
    assert actual == expected


def test_wave2_search_across_files_with_prepared_plan_matches_unprepared() -> None:
    """Verify prepared-plan reuse keeps match traversal semantics unchanged."""
    service = SearchReplaceService()
    files = [Path("a.txt"), Path("b.txt"), Path("c.txt")]
    rows_by_file = {
        files[0]: [
            SearchRow(files[0], 0, "A0", "s", "none"),
            SearchRow(files[0], 1, "A1", "s", "needle"),
        ],
        files[1]: [
            SearchRow(files[1], 0, "B0", "s", "none"),
            SearchRow(files[1], 1, "B1", "s", "none"),
        ],
        files[2]: [
            SearchRow(files[2], 0, "C0", "s", "needle"),
            SearchRow(files[2], 1, "C1", "s", "none"),
        ],
    }
    prepared_plan = service.prepare_search_plan(
        query="needle",
        use_regex=False,
        case_sensitive=False,
    )

    def _finder_unprepared(path: Path, start_row: int) -> Match | None:
        return service.find_match_in_rows(
            rows_by_file[path],
            "needle",
            SearchField.TRANSLATION,
            False,
            start_row=start_row,
            direction=1,
            case_sensitive=False,
        )

    def _finder_prepared(path: Path, start_row: int) -> Match | None:
        return service.find_match_in_rows(
            rows_by_file[path],
            "needle",
            SearchField.TRANSLATION,
            False,
            start_row=start_row,
            direction=1,
            case_sensitive=False,
            prepared_plan=prepared_plan,
        )

    expected = search_across_files(
        files=files,
        anchor_path=files[1],
        anchor_row=0,
        direction=1,
        wrap=True,
        find_in_file=_finder_unprepared,
    )
    actual = search_across_files(
        files=files,
        anchor_path=files[1],
        anchor_row=0,
        direction=1,
        wrap=True,
        find_in_file=_finder_prepared,
    )
    assert actual == expected
