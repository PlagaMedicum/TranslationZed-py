"""Test module for core search."""

from pathlib import Path

from translationzed_py.core.search import (
    SearchField,
    SearchRow,
    _build_preview,
    _find_literal_span,
    _matches_literal,
    search,
)


def test_search_plain_text():
    """Verify search plain text."""
    rows = [
        SearchRow(Path("A.txt"), 0, "KEY_ONE", "Source", "Value One"),
        SearchRow(Path("A.txt"), 1, "KEY_TWO", "Other", "Value Two"),
    ]
    matches = search(rows, "two", SearchField.TRANSLATION, False)
    assert [m.row for m in matches] == [1]


def test_search_regex():
    """Verify search regex."""
    rows = [
        SearchRow(Path("A.txt"), 0, "KEY_ONE", "Source", "Value One"),
        SearchRow(Path("A.txt"), 1, "KEY_TWO", "Other", "Value Two"),
    ]
    matches = search(rows, r"KEY_\w+", SearchField.KEY, True)
    assert [m.row for m in matches] == [0, 1]


def test_search_plain_composed_phrase_matches_non_contiguous_tokens():
    """Verify search plain composed phrase matches non contiguous tokens."""
    rows = [
        SearchRow(
            Path("A.txt"),
            0,
            "KEY_ONE",
            "<H1> COMBAT <BR> <TEXT> Mechanics section",
            "",
        ),
    ]
    matches = search(rows, "combat mechanics", SearchField.SOURCE, False)
    assert [m.row for m in matches] == [0]


def test_search_preview_is_one_line_and_present_for_literal_match():
    """Verify search preview is one line and present for literal match."""
    rows = [
        SearchRow(
            Path("A.txt"),
            0,
            "KEY_ONE",
            "Line one\nLine two with Needle token\nLine three",
            "",
        ),
    ]
    matches = search(
        rows,
        "needle",
        SearchField.SOURCE,
        False,
        include_preview=True,
        case_sensitive=False,
    )
    assert len(matches) == 1
    assert "Needle" in matches[0].preview
    assert "\n" not in matches[0].preview


def test_search_returns_empty_for_empty_query_and_invalid_regex():
    """Verify search returns no results for empty and invalid patterns."""
    rows = [SearchRow(Path("A.txt"), 0, "KEY_ONE", "Source", "Value")]
    assert search(rows, "", SearchField.KEY, False) == []
    assert search(rows, "(", SearchField.KEY, True) == []


def test_search_case_sensitive_toggle_applies_to_literal_queries():
    """Verify search literal mode honors case-sensitive toggles."""
    rows = [SearchRow(Path("A.txt"), 0, "KEY_ONE", "Needle", "Value")]
    assert search(rows, "needle", SearchField.SOURCE, False, case_sensitive=True) == []
    assert search(rows, "needle", SearchField.SOURCE, False, case_sensitive=False)


def test_matches_literal_rejects_short_or_misaligned_token_queries():
    """Verify literal matcher composition rules reject weak phrase matches."""
    assert _matches_literal("alphabet", "a b") is False
    assert _matches_literal("alpha beta gamma", "beta alpha") is False
    assert _matches_literal("alpha beta gamma", "alpha gamma") is True


def test_find_literal_span_handles_direct_partial_and_fallback_paths():
    """Verify literal span finder covers direct and fallback paths."""
    assert _find_literal_span("", "needle") == (0, 0)
    assert _find_literal_span("alpha beta", "beta") == (6, 4)
    assert _find_literal_span("alpha beta gamma", "alpha delta") == (0, 5)
    assert _find_literal_span("alpha beta", "delta gamma") == (0, 10)
    assert _find_literal_span("alpha beta", "   ") == (0, 0)


def test_build_preview_adds_ellipsis_and_compacts_whitespace():
    """Verify preview builder compacts text and applies edge ellipses."""
    text = (
        "prefix segment one two three "
        "needle token appears here "
        "with trailing details and tail"
    )
    preview = _build_preview(text, start=28, length=6, width=24)
    assert preview.startswith("…")
    assert preview.endswith("…")
    assert "\n" not in preview

    assert _build_preview("", start=0, length=0, width=10) == ""
