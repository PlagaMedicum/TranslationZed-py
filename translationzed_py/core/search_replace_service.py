from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .search import Match, SearchField, SearchRow, iter_matches


@dataclass(frozen=True, slots=True)
class ReplaceAllPlan:
    total: int
    counts: list[tuple[str, int]]


@dataclass(frozen=True, slots=True)
class SearchReplaceService:
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
