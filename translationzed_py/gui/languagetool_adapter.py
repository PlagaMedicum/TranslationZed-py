"""LanguageTool adapter helpers for main-window orchestration."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

from translationzed_py.core.languagetool import (
    LT_LEVEL_DEFAULT,
    LT_LEVEL_PICKY,
    LT_STATUS_OFFLINE,
    LT_STATUS_OK,
    LanguageToolCheckResult,
    LanguageToolMatch,
)
from translationzed_py.core.languagetool import check_text as _lt_check_text
from translationzed_py.core.languagetool import (
    default_server_url as _default_lt_server_url,
)
from translationzed_py.core.languagetool import (
    draft_language_map as _draft_lt_language_map,
)
from translationzed_py.core.languagetool import (
    dump_language_map as _dump_lt_language_map,
)
from translationzed_py.core.languagetool import (
    load_language_map as _load_lt_language_map,
)
from translationzed_py.core.languagetool import (
    normalize_editor_mode as _normalize_lt_editor_mode,
)
from translationzed_py.core.languagetool import (
    normalize_timeout_ms as _normalize_lt_timeout_ms,
)
from translationzed_py.core.languagetool import (
    resolve_language_code as _resolve_lt_language_code,
)

LT_EDITOR_DEBOUNCE_MS = 320
LT_ISSUE_UNDERLINE_COLOR = QColor(210, 48, 48, 210)


@dataclass(frozen=True, slots=True)
class LTEditorIssueSpan:
    """Represent one inline editor issue span mapped to a LT match."""

    start: int
    end: int
    match: LanguageToolMatch


def apply_loaded_preferences(win: Any, loaded: Any) -> None:
    """Apply LT-specific loaded preference values onto main-window state."""
    win._qa_check_languagetool = bool(loaded.qa_check_languagetool)
    win._qa_languagetool_max_rows = int(loaded.qa_languagetool_max_rows)
    win._qa_languagetool_automark = bool(loaded.qa_languagetool_automark)
    win._lt_editor_mode = _normalize_lt_editor_mode(loaded.lt_editor_mode)
    win._lt_server_url = str(loaded.lt_server_url).strip() or _default_lt_server_url()
    win._lt_timeout_ms = _normalize_lt_timeout_ms(loaded.lt_timeout_ms)
    win._lt_picky_mode = bool(loaded.lt_picky_mode)
    win._lt_locale_map = _load_lt_language_map(loaded.lt_locale_map)


def seed_locale_map_defaults(win: Any) -> None:
    """Fill missing locale-map entries with deterministic draft defaults."""
    drafted = _draft_lt_language_map(win._locales.keys())
    for locale, language_code in drafted.items():
        win._lt_locale_map.setdefault(locale, language_code)


def populate_preferences_dialog_values(win: Any, prefs: dict[str, object]) -> None:
    """Populate LT-related values for Preferences dialog initialization."""
    prefs.update(
        {
            "lt_editor_mode": win._lt_editor_mode,
            "lt_server_url": win._lt_server_url,
            "lt_timeout_ms": win._lt_timeout_ms,
            "lt_picky_mode": win._lt_picky_mode,
            "lt_locale_map": _dump_lt_language_map(win._lt_locale_map) or "{}",
            "qa_check_languagetool": win._qa_check_languagetool,
            "qa_languagetool_max_rows": win._qa_languagetool_max_rows,
            "qa_languagetool_automark": win._qa_languagetool_automark,
        }
    )


def apply_runtime_preferences(win: Any, values: Mapping[str, object]) -> bool:
    """Apply LT-related runtime preferences and return whether QA LT toggles changed."""
    previous_qa_lt = (
        win._qa_check_languagetool,
        win._qa_languagetool_max_rows,
        win._qa_languagetool_automark,
    )
    win._qa_check_languagetool = bool(
        values.get("qa_check_languagetool", win._qa_check_languagetool)
    )
    try:
        parsed_qa_lt_max_rows = int(
            str(values.get("qa_languagetool_max_rows", win._qa_languagetool_max_rows))
        )
    except (TypeError, ValueError):
        parsed_qa_lt_max_rows = int(win._qa_languagetool_max_rows)
    win._qa_languagetool_max_rows = max(1, min(5000, parsed_qa_lt_max_rows))
    win._qa_languagetool_automark = (
        bool(values.get("qa_languagetool_automark", win._qa_languagetool_automark))
        and win._qa_check_languagetool
    )
    qa_lt_changed = previous_qa_lt != (
        win._qa_check_languagetool,
        win._qa_languagetool_max_rows,
        win._qa_languagetool_automark,
    )
    win._lt_editor_mode = _normalize_lt_editor_mode(
        values.get("lt_editor_mode", win._lt_editor_mode)
    )
    win._lt_server_url = (
        str(values.get("lt_server_url", win._lt_server_url)).strip()
        or _default_lt_server_url()
    )
    win._lt_timeout_ms = _normalize_lt_timeout_ms(
        values.get("lt_timeout_ms", win._lt_timeout_ms)
    )
    win._lt_picky_mode = bool(values.get("lt_picky_mode", win._lt_picky_mode))
    win._lt_locale_map = _load_lt_language_map(
        values.get("lt_locale_map", _dump_lt_language_map(win._lt_locale_map))
    )
    if not win._lt_locale_map:
        win._lt_locale_map = _draft_lt_language_map(win._locales.keys())
    win._schedule_languagetool_editor_check(immediate=True)
    return qa_lt_changed


def build_persist_kwargs(win: Any) -> dict[str, object]:
    """Build LT-specific persist kwargs consumed by preferences service."""
    return {
        "qa_check_languagetool": win._qa_check_languagetool,
        "qa_languagetool_max_rows": win._qa_languagetool_max_rows,
        "qa_languagetool_automark": win._qa_languagetool_automark,
        "lt_editor_mode": win._lt_editor_mode,
        "lt_server_url": win._lt_server_url,
        "lt_timeout_ms": win._lt_timeout_ms,
        "lt_picky_mode": win._lt_picky_mode,
        "lt_locale_map": _dump_lt_language_map(win._lt_locale_map) or "{}",
    }


def _lt_level_for_picky(enabled: bool) -> str:
    return LT_LEVEL_PICKY if enabled else LT_LEVEL_DEFAULT


def _lt_status_text(result: LanguageToolCheckResult | None) -> str:
    if result is None:
        return "LT: idle"
    if result.warning:
        return "LT: picky unsupported (default used)"
    if result.status == LT_STATUS_OFFLINE:
        return "LT: offline"
    if result.status != LT_STATUS_OK:
        return "LT: offline"
    if result.matches:
        return f"LT: issues:{len(result.matches)}"
    return "LT: ok"


def _build_issue_selections(
    *,
    editor: QPlainTextEdit,
    spans: tuple[LTEditorIssueSpan, ...],
) -> list[QTextEdit.ExtraSelection]:
    if not spans:
        return []
    fmt = QTextCharFormat()
    fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
    fmt.setUnderlineColor(LT_ISSUE_UNDERLINE_COLOR)
    selections: list[QTextEdit.ExtraSelection] = []
    for span in spans:
        cursor = QTextCursor(editor.document())
        cursor.setPosition(span.start)
        cursor.setPosition(span.end, QTextCursor.KeepAnchor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = fmt
        selections.append(selection)
    return selections


def _build_issue_spans(
    *,
    editor: QPlainTextEdit,
    result: LanguageToolCheckResult | None,
) -> tuple[LTEditorIssueSpan, ...]:
    if result is None or result.status != LT_STATUS_OK or not result.matches:
        return ()
    text_len = len(editor.document().toPlainText())
    spans: list[LTEditorIssueSpan] = []
    for match in result.matches:
        start = max(0, int(match.offset))
        end = min(text_len, start + max(0, int(match.length)))
        if end <= start:
            continue
        spans.append(LTEditorIssueSpan(start=start, end=end, match=match))
    return tuple(spans)


def _run_check_job(
    *,
    request_id: int,
    path: Path,
    row: int,
    text: str,
    server_url: str,
    language: str,
    level: str,
    timeout_ms: int,
) -> tuple[int, Path, int, str, LanguageToolCheckResult]:
    result = _lt_check_text(
        server_url=server_url,
        language=language,
        text=text,
        level=level,
        timeout_ms=timeout_ms,
    )
    return request_id, path, row, text, result


def effective_locale_map(win: Any) -> dict[str, str]:
    """Return current locale map with draft defaults filled."""
    mapping = dict(win._lt_locale_map)
    drafted = _draft_lt_language_map(win._locales.keys())
    for locale, language_code in drafted.items():
        mapping.setdefault(locale, language_code)
    return mapping


def resolve_language_for_path(win: Any, path: Path | None) -> str:
    """Resolve LT language code for the given file path."""
    locale = win._locale_for_path(path) if path is not None else None
    return _resolve_lt_language_code(locale or "EN", effective_locale_map(win))


def clear_editor_state(win: Any, *, status_text: str) -> None:
    """Clear current editor LT highlights and set compact status text."""
    win._lt_last_result = None
    win._lt_issue_spans = ()
    if hasattr(win, "_detail_translation") and win._detail_translation is not None:
        win._detail_translation.setExtraSelections([])
    if (
        hasattr(win, "_detail_lt_status_label")
        and win._detail_lt_status_label is not None
    ):
        win._detail_lt_status_label.setText(status_text)


def current_editor_payload(win: Any) -> tuple[Path, int, str] | None:
    """Return current editor check payload or None when LT checks are disabled."""
    if win._lt_editor_mode == "off":
        return None
    if not win._detail_panel.isVisible():
        return None
    if win._current_pf is None or win._current_model is None:
        return None
    if win._detail_pending_row is not None or win._detail_translation.isReadOnly():
        return None
    idx = win.table.currentIndex()
    if not idx.isValid():
        return None
    path = win._current_pf.path
    row = int(idx.row())
    text = win._detail_translation.toPlainText()
    return (path, row, text)


def schedule_editor_check(win: Any, *, immediate: bool = False) -> None:
    """Schedule a debounced inline LT check for current detail-editor text."""
    payload = current_editor_payload(win)
    if payload is None:
        if win._lt_editor_mode == "off":
            clear_editor_state(win, status_text="LT: off")
        else:
            clear_editor_state(win, status_text="LT: idle")
        win._lt_pending_payload = None
        return
    win._lt_request_seq += 1
    request_id = win._lt_request_seq
    path, row, text = payload
    win._lt_pending_payload = (request_id, path, row, text)
    if immediate:
        if win._lt_debounce_timer.isActive():
            win._lt_debounce_timer.stop()
        start_editor_check(win)
        return
    win._lt_debounce_timer.start(LT_EDITOR_DEBOUNCE_MS)


def start_editor_check(win: Any) -> None:
    """Start pending debounced inline LT request when worker is available."""
    pending = win._lt_pending_payload
    if pending is None:
        return
    if win._lt_scan_future is not None and not win._lt_scan_future.done():
        return
    request_id, path, row, text = pending
    current = current_editor_payload(win)
    if current is None:
        win._lt_pending_payload = None
        clear_editor_state(win, status_text="LT: idle")
        return
    if current != (path, row, text):
        win._lt_pending_payload = None
        schedule_editor_check(win, immediate=True)
        return
    if win._lt_scan_pool is None:
        win._lt_scan_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="tzp-lt-editor",
        )
    level = _lt_level_for_picky(win._lt_picky_mode)
    language = resolve_language_for_path(win, path)
    win._lt_pending_payload = None
    win._lt_inflight_payload = (request_id, path, row, text)
    win._detail_lt_status_label.setText("LT: checking")
    win._lt_scan_future = win._lt_scan_pool.submit(
        _run_check_job,
        request_id=request_id,
        path=path,
        row=row,
        text=text,
        server_url=win._lt_server_url,
        language=language,
        level=level,
        timeout_ms=win._lt_timeout_ms,
    )
    if not win._lt_scan_timer.isActive():
        win._lt_scan_timer.start()


def poll_editor_check(win: Any) -> None:
    """Poll async inline LT request and apply result when still current."""
    future = win._lt_scan_future
    if future is None:
        win._lt_scan_timer.stop()
        return
    if not future.done():
        return
    win._lt_scan_timer.stop()
    win._lt_scan_future = None
    win._lt_inflight_payload = None
    try:
        request_id, path, row, text, result = future.result()
    except Exception:
        clear_editor_state(win, status_text="LT: offline")
        if win._lt_pending_payload is not None:
            start_editor_check(win)
        return
    current = current_editor_payload(win)
    expected = (path, row, text)
    if current != expected:
        if win._lt_pending_payload is not None:
            start_editor_check(win)
        return
    if request_id < win._lt_request_seq and win._lt_pending_payload is not None:
        start_editor_check(win)
        return
    apply_editor_result(win, result)
    if win._lt_pending_payload is not None:
        start_editor_check(win)


def apply_editor_result(win: Any, result: LanguageToolCheckResult | None) -> None:
    """Apply LT check result to detail editor UI indicator and underlines."""
    win._lt_last_result = result
    win._detail_lt_status_label.setText(_lt_status_text(result))
    spans = _build_issue_spans(editor=win._detail_translation, result=result)
    win._lt_issue_spans = spans
    selections = _build_issue_selections(editor=win._detail_translation, spans=spans)
    win._detail_translation.setExtraSelections(selections)


def issue_at_position(win: Any, position: int) -> LTEditorIssueSpan | None:
    """Return LT issue span that contains the given editor cursor position."""
    pos = max(0, int(position))
    spans = tuple(getattr(win, "_lt_issue_spans", ()) or ())
    for span in spans:
        if span.start <= pos < span.end:
            return span
    return None


def apply_issue_replacement(
    win: Any,
    *,
    span: LTEditorIssueSpan,
    replacement: str,
) -> bool:
    """Replace issue span text with one suggested replacement."""
    editor = win._detail_translation
    text_len = len(editor.document().toPlainText())
    start = max(0, min(text_len, int(span.start)))
    end = max(start, min(text_len, int(span.end)))
    if end <= start:
        return False
    cursor = QTextCursor(editor.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    cursor.insertText(str(replacement))
    return True


def shutdown_workers(win: Any) -> None:
    """Cancel/stop LT async workers and clear pending request state."""
    if win._lt_scan_future is not None:
        with contextlib.suppress(Exception):
            win._lt_scan_future.cancel()
    win._lt_scan_future = None
    win._lt_pending_payload = None
    win._lt_inflight_payload = None
    if win._lt_scan_pool is not None:
        with contextlib.suppress(Exception):
            win._lt_scan_pool.shutdown(wait=False, cancel_futures=True)
    win._lt_scan_pool = None
