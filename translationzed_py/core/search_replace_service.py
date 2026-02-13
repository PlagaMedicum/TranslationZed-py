from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .model import Entry, Status
from .search import Match, SearchField, SearchRow, iter_matches
from .status_cache import CacheEntry

if TYPE_CHECKING:
    from .model import ParsedFile


@dataclass(frozen=True, slots=True)
class ReplaceAllPlan:
    total: int
    counts: list[tuple[str, int]]


@dataclass(frozen=True, slots=True)
class ReplaceRequest:
    pattern: re.Pattern[str]
    replacement: str
    use_regex: bool
    matches_empty: bool
    has_group_ref: bool


@dataclass(frozen=True, slots=True)
class ReplaceAllRunPlan:
    run_replace: bool
    show_confirmation: bool
    scope_label: str
    counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class ReplaceAllFileCountCallbacks:
    parse_file: Callable[[Path], ParsedFile]
    read_cache: Callable[[Path], Mapping[int, CacheEntry]]


@dataclass(frozen=True, slots=True)
class ReplaceAllFileApplyCallbacks:
    parse_file: Callable[[Path], ParsedFile]
    read_cache: Callable[[Path], Mapping[int, CacheEntry]]
    write_cache: Callable[[Path, Iterable[Entry], set[str], Mapping[str, str]], object]


@dataclass(frozen=True, slots=True)
class ReplaceAllFileApplyResult:
    changed_keys: set[str]
    changed_any: bool


@dataclass(frozen=True, slots=True)
class ReplaceAllRowsCallbacks:
    row_count: Callable[[], int]
    read_text: Callable[[int], str | None]
    write_text: Callable[[int, str], object]


@dataclass(frozen=True, slots=True)
class ReplaceAllRowsApplyResult:
    changed_rows: int


@dataclass(frozen=True, slots=True)
class ReplaceCurrentRowCallbacks:
    read_text: Callable[[int], str | None]
    write_text: Callable[[int, str], object]


class ReplaceRequestError(Exception):
    pass


class ReplaceAllFileParseError(Exception):
    def __init__(self, *, path: Path, original: Exception) -> None:
        super().__init__(str(original))
        self.path = path
        self.original = original


@dataclass(frozen=True, slots=True)
class SearchPanelItem:
    file: Path
    row: int
    label: str


@dataclass(frozen=True, slots=True)
class SearchPanelPlan:
    status_message: str
    items: tuple[SearchPanelItem, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class SearchRunPlan:
    run_search: bool
    query: str
    use_regex: bool
    field: SearchField | None
    include_source: bool
    include_value: bool
    files: tuple[Path, ...]
    anchor_path: Path | None
    anchor_row: int
    status_message: str | None


@dataclass(frozen=True, slots=True)
class SearchRowsCacheKey:
    path: Path
    include_source: bool
    include_value: bool


@dataclass(frozen=True, slots=True)
class SearchRowsCacheStamp:
    file_mtime_ns: int
    cache_mtime_ns: int
    source_mtime_ns: int


@dataclass(frozen=True, slots=True)
class SearchRowsCacheLookupPlan:
    key: SearchRowsCacheKey
    stamp: SearchRowsCacheStamp
    use_cached_rows: bool


@dataclass(frozen=True, slots=True)
class SearchRowsCacheStorePlan:
    should_store_rows: bool


@dataclass(frozen=True, slots=True)
class SearchRowsCacheStampCallbacks:
    file_mtime_ns: Callable[[Path], int | None]
    cache_mtime_ns: Callable[[Path], int]
    source_mtime_ns: Callable[[Path], int]


@dataclass(frozen=True, slots=True)
class SearchRowsSourcePlan:
    has_rows: bool
    use_active_model_rows: bool


@dataclass(frozen=True, slots=True)
class SearchRowsFileCallbacks:
    parse_eager: Callable[[Path, str], ParsedFile]
    parse_lazy: Callable[[Path, str], ParsedFile]
    read_cache: Callable[[Path], Mapping[int, CacheEntry]]
    load_source_lookup: Callable[
        [ParsedFile], tuple[Sequence[str] | None, Callable[[str], str]]
    ]


@dataclass(frozen=True, slots=True)
class SearchRowsBuildResult:
    rows: Iterable[SearchRow]
    entry_count: int


@dataclass(frozen=True, slots=True)
class SearchMatchOpenPlan:
    open_target_file: bool
    target_file: Path | None


@dataclass(frozen=True, slots=True)
class SearchMatchApplyPlan:
    select_in_table: bool
    target_row: int
    target_column: int


@dataclass(frozen=True, slots=True)
class SearchReplaceService:
    def scope_files(
        self,
        *,
        scope: str,
        current_file: Path | None,
        current_locale: str | None,
        selected_locales: Iterable[str],
        files_for_locale: Callable[[str], list[Path]],
    ) -> list[Path]:
        return scope_files(
            scope=scope,
            current_file=current_file,
            current_locale=current_locale,
            selected_locales=selected_locales,
            files_for_locale=files_for_locale,
        )

    def search_spec_for_column(self, column: int) -> tuple[SearchField, bool, bool]:
        return search_spec_for_column(column)

    def find_match_in_rows(
        self,
        rows: Iterable[SearchRow],
        query: str,
        field: SearchField,
        use_regex: bool,
        *,
        start_row: int,
        direction: int,
        case_sensitive: bool,
    ) -> Match | None:
        return find_match_in_rows(
            rows,
            query,
            field,
            use_regex,
            start_row=start_row,
            direction=direction,
            case_sensitive=case_sensitive,
        )

    def search_across_files(
        self,
        *,
        files: list[Path],
        anchor_path: Path | None,
        anchor_row: int,
        direction: int,
        wrap: bool,
        find_in_file: Callable[[Path, int], Match | None],
    ) -> Match | None:
        return search_across_files(
            files=files,
            anchor_path=anchor_path,
            anchor_row=anchor_row,
            direction=direction,
            wrap=wrap,
            find_in_file=find_in_file,
        )

    def build_replace_all_plan(
        self,
        *,
        files: list[Path],
        current_file: Path | None,
        display_name: Callable[[Path], str],
        count_in_current: Callable[[], int | None],
        count_in_file: Callable[[Path], int | None],
    ) -> ReplaceAllPlan | None:
        return build_replace_all_plan(
            files=files,
            current_file=current_file,
            display_name=display_name,
            count_in_current=count_in_current,
            count_in_file=count_in_file,
        )

    def build_replace_request(
        self,
        *,
        query: str,
        replacement: str,
        use_regex: bool,
        case_sensitive: bool,
    ) -> ReplaceRequest | None:
        return build_replace_request(
            query=query,
            replacement=replacement,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
        )

    def build_replace_all_run_plan(
        self,
        *,
        scope: str,
        current_locale: str | None,
        selected_locale_count: int,
        files: list[Path],
        current_file: Path | None,
        display_name: Callable[[Path], str],
        count_in_current: Callable[[], int | None],
        count_in_file: Callable[[Path], int | None],
    ) -> ReplaceAllRunPlan | None:
        return build_replace_all_run_plan(
            scope=scope,
            current_locale=current_locale,
            selected_locale_count=selected_locale_count,
            files=files,
            current_file=current_file,
            display_name=display_name,
            count_in_current=count_in_current,
            count_in_file=count_in_file,
        )

    def apply_replace_all(
        self,
        *,
        files: list[Path],
        current_file: Path | None,
        apply_in_current: Callable[[], bool],
        apply_in_file: Callable[[Path], bool],
    ) -> bool:
        return apply_replace_all(
            files=files,
            current_file=current_file,
            apply_in_current=apply_in_current,
            apply_in_file=apply_in_file,
        )

    def apply_replace_in_row(
        self,
        *,
        row: int,
        request: ReplaceRequest,
        callbacks: ReplaceCurrentRowCallbacks,
    ) -> bool:
        return apply_replace_in_row(
            row=row,
            request=request,
            callbacks=callbacks,
        )

    def count_replace_all_in_file(
        self,
        path: Path,
        *,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
        callbacks: ReplaceAllFileCountCallbacks,
        hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
    ) -> int:
        return count_replace_all_in_file(
            path,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
            hash_for_entry=hash_for_entry,
        )

    def apply_replace_all_in_file(
        self,
        path: Path,
        *,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
        callbacks: ReplaceAllFileApplyCallbacks,
        hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
    ) -> ReplaceAllFileApplyResult:
        return apply_replace_all_in_file(
            path,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
            hash_for_entry=hash_for_entry,
        )

    def count_replace_all_in_rows(
        self,
        *,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
        callbacks: ReplaceAllRowsCallbacks,
    ) -> int:
        return count_replace_all_in_rows(
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
        )

    def apply_replace_all_in_rows(
        self,
        *,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
        callbacks: ReplaceAllRowsCallbacks,
    ) -> ReplaceAllRowsApplyResult:
        return apply_replace_all_in_rows(
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
        )

    def search_result_label(self, *, match: Match, root: Path) -> str:
        return search_result_label(match=match, root=root)

    def build_search_panel_plan(
        self,
        *,
        files: list[Path],
        root: Path,
        result_limit: int,
        iter_matches_for_file: Callable[[Path], Iterable[Match]],
    ) -> SearchPanelPlan:
        return build_search_panel_plan(
            files=files,
            root=root,
            result_limit=result_limit,
            iter_matches_for_file=iter_matches_for_file,
        )

    def build_search_run_plan(
        self,
        *,
        query_text: str,
        column: int,
        use_regex: bool,
        files: list[Path],
        current_file: Path | None,
        current_row: int | None,
        direction: int,
    ) -> SearchRunPlan:
        return build_search_run_plan(
            query_text=query_text,
            column=column,
            use_regex=use_regex,
            files=files,
            current_file=current_file,
            current_row=current_row,
            direction=direction,
        )

    def build_rows_cache_lookup_plan(
        self,
        *,
        path: Path,
        include_source: bool,
        include_value: bool,
        file_mtime_ns: int,
        cache_mtime_ns: int,
        source_mtime_ns: int,
        cached_stamp: SearchRowsCacheStamp | None,
    ) -> SearchRowsCacheLookupPlan:
        return build_rows_cache_lookup_plan(
            path=path,
            include_source=include_source,
            include_value=include_value,
            file_mtime_ns=file_mtime_ns,
            cache_mtime_ns=cache_mtime_ns,
            source_mtime_ns=source_mtime_ns,
            cached_stamp=cached_stamp,
        )

    def collect_rows_cache_stamp(
        self,
        *,
        path: Path,
        include_source: bool,
        include_value: bool,
        callbacks: SearchRowsCacheStampCallbacks,
    ) -> SearchRowsCacheStamp | None:
        return collect_rows_cache_stamp(
            path=path,
            include_source=include_source,
            include_value=include_value,
            callbacks=callbacks,
        )

    def build_rows_cache_store_plan(
        self,
        *,
        rows_materialized: bool,
        entry_count: int,
        cache_row_limit: int,
    ) -> SearchRowsCacheStorePlan:
        return build_rows_cache_store_plan(
            rows_materialized=rows_materialized,
            entry_count=entry_count,
            cache_row_limit=cache_row_limit,
        )

    def build_rows_source_plan(
        self,
        *,
        locale_known: bool,
        is_current_file: bool,
        has_current_model: bool,
    ) -> SearchRowsSourcePlan:
        return build_rows_source_plan(
            locale_known=locale_known,
            is_current_file=is_current_file,
            has_current_model=has_current_model,
        )

    def load_search_rows_from_file(
        self,
        *,
        path: Path,
        encoding: str,
        use_lazy_parser: bool,
        include_source: bool,
        include_value: bool,
        cache_row_limit: int,
        callbacks: SearchRowsFileCallbacks,
        hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
    ) -> SearchRowsBuildResult | None:
        return load_search_rows_from_file(
            path=path,
            encoding=encoding,
            use_lazy_parser=use_lazy_parser,
            include_source=include_source,
            include_value=include_value,
            cache_row_limit=cache_row_limit,
            callbacks=callbacks,
            hash_for_entry=hash_for_entry,
        )

    def build_search_rows(
        self,
        *,
        path: Path,
        entries: Iterable[Entry],
        entry_count: int,
        include_source: bool,
        include_value: bool,
        source_by_row: Sequence[str] | None,
        source_for_key: Callable[[str], str],
        cache_map: Mapping[int, CacheEntry],
        cache_row_limit: int,
        hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
    ) -> SearchRowsBuildResult:
        return build_search_rows(
            path=path,
            entries=entries,
            entry_count=entry_count,
            include_source=include_source,
            include_value=include_value,
            source_by_row=source_by_row,
            source_for_key=source_for_key,
            cache_map=cache_map,
            cache_row_limit=cache_row_limit,
            hash_for_entry=hash_for_entry,
        )

    def build_match_open_plan(
        self,
        *,
        has_match: bool,
        match_file: Path | None,
        current_file: Path | None,
    ) -> SearchMatchOpenPlan:
        return build_match_open_plan(
            has_match=has_match,
            match_file=match_file,
            current_file=current_file,
        )

    def build_match_apply_plan(
        self,
        *,
        has_match: bool,
        match_file: Path | None,
        current_file: Path | None,
        has_current_model: bool,
        match_row: int,
        row_count: int,
        column: int,
    ) -> SearchMatchApplyPlan:
        return build_match_apply_plan(
            has_match=has_match,
            match_file=match_file,
            current_file=current_file,
            has_current_model=has_current_model,
            match_row=match_row,
            row_count=row_count,
            column=column,
        )


def scope_files(
    *,
    scope: str,
    current_file: Path | None,
    current_locale: str | None,
    selected_locales: Iterable[str],
    files_for_locale: Callable[[str], list[Path]],
) -> list[Path]:
    if current_file is None:
        return []
    if scope == "FILE":
        return [current_file]
    if scope == "LOCALE":
        if not current_locale:
            return []
        return list(files_for_locale(current_locale))
    files: list[Path] = []
    for locale in selected_locales:
        files.extend(files_for_locale(locale))
    return files


def search_result_label(*, match: Match, root: Path) -> str:
    try:
        rel = str(match.file.relative_to(root))
    except ValueError:
        rel = str(match.file)
    base = f"{rel}:{match.row + 1}"
    preview = str(getattr(match, "preview", "")).strip()
    if not preview:
        return base
    return f"{base} · {preview}"


def build_search_panel_plan(
    *,
    files: list[Path],
    root: Path,
    result_limit: int,
    iter_matches_for_file: Callable[[Path], Iterable[Match]],
) -> SearchPanelPlan:
    limit = max(1, int(result_limit))
    items: list[SearchPanelItem] = []
    truncated = False
    for path in files:
        for match in iter_matches_for_file(path):
            items.append(
                SearchPanelItem(
                    file=match.file,
                    row=match.row,
                    label=search_result_label(match=match, root=root),
                )
            )
            if len(items) >= limit:
                truncated = True
                break
        if truncated:
            break
    if not items:
        return SearchPanelPlan(
            status_message="No matches in current scope.",
            items=(),
            truncated=False,
        )
    if truncated:
        return SearchPanelPlan(
            status_message=f"Showing first {len(items)} matches (limit {limit}).",
            items=tuple(items),
            truncated=True,
        )
    return SearchPanelPlan(
        status_message=f"{len(items)} matches in current scope.",
        items=tuple(items),
        truncated=False,
    )


def build_search_run_plan(
    *,
    query_text: str,
    column: int,
    use_regex: bool,
    files: list[Path],
    current_file: Path | None,
    current_row: int | None,
    direction: int,
) -> SearchRunPlan:
    query = query_text.strip()
    if not query:
        return SearchRunPlan(
            run_search=False,
            query="",
            use_regex=use_regex,
            field=None,
            include_source=False,
            include_value=False,
            files=(),
            anchor_path=None,
            anchor_row=anchor_row(current_row, direction),
            status_message=None,
        )
    if not files:
        return SearchRunPlan(
            run_search=False,
            query=query,
            use_regex=use_regex,
            field=None,
            include_source=False,
            include_value=False,
            files=(),
            anchor_path=None,
            anchor_row=anchor_row(current_row, direction),
            status_message="No files in current search scope.",
        )
    field, include_source, include_value = search_spec_for_column(column)
    resolved_anchor_path = current_file if current_file is not None else files[0]
    return SearchRunPlan(
        run_search=True,
        query=query,
        use_regex=use_regex,
        field=field,
        include_source=include_source,
        include_value=include_value,
        files=tuple(files),
        anchor_path=resolved_anchor_path,
        anchor_row=anchor_row(current_row, direction),
        status_message=None,
    )


def build_rows_cache_lookup_plan(
    *,
    path: Path,
    include_source: bool,
    include_value: bool,
    file_mtime_ns: int,
    cache_mtime_ns: int,
    source_mtime_ns: int,
    cached_stamp: SearchRowsCacheStamp | None,
) -> SearchRowsCacheLookupPlan:
    key = SearchRowsCacheKey(
        path=path,
        include_source=include_source,
        include_value=include_value,
    )
    stamp = SearchRowsCacheStamp(
        file_mtime_ns=file_mtime_ns,
        cache_mtime_ns=cache_mtime_ns,
        source_mtime_ns=source_mtime_ns,
    )
    return SearchRowsCacheLookupPlan(
        key=key,
        stamp=stamp,
        use_cached_rows=(cached_stamp == stamp),
    )


def collect_rows_cache_stamp(
    *,
    path: Path,
    include_source: bool,
    include_value: bool,
    callbacks: SearchRowsCacheStampCallbacks,
) -> SearchRowsCacheStamp | None:
    file_mtime_ns = callbacks.file_mtime_ns(path)
    if file_mtime_ns is None:
        return None
    cache_mtime_ns = callbacks.cache_mtime_ns(path) if include_value else 0
    source_mtime_ns = callbacks.source_mtime_ns(path) if include_source else 0
    return SearchRowsCacheStamp(
        file_mtime_ns=file_mtime_ns,
        cache_mtime_ns=cache_mtime_ns,
        source_mtime_ns=source_mtime_ns,
    )


def build_rows_cache_store_plan(
    *,
    rows_materialized: bool,
    entry_count: int,
    cache_row_limit: int,
) -> SearchRowsCacheStorePlan:
    return SearchRowsCacheStorePlan(
        should_store_rows=rows_materialized and entry_count <= cache_row_limit
    )


def build_rows_source_plan(
    *,
    locale_known: bool,
    is_current_file: bool,
    has_current_model: bool,
) -> SearchRowsSourcePlan:
    if not locale_known:
        return SearchRowsSourcePlan(
            has_rows=False,
            use_active_model_rows=False,
        )
    return SearchRowsSourcePlan(
        has_rows=True,
        use_active_model_rows=is_current_file and has_current_model,
    )


def load_search_rows_from_file(
    *,
    path: Path,
    encoding: str,
    use_lazy_parser: bool,
    include_source: bool,
    include_value: bool,
    cache_row_limit: int,
    callbacks: SearchRowsFileCallbacks,
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> SearchRowsBuildResult | None:
    try:
        parsed = (
            callbacks.parse_lazy(path, encoding)
            if use_lazy_parser
            else callbacks.parse_eager(path, encoding)
        )
    except Exception:
        return None
    if include_source:
        source_by_row, source_for_key = callbacks.load_source_lookup(parsed)
    else:
        source_by_row = None
        source_for_key = _empty_source_lookup
    cache_map: Mapping[int, CacheEntry] = (
        callbacks.read_cache(path) if include_value else {}
    )
    entry_count = len(parsed.entries)
    return build_search_rows(
        path=path,
        entries=parsed.entries,
        entry_count=entry_count,
        include_source=include_source,
        include_value=include_value,
        source_by_row=source_by_row,
        source_for_key=source_for_key,
        cache_map=cache_map,
        cache_row_limit=cache_row_limit,
        hash_for_entry=hash_for_entry,
    )


def build_search_rows(
    *,
    path: Path,
    entries: Iterable[Entry],
    entry_count: int,
    include_source: bool,
    include_value: bool,
    source_by_row: Sequence[str] | None,
    source_for_key: Callable[[str], str],
    cache_map: Mapping[int, CacheEntry],
    cache_row_limit: int,
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> SearchRowsBuildResult:
    use_cache = include_value and bool(cache_map)

    def _iter_rows() -> Iterable[SearchRow]:
        for idx, entry in enumerate(entries):
            key = entry.key
            value = ""
            if include_value:
                if use_cache:
                    key_hash = hash_for_entry(entry, cache_map)
                    rec = cache_map.get(key_hash)
                    value = rec.value if rec and rec.value is not None else entry.value
                else:
                    value = entry.value
            source = ""
            if include_source:
                if source_by_row is not None and idx < len(source_by_row):
                    source = source_by_row[idx]
                else:
                    source = source_for_key(key)
            yield SearchRow(
                file=path,
                row=idx,
                key=key,
                source=source,
                value="" if value is None else str(value),
            )

    if entry_count <= cache_row_limit:
        rows: Iterable[SearchRow] = list(_iter_rows())
    else:
        rows = _iter_rows()
    return SearchRowsBuildResult(rows=rows, entry_count=entry_count)


def _empty_source_lookup(_key: str) -> str:
    return ""


def build_match_open_plan(
    *,
    has_match: bool,
    match_file: Path | None,
    current_file: Path | None,
) -> SearchMatchOpenPlan:
    if not has_match or match_file is None:
        return SearchMatchOpenPlan(open_target_file=False, target_file=None)
    if current_file is None or match_file != current_file:
        return SearchMatchOpenPlan(open_target_file=True, target_file=match_file)
    return SearchMatchOpenPlan(open_target_file=False, target_file=match_file)


def build_match_apply_plan(
    *,
    has_match: bool,
    match_file: Path | None,
    current_file: Path | None,
    has_current_model: bool,
    match_row: int,
    row_count: int,
    column: int,
) -> SearchMatchApplyPlan:
    can_select = bool(
        has_match
        and has_current_model
        and match_file is not None
        and current_file is not None
        and match_file == current_file
        and 0 <= match_row < row_count
    )
    return SearchMatchApplyPlan(
        select_in_table=can_select,
        target_row=match_row,
        target_column=column,
    )


def build_replace_all_run_plan(
    *,
    scope: str,
    current_locale: str | None,
    selected_locale_count: int,
    files: list[Path],
    current_file: Path | None,
    display_name: Callable[[Path], str],
    count_in_current: Callable[[], int | None],
    count_in_file: Callable[[Path], int | None],
) -> ReplaceAllRunPlan | None:
    if scope == "FILE" or len(files) <= 1:
        return ReplaceAllRunPlan(
            run_replace=True,
            show_confirmation=False,
            scope_label=scope_label(
                scope=scope,
                current_locale=current_locale,
                selected_locale_count=selected_locale_count,
            ),
            counts=(),
        )
    planned = build_replace_all_plan(
        files=files,
        current_file=current_file,
        display_name=display_name,
        count_in_current=count_in_current,
        count_in_file=count_in_file,
    )
    if planned is None:
        return None
    if planned.total <= 0:
        return ReplaceAllRunPlan(
            run_replace=False,
            show_confirmation=False,
            scope_label=scope_label(
                scope=scope,
                current_locale=current_locale,
                selected_locale_count=selected_locale_count,
            ),
            counts=(),
        )
    return ReplaceAllRunPlan(
        run_replace=True,
        show_confirmation=True,
        scope_label=scope_label(
            scope=scope,
            current_locale=current_locale,
            selected_locale_count=selected_locale_count,
        ),
        counts=tuple(planned.counts),
    )


def build_replace_request(
    *,
    query: str,
    replacement: str,
    use_regex: bool,
    case_sensitive: bool,
) -> ReplaceRequest | None:
    if not query:
        return None
    flags = re.MULTILINE
    if not case_sensitive:
        flags |= re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error as exc:
        raise ReplaceRequestError(str(exc)) from exc
    matches_empty = bool(pattern.match(""))
    has_group_ref = bool(
        use_regex and re.search(r"\$(\d+)|\\g<\\d+>|\\[1-9]", replacement)
    )
    return ReplaceRequest(
        pattern=pattern,
        replacement=replacement,
        use_regex=use_regex,
        matches_empty=matches_empty,
        has_group_ref=has_group_ref,
    )


def apply_replace_in_row(
    *,
    row: int,
    request: ReplaceRequest,
    callbacks: ReplaceCurrentRowCallbacks,
) -> bool:
    text = callbacks.read_text(row)
    raw_text = "" if text is None else str(text)
    changed, new_text = replace_text(
        raw_text,
        pattern=request.pattern,
        replacement=request.replacement,
        use_regex=request.use_regex,
        matches_empty=request.matches_empty,
        has_group_ref=request.has_group_ref,
        mode="single",
    )
    if changed:
        callbacks.write_text(row, new_text)
    return changed


def prioritize_current_file(files: list[Path], current_file: Path | None) -> list[Path]:
    if current_file is None or current_file not in files:
        return list(files)
    return [current_file, *[path for path in files if path != current_file]]


def scope_label(
    *,
    scope: str,
    current_locale: str | None,
    selected_locale_count: int,
) -> str:
    if scope == "LOCALE":
        return f"Locale {current_locale}" if current_locale else "Locale"
    if scope == "POOL":
        return f"Pool ({selected_locale_count})"
    return "File"


def search_spec_for_column(column: int) -> tuple[SearchField, bool, bool]:
    if column == 0:
        return SearchField.KEY, False, False
    if column == 1:
        return SearchField.SOURCE, True, False
    return SearchField.TRANSLATION, False, True


def anchor_row(current_row: int | None, direction: int) -> int:
    if current_row is not None:
        return current_row
    return -1 if direction > 0 else sys.maxsize


def fallback_row(direction: int) -> int:
    return -1 if direction > 0 else sys.maxsize


def find_match_in_rows(
    rows: Iterable[SearchRow],
    query: str,
    field: SearchField,
    use_regex: bool,
    *,
    start_row: int,
    direction: int,
    case_sensitive: bool = False,
) -> Match | None:
    if direction >= 0:
        for match in iter_matches(
            rows,
            query,
            field,
            use_regex,
            case_sensitive=case_sensitive,
        ):
            if match.row > start_row:
                return match
        return None
    last_match: Match | None = None
    for match in iter_matches(
        rows,
        query,
        field,
        use_regex,
        case_sensitive=case_sensitive,
    ):
        if match.row >= start_row:
            break
        last_match = match
    return last_match


def replace_text(
    text: str,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
    mode: Literal["single", "all"],
) -> tuple[bool, str]:
    if mode == "single":
        return _replace_single(
            text,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
        )
    return _replace_all(
        text,
        pattern=pattern,
        replacement=replacement,
        use_regex=use_regex,
        matches_empty=matches_empty,
        has_group_ref=has_group_ref,
    )


def _replace_single(
    text: str,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
) -> tuple[bool, str]:
    if not pattern.search(text):
        return False, text
    if matches_empty and not has_group_ref:
        new_text = replacement
    elif use_regex:
        template = _regex_template(replacement)

        def _expander(match: re.Match[str]) -> str:
            return match.expand(template)

        new_text = pattern.sub(_expander, text, count=1)
    else:
        new_text = pattern.sub(lambda _m: replacement, text, count=1)
    return new_text != text, new_text


def _replace_all(
    text: str,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
) -> tuple[bool, str]:
    if not text:
        return False, text
    if matches_empty and not has_group_ref:
        new_text = replacement
    else:
        if not pattern.search(text):
            return False, text
        if use_regex:
            template = _regex_template(replacement)
            count = 1 if matches_empty else 0

            def _expander(match: re.Match[str]) -> str:
                return match.expand(template)

            new_text = pattern.sub(_expander, text, count=count)
        else:
            new_text = pattern.sub(lambda _m: replacement, text)
    return new_text != text, new_text


def _regex_template(replacement: str) -> str:
    return re.sub(r"\$(\d+)", r"\\g<\1>", replacement)


def search_across_files(
    *,
    files: list[Path],
    anchor_path: Path | None,
    anchor_row: int,
    direction: int,
    wrap: bool,
    find_in_file: Callable[[Path, int], Match | None],
) -> Match | None:
    if not files:
        return None
    if anchor_path not in files:
        anchor_index = 0
        anchor_path = files[0]
    else:
        anchor_index = files.index(anchor_path)

    if direction < 0:
        before = list(reversed(files[:anchor_index]))
        after = list(reversed(files[anchor_index + 1 :]))
        ordered_others = before + after if wrap else before
    else:
        after = list(files[anchor_index + 1 :])
        before = list(files[:anchor_index])
        ordered_others = after + before if wrap else after

    match = find_in_file(anchor_path, anchor_row)
    if match is not None:
        return match

    fallback = fallback_row(direction)
    for path in ordered_others:
        match = find_in_file(path, fallback)
        if match is not None:
            return match

    if not wrap:
        return None
    if direction > 0 and anchor_row < 0:
        return None
    if direction < 0 and anchor_row >= sys.maxsize:
        return None
    return find_in_file(anchor_path, fallback)


def build_replace_all_plan(
    *,
    files: list[Path],
    current_file: Path | None,
    display_name: Callable[[Path], str],
    count_in_current: Callable[[], int | None],
    count_in_file: Callable[[Path], int | None],
) -> ReplaceAllPlan | None:
    total = 0
    counts: list[tuple[str, int]] = []
    for path in files:
        if current_file and path == current_file:
            file_count = count_in_current()
        else:
            file_count = count_in_file(path)
        if file_count is None:
            return None
        total += file_count
        if file_count:
            counts.append((display_name(path), file_count))
    return ReplaceAllPlan(total=total, counts=counts)


def apply_replace_all(
    *,
    files: list[Path],
    current_file: Path | None,
    apply_in_current: Callable[[], bool],
    apply_in_file: Callable[[Path], bool],
) -> bool:
    if current_file and current_file in files and not apply_in_current():
        return False
    for path in files:
        if current_file and path == current_file:
            continue
        if not apply_in_file(path):
            return False
    return True


def count_replace_all_in_file(
    path: Path,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
    callbacks: ReplaceAllFileCountCallbacks,
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> int:
    parsed, cache_map = _load_replace_file(
        path, callbacks.parse_file, callbacks.read_cache
    )
    count = 0
    for entry in parsed.entries:
        _, value, _status = _resolve_entry_overlay(
            entry=entry,
            cache_map=cache_map,
            hash_for_entry=hash_for_entry,
        )
        text = "" if value is None else str(value)
        changed, _new_text = replace_text(
            text,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            mode="all",
        )
        if changed:
            count += 1
    return count


def apply_replace_all_in_file(
    path: Path,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
    callbacks: ReplaceAllFileApplyCallbacks,
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> ReplaceAllFileApplyResult:
    parsed, cache_map = _load_replace_file(
        path, callbacks.parse_file, callbacks.read_cache
    )
    changed_keys: set[str] = set()
    original_values: dict[str, str] = {}
    new_entries: list[Entry] = []
    for entry in parsed.entries:
        _, value, status = _resolve_entry_overlay(
            entry=entry,
            cache_map=cache_map,
            hash_for_entry=hash_for_entry,
        )
        text = "" if value is None else str(value)
        changed, new_value = replace_text(
            text,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            mode="all",
        )
        if changed:
            status = Status.TRANSLATED
            changed_keys.add(entry.key)
            original_values[entry.key] = text
        if new_value != entry.value or status != entry.status:
            entry = type(entry)(
                entry.key,
                new_value,
                status,
                entry.span,
                entry.segments,
                entry.gaps,
                entry.raw,
                getattr(entry, "key_hash", None),
            )
        new_entries.append(entry)
    callbacks.write_cache(path, new_entries, changed_keys, original_values)
    return ReplaceAllFileApplyResult(
        changed_keys=changed_keys,
        changed_any=bool(changed_keys),
    )


def count_replace_all_in_rows(
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
    callbacks: ReplaceAllRowsCallbacks,
) -> int:
    count = 0
    for row in range(callbacks.row_count()):
        text = callbacks.read_text(row)
        raw_text = "" if text is None else str(text)
        changed, _new_text = replace_text(
            raw_text,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            mode="all",
        )
        if changed:
            count += 1
    return count


def apply_replace_all_in_rows(
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
    callbacks: ReplaceAllRowsCallbacks,
) -> ReplaceAllRowsApplyResult:
    changed_rows = 0
    for row in range(callbacks.row_count()):
        text = callbacks.read_text(row)
        raw_text = "" if text is None else str(text)
        changed, new_text = replace_text(
            raw_text,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            mode="all",
        )
        if not changed:
            continue
        callbacks.write_text(row, new_text)
        changed_rows += 1
    return ReplaceAllRowsApplyResult(changed_rows=changed_rows)


def _load_replace_file(
    path: Path,
    parse_file: Callable[[Path], ParsedFile],
    read_cache: Callable[[Path], Mapping[int, CacheEntry]],
) -> tuple[ParsedFile, Mapping[int, CacheEntry]]:
    try:
        parsed = parse_file(path)
    except Exception as exc:  # pragma: no cover - adapter handles/reporting
        raise ReplaceAllFileParseError(path=path, original=exc) from exc
    return parsed, read_cache(path)


def _resolve_entry_overlay(
    *,
    entry: Entry,
    cache_map: Mapping[int, CacheEntry],
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> tuple[int, str | None, Status]:
    key_hash = hash_for_entry(entry, cache_map)
    cache = cache_map.get(key_hash)
    value = cache.value if cache and cache.value is not None else entry.value
    status = cache.status if cache else entry.status
    return key_hash, value, status
