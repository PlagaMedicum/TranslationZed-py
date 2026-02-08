from pathlib import Path

from translationzed_py.core.search import SearchField, SearchRow, search


def test_search_plain_text():
    rows = [
        SearchRow(Path("A.txt"), 0, "KEY_ONE", "Source", "Value One"),
        SearchRow(Path("A.txt"), 1, "KEY_TWO", "Other", "Value Two"),
    ]
    matches = search(rows, "two", SearchField.TRANSLATION, False)
    assert [m.row for m in matches] == [1]


def test_search_regex():
    rows = [
        SearchRow(Path("A.txt"), 0, "KEY_ONE", "Source", "Value One"),
        SearchRow(Path("A.txt"), 1, "KEY_TWO", "Other", "Value Two"),
    ]
    matches = search(rows, r"KEY_\w+", SearchField.KEY, True)
    assert [m.row for m in matches] == [0, 1]


def test_search_plain_composed_phrase_matches_non_contiguous_tokens():
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
