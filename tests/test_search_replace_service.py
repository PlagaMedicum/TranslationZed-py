from __future__ import annotations

import re
from pathlib import Path

from translationzed_py.core.search import SearchField, SearchRow
from translationzed_py.core.search_replace_service import (
    SearchReplaceService,
    anchor_row,
    apply_replace_all,
    build_replace_all_plan,
    fallback_row,
    find_match_in_rows,
    prioritize_current_file,
    replace_text,
    scope_files,
    scope_label,
    search_across_files,
    search_spec_for_column,
)


def test_scope_files_resolves_file_locale_pool() -> None:
    current = Path("BE/ui.txt")
    files_by_locale = {
        "BE": [Path("BE/a.txt"), Path("BE/b.txt")],
        "RU": [Path("RU/a.txt")],
    }

    def resolver(locale: str) -> list[Path]:
        return files_by_locale.get(locale, [])

    assert scope_files(
        scope="FILE",
        current_file=current,
        current_locale="BE",
        selected_locales=["BE", "RU"],
        files_for_locale=resolver,
    ) == [current]
    assert (
        scope_files(
            scope="LOCALE",
            current_file=current,
            current_locale="BE",
            selected_locales=["BE", "RU"],
            files_for_locale=resolver,
        )
        == files_by_locale["BE"]
    )
    assert scope_files(
        scope="POOL",
        current_file=current,
        current_locale="BE",
        selected_locales=["BE", "RU"],
        files_for_locale=resolver,
    ) == [*files_by_locale["BE"], *files_by_locale["RU"]]


def test_prioritize_current_file_moves_current_to_front() -> None:
    files = [Path("a"), Path("b"), Path("c")]
    assert prioritize_current_file(files, Path("b")) == [
        Path("b"),
        Path("a"),
        Path("c"),
    ]
    assert prioritize_current_file(files, Path("x")) == files


def test_scope_label_and_search_spec() -> None:
    assert (
        scope_label(scope="LOCALE", current_locale="BE", selected_locale_count=3)
        == "Locale BE"
    )
    assert (
        scope_label(scope="POOL", current_locale=None, selected_locale_count=3)
        == "Pool (3)"
    )
    assert (
        scope_label(scope="FILE", current_locale="BE", selected_locale_count=3)
        == "File"
    )
    assert search_spec_for_column(0) == (SearchField.KEY, False, False)
    assert search_spec_for_column(1) == (SearchField.SOURCE, True, False)
    assert search_spec_for_column(2) == (SearchField.TRANSLATION, False, True)


def test_anchor_and_fallback_rows() -> None:
    assert anchor_row(4, 1) == 4
    assert anchor_row(None, 1) == -1
    assert anchor_row(None, -1) > 1_000_000
    assert fallback_row(1) == -1
    assert fallback_row(-1) > 1_000_000


def test_find_match_in_rows_forward_and_backward() -> None:
    rows = [
        SearchRow(Path("x"), 0, "A", "s0", "v0"),
        SearchRow(Path("x"), 1, "B", "s1", "needle"),
        SearchRow(Path("x"), 2, "C", "s2", "needle"),
    ]
    fwd = find_match_in_rows(
        rows,
        "needle",
        SearchField.TRANSLATION,
        False,
        start_row=0,
        direction=1,
    )
    back = find_match_in_rows(
        rows,
        "needle",
        SearchField.TRANSLATION,
        False,
        start_row=2,
        direction=-1,
    )
    assert fwd is not None and fwd.row == 1
    assert back is not None and back.row == 1


def test_find_match_in_rows_honors_case_sensitive_toggle() -> None:
    rows = [SearchRow(Path("x"), 0, "A", "Alpha", "Value")]

    insensitive = find_match_in_rows(
        rows,
        "alpha",
        SearchField.SOURCE,
        False,
        start_row=-1,
        direction=1,
        case_sensitive=False,
    )
    sensitive = find_match_in_rows(
        rows,
        "alpha",
        SearchField.SOURCE,
        False,
        start_row=-1,
        direction=1,
        case_sensitive=True,
    )

    assert insensitive is not None and insensitive.row == 0
    assert sensitive is None


def test_replace_text_single_and_all_modes() -> None:
    pattern = re.compile("a")
    changed, text = replace_text(
        "aba",
        pattern=pattern,
        replacement="x",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        mode="single",
    )
    assert changed is True
    assert text == "xba"

    changed, text = replace_text(
        "aba",
        pattern=pattern,
        replacement="x",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        mode="all",
    )
    assert changed is True
    assert text == "xbx"


def test_replace_text_handles_regex_groups_and_empty_match_case() -> None:
    pattern = re.compile(r"(foo)")
    changed, text = replace_text(
        "foo",
        pattern=pattern,
        replacement="$1-bar",
        use_regex=True,
        matches_empty=False,
        has_group_ref=True,
        mode="single",
    )
    assert changed is True
    assert text == "foo-bar"

    empty_pattern = re.compile("")
    changed, text = replace_text(
        "abc",
        pattern=empty_pattern,
        replacement="Z",
        use_regex=True,
        matches_empty=True,
        has_group_ref=False,
        mode="all",
    )
    assert changed is True
    assert text == "Z"

    changed, text = replace_text(
        "abc",
        pattern=empty_pattern,
        replacement="$0X",
        use_regex=True,
        matches_empty=True,
        has_group_ref=True,
        mode="all",
    )
    assert changed is True
    assert text == "Xabc"


def test_search_across_files_honors_direction_and_wrap() -> None:
    files = [Path("a.txt"), Path("b.txt"), Path("c.txt")]
    calls: list[tuple[Path, int]] = []

    def finder(path: Path, start_row: int):
        calls.append((path, start_row))
        if path == Path("b.txt") and start_row == 9:
            return None
        if path == Path("c.txt") and start_row == -1:
            return SearchRow(path, 2, "K", "", "match")
        return None

    match = search_across_files(
        files=files,
        anchor_path=Path("b.txt"),
        anchor_row=9,
        direction=1,
        wrap=True,
        find_in_file=finder,
    )

    assert match is not None and match.file == Path("c.txt") and match.row == 2
    assert calls[:2] == [(Path("b.txt"), 9), (Path("c.txt"), -1)]


def test_search_across_files_wraps_after_anchor_sequence() -> None:
    files = [Path("a.txt"), Path("b.txt"), Path("c.txt"), Path("d.txt")]
    calls: list[tuple[Path, int]] = []

    def finder(path: Path, start_row: int):
        calls.append((path, start_row))
        if path == Path("d.txt") and start_row == -1:
            return SearchRow(path, 3, "K", "", "match")
        return None

    match = search_across_files(
        files=files,
        anchor_path=Path("b.txt"),
        anchor_row=100,
        direction=1,
        wrap=True,
        find_in_file=finder,
    )

    assert match is not None and match.file == Path("d.txt")
    assert calls[:3] == [
        (Path("b.txt"), 100),
        (Path("c.txt"), -1),
        (Path("d.txt"), -1),
    ]


def test_search_across_files_no_wrap_returns_none() -> None:
    files = [Path("a.txt"), Path("b.txt")]
    match = search_across_files(
        files=files,
        anchor_path=Path("a.txt"),
        anchor_row=3,
        direction=1,
        wrap=False,
        find_in_file=lambda _path, _row: None,
    )
    assert match is None


def test_search_replace_service_wraps_search_across_files() -> None:
    service = SearchReplaceService()
    files = [Path("a.txt"), Path("b.txt")]
    match = service.search_across_files(
        files=files,
        anchor_path=Path("x.txt"),
        anchor_row=-1,
        direction=1,
        wrap=True,
        find_in_file=lambda path, _row: (
            SearchRow(path, 1, "K", "", "m") if path == Path("a.txt") else None
        ),
    )
    assert match is not None and match.file == Path("a.txt")


def test_build_replace_all_plan_aggregates_counts() -> None:
    files = [Path("a.txt"), Path("b.txt"), Path("c.txt")]
    plan = build_replace_all_plan(
        files=files,
        current_file=Path("b.txt"),
        display_name=lambda path: path.stem,
        count_in_current=lambda: 2,
        count_in_file=lambda path: 1 if path != Path("c.txt") else 0,
    )
    assert plan is not None
    assert plan.total == 3
    assert plan.counts == [("a", 1), ("b", 2)]


def test_apply_replace_all_runs_current_then_other_files() -> None:
    files = [Path("a.txt"), Path("b.txt"), Path("c.txt")]
    calls: list[str] = []

    ok = apply_replace_all(
        files=files,
        current_file=Path("b.txt"),
        apply_in_current=lambda: calls.append("current") is None or True,
        apply_in_file=lambda path: calls.append(path.name) is None or True,
    )

    assert ok is True
    assert calls == ["current", "a.txt", "c.txt"]


def test_search_replace_service_wraps_replace_all_helpers() -> None:
    service = SearchReplaceService()
    files = [Path("a.txt")]
    plan = service.build_replace_all_plan(
        files=files,
        current_file=Path("a.txt"),
        display_name=lambda path: str(path),
        count_in_current=lambda: 4,
        count_in_file=lambda _path: 0,
    )
    assert plan is not None
    assert plan.total == 4
    assert service.apply_replace_all(
        files=files,
        current_file=Path("a.txt"),
        apply_in_current=lambda: True,
        apply_in_file=lambda _path: True,
    )
