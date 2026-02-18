"""Test module for core search."""

from pathlib import Path

from translationzed_py.core.search import SearchField, SearchRow, search


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
