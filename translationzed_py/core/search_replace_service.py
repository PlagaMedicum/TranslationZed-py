from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal

from .search import Match, SearchField, SearchRow, iter_matches


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
) -> Match | None:
    if direction >= 0:
        for match in iter_matches(rows, query, field, use_regex):
            if match.row > start_row:
                return match
        return None
    last_match: Match | None = None
    for match in iter_matches(rows, query, field, use_regex):
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
