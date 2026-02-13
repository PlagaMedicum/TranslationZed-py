from __future__ import annotations

import re
from pathlib import Path

import pytest

from translationzed_py.core.model import Entry, ParsedFile, Status
from translationzed_py.core.search import Match, SearchField, SearchRow
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileApplyCallbacks,
    ReplaceAllFileApplyResult,
    ReplaceAllFileCountCallbacks,
    ReplaceAllFileParseError,
    ReplaceAllRowsApplyResult,
    ReplaceAllRowsCallbacks,
    ReplaceCurrentRowCallbacks,
    ReplaceRequest,
    ReplaceRequestError,
    SearchMatchApplyPlan,
    SearchMatchOpenPlan,
    SearchReplaceService,
    SearchRowsBuildResult,
    SearchRowsCacheStamp,
    SearchRowsCacheStampCallbacks,
    SearchRowsFileCallbacks,
    SearchRowsSourcePlan,
    anchor_row,
    apply_replace_all,
    apply_replace_all_in_file,
    apply_replace_all_in_rows,
    apply_replace_in_row,
    build_match_apply_plan,
    build_match_open_plan,
    build_replace_all_plan,
    build_replace_all_run_plan,
    build_replace_request,
    build_rows_cache_lookup_plan,
    build_rows_cache_store_plan,
    build_rows_source_plan,
    build_search_rows,
    collect_rows_cache_stamp,
    count_replace_all_in_file,
    count_replace_all_in_rows,
    fallback_row,
    find_match_in_rows,
    load_search_rows_from_file,
    prioritize_current_file,
    replace_text,
    scope_files,
    scope_label,
    search_across_files,
    search_result_label,
    search_spec_for_column,
)
from translationzed_py.core.status_cache import CacheEntry, CacheMap


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


def test_search_replace_service_delegates_scope_and_search_spec_helpers() -> None:
    service = SearchReplaceService()
    current = Path("BE/ui.txt")
    files = service.scope_files(
        scope="FILE",
        current_file=current,
        current_locale="BE",
        selected_locales=["BE"],
        files_for_locale=lambda _loc: [],
    )
    field, include_source, include_value = service.search_spec_for_column(2)
    assert files == [current]
    assert field == SearchField.TRANSLATION
    assert include_source is False
    assert include_value is True


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


def test_search_result_label_includes_relative_path_row_and_preview() -> None:
    root = Path("/tmp/proj")
    match = Match(root / "BE" / "ui.txt", 7, preview="hello world")
    assert search_result_label(match=match, root=root) == "BE/ui.txt:8 · hello world"


def test_search_result_label_handles_external_path_without_preview() -> None:
    root = Path("/tmp/proj")
    external = Path("/var/tmp/external.txt")
    match = Match(external, 0)
    assert search_result_label(match=match, root=root) == f"{external}:1"


def test_build_search_panel_plan_with_truncation() -> None:
    root = Path("/tmp/proj")
    files = [root / "BE" / "a.txt", root / "BE" / "b.txt"]
    by_file = {
        files[0]: [
            Match(files[0], 0, preview="first"),
            Match(files[0], 1, preview="second"),
        ],
        files[1]: [Match(files[1], 0, preview="third")],
    }
    service = SearchReplaceService()
    plan = service.build_search_panel_plan(
        files=files,
        root=root,
        result_limit=2,
        iter_matches_for_file=lambda path: by_file.get(path, []),
    )
    assert plan.truncated is True
    assert plan.status_message == "Showing first 2 matches (limit 2)."
    assert len(plan.items) == 2
    assert plan.items[0].label == "BE/a.txt:1 · first"
    assert plan.items[1].label == "BE/a.txt:2 · second"


def test_build_search_panel_plan_without_matches() -> None:
    root = Path("/tmp/proj")
    files = [root / "BE" / "a.txt"]
    service = SearchReplaceService()
    plan = service.build_search_panel_plan(
        files=files,
        root=root,
        result_limit=10,
        iter_matches_for_file=lambda _path: [],
    )
    assert plan.truncated is False
    assert plan.items == ()
    assert plan.status_message == "No matches in current scope."


def test_build_search_run_plan_for_empty_query_and_missing_files() -> None:
    service = SearchReplaceService()
    empty_query = service.build_search_run_plan(
        query_text="   ",
        column=2,
        use_regex=False,
        files=[Path("a.txt")],
        current_file=Path("a.txt"),
        current_row=10,
        direction=1,
    )
    assert empty_query.run_search is False
    assert empty_query.status_message is None

    missing_files = service.build_search_run_plan(
        query_text="needle",
        column=2,
        use_regex=False,
        files=[],
        current_file=None,
        current_row=None,
        direction=1,
    )
    assert missing_files.run_search is False
    assert missing_files.status_message == "No files in current search scope."


def test_build_search_run_plan_resolves_search_field_and_anchor() -> None:
    service = SearchReplaceService()
    files = [Path("a.txt"), Path("b.txt")]
    plan = service.build_search_run_plan(
        query_text="needle",
        column=1,
        use_regex=True,
        files=files,
        current_file=None,
        current_row=None,
        direction=-1,
    )
    assert plan.run_search is True
    assert plan.query == "needle"
    assert plan.use_regex is True
    assert plan.field == SearchField.SOURCE
    assert plan.include_source is True
    assert plan.include_value is False
    assert plan.files == tuple(files)
    assert plan.anchor_path == files[0]
    assert plan.anchor_row > 1_000_000


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


def test_build_replace_all_run_plan_file_scope_skips_confirmation() -> None:
    files = [Path("a.txt")]
    plan = build_replace_all_run_plan(
        scope="FILE",
        current_locale="BE",
        selected_locale_count=1,
        files=files,
        current_file=Path("a.txt"),
        display_name=lambda path: path.stem,
        count_in_current=lambda: 3,
        count_in_file=lambda _path: 0,
    )
    assert plan is not None
    assert plan.run_replace is True
    assert plan.show_confirmation is False
    assert plan.scope_label == "File"


def test_build_replace_all_run_plan_multi_file_requires_confirmation() -> None:
    files = [Path("a.txt"), Path("b.txt")]
    plan = build_replace_all_run_plan(
        scope="LOCALE",
        current_locale="BE",
        selected_locale_count=2,
        files=files,
        current_file=Path("a.txt"),
        display_name=lambda path: path.stem,
        count_in_current=lambda: 1,
        count_in_file=lambda _path: 2,
    )
    assert plan is not None
    assert plan.run_replace is True
    assert plan.show_confirmation is True
    assert plan.scope_label == "Locale BE"
    assert list(plan.counts) == [("a", 1), ("b", 2)]


def test_build_replace_all_run_plan_multi_file_zero_total_skips_replace() -> None:
    files = [Path("a.txt"), Path("b.txt")]
    plan = build_replace_all_run_plan(
        scope="POOL",
        current_locale=None,
        selected_locale_count=2,
        files=files,
        current_file=Path("a.txt"),
        display_name=lambda path: path.stem,
        count_in_current=lambda: 0,
        count_in_file=lambda _path: 0,
    )
    assert plan is not None
    assert plan.run_replace is False
    assert plan.show_confirmation is False
    assert plan.scope_label == "Pool (2)"


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
    run_plan = service.build_replace_all_run_plan(
        scope="FILE",
        current_locale="BE",
        selected_locale_count=1,
        files=files,
        current_file=Path("a.txt"),
        display_name=lambda path: str(path),
        count_in_current=lambda: 1,
        count_in_file=lambda _path: 0,
    )
    assert run_plan is not None
    assert run_plan.run_replace is True


def _entry(key: str, value: str, status: Status = Status.UNTOUCHED) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=None,
    )


def test_count_replace_all_in_file_uses_cache_overlay_text() -> None:
    path = Path("BE/ui.txt")
    parsed = ParsedFile(path, [_entry("A", "Drop one"), _entry("B", "Rest")], b"")
    cache = CacheMap(hash_bits=64)
    cache[11] = CacheEntry(
        status=Status.TRANSLATED, value="Drop all", original="Drop one"
    )

    count = count_replace_all_in_file(
        path,
        pattern=re.compile("Drop"),
        replacement="Use",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        callbacks=ReplaceAllFileCountCallbacks(
            parse_file=lambda _path: parsed,
            read_cache=lambda _path: cache,
        ),
        hash_for_entry=lambda entry, _cache: 11 if entry.key == "A" else 12,
    )

    assert count == 1


def test_apply_replace_all_in_file_marks_translated_and_writes_cache() -> None:
    path = Path("BE/ui.txt")
    parsed = ParsedFile(path, [_entry("A", "Drop one")], b"")
    cache = CacheMap(hash_bits=64)
    writes: list[tuple[Path, list[Entry], set[str], dict[str, str]]] = []

    result = apply_replace_all_in_file(
        path,
        pattern=re.compile("Drop"),
        replacement="Use",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        callbacks=ReplaceAllFileApplyCallbacks(
            parse_file=lambda _path: parsed,
            read_cache=lambda _path: cache,
            write_cache=lambda file_path, entries, changed_keys, original_values: writes.append(
                (file_path, list(entries), set(changed_keys), dict(original_values))
            ),
        ),
        hash_for_entry=lambda _entry, _cache: 1,
    )

    assert result == ReplaceAllFileApplyResult(changed_keys={"A"}, changed_any=True)
    assert writes and writes[0][0] == path
    assert writes[0][2] == {"A"}
    assert writes[0][3] == {"A": "Drop one"}
    written_entry = writes[0][1][0]
    assert written_entry.value == "Use one"
    assert written_entry.status == Status.TRANSLATED


def test_count_replace_all_in_file_wraps_parse_error() -> None:
    path = Path("BE/ui.txt")
    callbacks = ReplaceAllFileCountCallbacks(
        parse_file=lambda _path: (_ for _ in ()).throw(ValueError("broken parse")),
        read_cache=lambda _path: CacheMap(),
    )

    try:
        count_replace_all_in_file(
            path,
            pattern=re.compile("x"),
            replacement="y",
            use_regex=False,
            matches_empty=False,
            has_group_ref=False,
            callbacks=callbacks,
            hash_for_entry=lambda _entry, _cache: 1,
        )
    except ReplaceAllFileParseError as exc:
        assert exc.path == path
        assert isinstance(exc.original, ValueError)
    else:  # pragma: no cover
        raise AssertionError("ReplaceAllFileParseError was not raised")


def test_count_replace_all_in_rows_counts_changed_rows() -> None:
    rows = ["Drop one", "Rest", "Drop all"]
    callbacks = ReplaceAllRowsCallbacks(
        row_count=lambda: len(rows),
        read_text=lambda row: rows[row],
        write_text=lambda _row, _text: None,
    )

    count = count_replace_all_in_rows(
        pattern=re.compile("Drop"),
        replacement="Use",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        callbacks=callbacks,
    )

    assert count == 2


def test_apply_replace_all_in_rows_updates_rows_via_callback() -> None:
    rows = ["Drop one", "Rest", "Drop all"]
    callbacks = ReplaceAllRowsCallbacks(
        row_count=lambda: len(rows),
        read_text=lambda row: rows[row],
        write_text=lambda row, text: rows.__setitem__(row, text),
    )

    result = apply_replace_all_in_rows(
        pattern=re.compile("Drop"),
        replacement="Use",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
        callbacks=callbacks,
    )

    assert result == ReplaceAllRowsApplyResult(changed_rows=2)
    assert rows == ["Use one", "Rest", "Use all"]


def test_build_replace_request_builds_case_sensitive_regex() -> None:
    request = build_replace_request(
        query="Drop",
        replacement="$1-all",
        use_regex=True,
        case_sensitive=True,
    )
    assert request is not None
    assert isinstance(request, ReplaceRequest)
    assert request.pattern.pattern == "Drop"
    assert request.use_regex is True
    assert request.matches_empty is False
    assert request.has_group_ref is True


def test_build_replace_request_returns_none_for_empty_query() -> None:
    assert (
        build_replace_request(
            query="",
            replacement="x",
            use_regex=False,
            case_sensitive=False,
        )
        is None
    )


def test_build_replace_request_raises_on_invalid_regex() -> None:
    with pytest.raises(ReplaceRequestError):
        build_replace_request(
            query="(",
            replacement="x",
            use_regex=True,
            case_sensitive=False,
        )


def test_apply_replace_in_row_uses_callbacks_and_returns_changed() -> None:
    rows = ["Drop one", "Rest"]
    request = ReplaceRequest(
        pattern=re.compile("Drop"),
        replacement="Use",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    callbacks = ReplaceCurrentRowCallbacks(
        read_text=lambda row: rows[row],
        write_text=lambda row, text: rows.__setitem__(row, text),
    )

    changed = apply_replace_in_row(row=0, request=request, callbacks=callbacks)
    unchanged = apply_replace_in_row(row=1, request=request, callbacks=callbacks)

    assert changed is True
    assert unchanged is False
    assert rows == ["Use one", "Rest"]


def test_build_rows_cache_lookup_plan_uses_cached_when_stamp_matches() -> None:
    path = Path("BE/ui.txt")
    cached = SearchRowsCacheStamp(
        file_mtime_ns=10,
        cache_mtime_ns=20,
        source_mtime_ns=30,
    )
    plan = build_rows_cache_lookup_plan(
        path=path,
        include_source=True,
        include_value=False,
        file_mtime_ns=10,
        cache_mtime_ns=20,
        source_mtime_ns=30,
        cached_stamp=cached,
    )
    assert plan.key.path == path
    assert plan.key.include_source is True
    assert plan.key.include_value is False
    assert plan.stamp == cached
    assert plan.use_cached_rows is True


def test_build_rows_cache_lookup_plan_miss_when_stamp_differs() -> None:
    path = Path("BE/ui.txt")
    cached = SearchRowsCacheStamp(
        file_mtime_ns=10,
        cache_mtime_ns=20,
        source_mtime_ns=30,
    )
    plan = build_rows_cache_lookup_plan(
        path=path,
        include_source=False,
        include_value=True,
        file_mtime_ns=11,
        cache_mtime_ns=20,
        source_mtime_ns=30,
        cached_stamp=cached,
    )
    assert plan.use_cached_rows is False


def test_collect_rows_cache_stamp_returns_none_without_file_mtime() -> None:
    stamp = collect_rows_cache_stamp(
        path=Path("BE/ui.txt"),
        include_source=True,
        include_value=True,
        callbacks=SearchRowsCacheStampCallbacks(
            file_mtime_ns=lambda _path: None,
            cache_mtime_ns=lambda _path: 22,
            source_mtime_ns=lambda _path: 33,
        ),
    )
    assert stamp is None


def test_collect_rows_cache_stamp_honors_include_flags() -> None:
    cache_calls: list[str] = []
    source_calls: list[str] = []
    stamp = collect_rows_cache_stamp(
        path=Path("BE/ui.txt"),
        include_source=False,
        include_value=False,
        callbacks=SearchRowsCacheStampCallbacks(
            file_mtime_ns=lambda _path: 11,
            cache_mtime_ns=lambda _path: cache_calls.append("cache") or 22,
            source_mtime_ns=lambda _path: source_calls.append("source") or 33,
        ),
    )
    assert stamp == SearchRowsCacheStamp(
        file_mtime_ns=11,
        cache_mtime_ns=0,
        source_mtime_ns=0,
    )
    assert not cache_calls
    assert not source_calls


def test_search_replace_service_wraps_collect_rows_cache_stamp() -> None:
    service = SearchReplaceService()
    stamp = service.collect_rows_cache_stamp(
        path=Path("BE/ui.txt"),
        include_source=True,
        include_value=True,
        callbacks=SearchRowsCacheStampCallbacks(
            file_mtime_ns=lambda _path: 11,
            cache_mtime_ns=lambda _path: 22,
            source_mtime_ns=lambda _path: 33,
        ),
    )
    assert stamp == SearchRowsCacheStamp(
        file_mtime_ns=11,
        cache_mtime_ns=22,
        source_mtime_ns=33,
    )


def test_build_rows_cache_store_plan_requires_materialized_and_limit() -> None:
    store = build_rows_cache_store_plan(
        rows_materialized=True,
        entry_count=100,
        cache_row_limit=1000,
    )
    too_large = build_rows_cache_store_plan(
        rows_materialized=True,
        entry_count=2000,
        cache_row_limit=1000,
    )
    not_materialized = build_rows_cache_store_plan(
        rows_materialized=False,
        entry_count=100,
        cache_row_limit=1000,
    )
    assert store.should_store_rows is True
    assert too_large.should_store_rows is False
    assert not_materialized.should_store_rows is False


def test_search_replace_service_wraps_rows_cache_helpers() -> None:
    service = SearchReplaceService()
    cached = SearchRowsCacheStamp(
        file_mtime_ns=1,
        cache_mtime_ns=2,
        source_mtime_ns=3,
    )
    lookup = service.build_rows_cache_lookup_plan(
        path=Path("BE/ui.txt"),
        include_source=True,
        include_value=True,
        file_mtime_ns=1,
        cache_mtime_ns=2,
        source_mtime_ns=3,
        cached_stamp=cached,
    )
    store = service.build_rows_cache_store_plan(
        rows_materialized=True,
        entry_count=10,
        cache_row_limit=100,
    )
    assert lookup.use_cached_rows is True
    assert store.should_store_rows is True


def test_build_rows_source_plan_handles_locale_and_model_flags() -> None:
    missing_locale = build_rows_source_plan(
        locale_known=False,
        is_current_file=True,
        has_current_model=True,
    )
    current_file_rows = build_rows_source_plan(
        locale_known=True,
        is_current_file=True,
        has_current_model=True,
    )
    cached_file_rows = build_rows_source_plan(
        locale_known=True,
        is_current_file=False,
        has_current_model=True,
    )
    assert missing_locale == SearchRowsSourcePlan(
        has_rows=False,
        use_active_model_rows=False,
    )
    assert current_file_rows == SearchRowsSourcePlan(
        has_rows=True,
        use_active_model_rows=True,
    )
    assert cached_file_rows == SearchRowsSourcePlan(
        has_rows=True,
        use_active_model_rows=False,
    )


def test_search_replace_service_wraps_rows_source_plan() -> None:
    service = SearchReplaceService()
    plan = service.build_rows_source_plan(
        locale_known=True,
        is_current_file=False,
        has_current_model=False,
    )
    assert plan == SearchRowsSourcePlan(
        has_rows=True,
        use_active_model_rows=False,
    )


def test_load_search_rows_from_file_uses_lazy_parser_and_overlays_cache() -> None:
    path = Path("BE/ui.txt")
    entries = [_entry("A", "file-a")]
    parsed = ParsedFile(path, entries, b"")
    cache = CacheMap(hash_bits=64)
    cache[11] = CacheEntry(Status.TRANSLATED, "cache-a", "orig-a")
    calls: list[str] = []
    result = load_search_rows_from_file(
        path=path,
        encoding="UTF-8",
        use_lazy_parser=True,
        include_source=True,
        include_value=True,
        cache_row_limit=100,
        callbacks=SearchRowsFileCallbacks(
            parse_eager=lambda _path, _enc: (_ for _ in ()).throw(
                AssertionError("eager parser should not be used")
            ),
            parse_lazy=lambda _path, _enc: parsed,
            read_cache=lambda _path: cache,
            load_source_lookup=lambda _pf: (
                calls.append("source") or ["src-a"],
                lambda key: f"lookup-{key}",
            ),
        ),
        hash_for_entry=lambda _entry, _cache: 11,
    )
    assert result is not None
    rows = list(result.rows)
    assert rows[0].value == "cache-a"
    assert rows[0].source == "src-a"
    assert calls == ["source"]


def test_load_search_rows_from_file_returns_none_on_parse_error() -> None:
    result = load_search_rows_from_file(
        path=Path("BE/ui.txt"),
        encoding="UTF-8",
        use_lazy_parser=False,
        include_source=False,
        include_value=False,
        cache_row_limit=100,
        callbacks=SearchRowsFileCallbacks(
            parse_eager=lambda _path, _enc: (_ for _ in ()).throw(ValueError("bad")),
            parse_lazy=lambda _path, _enc: (_ for _ in ()).throw(
                AssertionError("lazy parser should not be used")
            ),
            read_cache=lambda _path: (_ for _ in ()).throw(
                AssertionError("cache should not be read")
            ),
            load_source_lookup=lambda _pf: (_ for _ in ()).throw(
                AssertionError("source lookup should not run")
            ),
        ),
        hash_for_entry=lambda _entry, _cache: 0,
    )
    assert result is None


def test_search_replace_service_wraps_load_search_rows_from_file() -> None:
    service = SearchReplaceService()
    path = Path("BE/ui.txt")
    parsed = ParsedFile(path, [_entry("A", "value")], b"")
    result = service.load_search_rows_from_file(
        path=path,
        encoding="UTF-8",
        use_lazy_parser=False,
        include_source=False,
        include_value=False,
        cache_row_limit=100,
        callbacks=SearchRowsFileCallbacks(
            parse_eager=lambda _path, _enc: parsed,
            parse_lazy=lambda _path, _enc: parsed,
            read_cache=lambda _path: CacheMap(),
            load_source_lookup=lambda _pf: (None, lambda _key: ""),
        ),
        hash_for_entry=lambda _entry, _cache: 0,
    )
    assert result is not None
    assert [row.value for row in result.rows] == [""]


def test_build_search_rows_applies_cache_overlay_and_source_lookup() -> None:
    path = Path("BE/ui.txt")
    entries = [_entry("A", "file-a"), _entry("B", "file-b")]
    cache = CacheMap(hash_bits=64)
    cache[11] = CacheEntry(Status.TRANSLATED, "cache-a", "orig-a")
    result = build_search_rows(
        path=path,
        entries=entries,
        entry_count=len(entries),
        include_source=True,
        include_value=True,
        source_by_row=["src-0"],
        source_for_key=lambda key: f"lookup-{key}",
        cache_map=cache,
        cache_row_limit=100,
        hash_for_entry=lambda entry, _cache: 11 if entry.key == "A" else 22,
    )
    rows = list(result.rows)
    assert rows[0].source == "src-0"
    assert rows[0].value == "cache-a"
    assert rows[1].source == "lookup-B"
    assert rows[1].value == "file-b"
    assert result.entry_count == 2


def test_build_search_rows_uses_generator_above_limit() -> None:
    path = Path("BE/ui.txt")
    entries = [_entry("A", "v1"), _entry("B", "v2")]
    result = build_search_rows(
        path=path,
        entries=entries,
        entry_count=1000,
        include_source=False,
        include_value=True,
        source_by_row=None,
        source_for_key=lambda _key: "",
        cache_map=CacheMap(),
        cache_row_limit=10,
        hash_for_entry=lambda _entry, _cache: 0,
    )
    assert isinstance(result, SearchRowsBuildResult)
    assert not isinstance(result.rows, list)
    assert [row.value for row in result.rows] == ["v1", "v2"]


def test_search_replace_service_wraps_build_search_rows() -> None:
    service = SearchReplaceService()
    entries = [_entry("A", "v1")]
    result = service.build_search_rows(
        path=Path("BE/ui.txt"),
        entries=entries,
        entry_count=1,
        include_source=False,
        include_value=True,
        source_by_row=None,
        source_for_key=lambda _key: "",
        cache_map=CacheMap(),
        cache_row_limit=10,
        hash_for_entry=lambda _entry, _cache: 0,
    )
    assert isinstance(result, SearchRowsBuildResult)
    assert [row.value for row in result.rows] == ["v1"]


def test_build_match_open_plan_requires_open_for_other_file() -> None:
    same = build_match_open_plan(
        has_match=True,
        match_file=Path("BE/a.txt"),
        current_file=Path("BE/a.txt"),
    )
    other = build_match_open_plan(
        has_match=True,
        match_file=Path("BE/b.txt"),
        current_file=Path("BE/a.txt"),
    )
    missing = build_match_open_plan(
        has_match=False,
        match_file=None,
        current_file=Path("BE/a.txt"),
    )
    assert same == SearchMatchOpenPlan(
        open_target_file=False, target_file=Path("BE/a.txt")
    )
    assert other == SearchMatchOpenPlan(
        open_target_file=True, target_file=Path("BE/b.txt")
    )
    assert missing == SearchMatchOpenPlan(open_target_file=False, target_file=None)


def test_build_match_apply_plan_validates_selection_requirements() -> None:
    good = build_match_apply_plan(
        has_match=True,
        match_file=Path("BE/a.txt"),
        current_file=Path("BE/a.txt"),
        has_current_model=True,
        match_row=2,
        row_count=5,
        column=1,
    )
    bad = build_match_apply_plan(
        has_match=True,
        match_file=Path("BE/b.txt"),
        current_file=Path("BE/a.txt"),
        has_current_model=True,
        match_row=2,
        row_count=5,
        column=1,
    )
    assert good == SearchMatchApplyPlan(
        select_in_table=True,
        target_row=2,
        target_column=1,
    )
    assert bad == SearchMatchApplyPlan(
        select_in_table=False,
        target_row=2,
        target_column=1,
    )


def test_search_replace_service_wraps_match_selection_plans() -> None:
    service = SearchReplaceService()
    open_plan = service.build_match_open_plan(
        has_match=True,
        match_file=Path("BE/a.txt"),
        current_file=Path("BE/b.txt"),
    )
    apply_plan = service.build_match_apply_plan(
        has_match=True,
        match_file=Path("BE/a.txt"),
        current_file=Path("BE/a.txt"),
        has_current_model=True,
        match_row=0,
        row_count=1,
        column=2,
    )
    assert open_plan.open_target_file is True
    assert apply_plan.select_in_table is True
