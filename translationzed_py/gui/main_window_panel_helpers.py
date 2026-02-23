"""Extracted MainWindow panel/selection/status helper methods."""

from __future__ import annotations

import contextlib
import html
import time
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from translationzed_py.core import parse_lazy
from translationzed_py.core.model import STATUS_ORDER, Status
from translationzed_py.core.qa_service import QAFinding as _QAFinding
from translationzed_py.core.search import Match as _SearchMatch
from translationzed_py.core.status_cache import read as _read_status_cache
from translationzed_py.core.tm_query import TMQueryKey, TMQueryPolicy
from translationzed_py.core.tm_store import TMMatch, TMStore
from translationzed_py.core.tm_workflow_service import (
    TMSelectionPlan as _TMSelectionPlan,
)

from . import languagetool_adapter as _lt_adapter
from .delegates import MAX_VISUAL_CHARS
from .perf_trace import PERF_TRACE
from .search_scope_ui import scope_icon_for as _scope_icon_for
from .tm_preview import apply_tm_preview_highlights as _apply_tm_preview_highlights
from .tm_preview import prepare_tm_preview_terms as _prepare_tm_preview_terms

_DONE_STATUSES = {Status.TRANSLATED, Status.PROOFREAD}


def _progress_percent(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((done * 100) / total))


def _progress_counts_from_model(win) -> tuple[int, int, int] | None:
    model = getattr(win, "_current_model", None)
    if model is None or not hasattr(model, "status_for_row"):
        return None
    try:
        total = int(model.rowCount())
    except Exception:
        return None
    translated = 0
    proofread = 0
    for row in range(total):
        status = model.status_for_row(row)
        if status in _DONE_STATUSES:
            translated += 1
        if status == Status.PROOFREAD:
            proofread += 1
    return total, translated, proofread


def _progress_counts_for_file(win, path: Path) -> tuple[int, int, int]:
    file_cache = getattr(win, "_progress_file_counts", None)
    if file_cache is None:
        file_cache = {}
        win._progress_file_counts = file_cache
    current = getattr(win, "_current_pf", None)
    if current is not None and current.path == path:
        model_counts = _progress_counts_from_model(win)
        if model_counts is not None:
            file_cache[path] = model_counts
            return model_counts
    cached = file_cache.get(path)
    if cached is not None:
        return cached
    locale = win._locale_for_path(path)
    encoding = (
        win._locales.get(locale, None).charset if locale in win._locales else None
    ) or "utf-8"
    try:
        parsed = parse_lazy(path, encoding=encoding)
    except Exception:
        counts = (0, 0, 0)
        file_cache[path] = counts
        return counts
    cache_map = _read_status_cache(win._root, path)
    total = 0
    translated = 0
    proofread = 0
    for entry in parsed.entries:
        total += 1
        status = entry.status
        cached_entry = cache_map.get(win._hash_for_cache(entry, cache_map))
        if cached_entry is not None:
            status = cached_entry.status
        if status in _DONE_STATUSES:
            translated += 1
        if status == Status.PROOFREAD:
            proofread += 1
    counts = (total, translated, proofread)
    file_cache[path] = counts
    return counts


def _progress_locale_counts(win, locale: str) -> tuple[int, int, int]:
    locale_cache = getattr(win, "_progress_locale_counts", None)
    if locale_cache is None:
        locale_cache = {}
        win._progress_locale_counts = locale_cache
    cached = locale_cache.get(locale)
    if cached is not None:
        return cached
    totals = [0, 0, 0]
    for path in win._files_for_locale(locale):
        file_counts = _progress_counts_for_file(win, path)
        totals[0] += file_counts[0]
        totals[1] += file_counts[1]
        totals[2] += file_counts[2]
    result = (totals[0], totals[1], totals[2])
    locale_cache[locale] = result
    return result


def _progress_segment(win) -> str | None:
    current = getattr(win, "_current_pf", None)
    if current is None:
        return None
    file_counts = _progress_counts_from_model(win)
    if file_counts is None:
        return None
    locale = win._locale_for_path(current.path)
    if not locale:
        return None
    file_total, file_translated, file_proofread = file_counts
    file_cache = getattr(win, "_progress_file_counts", None)
    if file_cache is None:
        file_cache = {}
        win._progress_file_counts = file_cache
    previous_file_counts = file_cache.get(current.path)
    file_cache[current.path] = file_counts
    if previous_file_counts != file_counts:
        locale_cache = getattr(win, "_progress_locale_counts", None)
        if locale_cache is not None:
            locale_cache.pop(locale, None)
    locale_total, locale_translated, locale_proofread = _progress_locale_counts(
        win, locale
    )
    return (
        "Progress "
        f"File T:{_progress_percent(file_translated, file_total)}% "
        f"P:{_progress_percent(file_proofread, file_total)}% "
        "| "
        f"Locale T:{_progress_percent(locale_translated, locale_total)}% "
        f"P:{_progress_percent(locale_proofread, locale_total)}%"
    )


def _set_qa_progress_visible(win, visible: bool) -> None:
    win._qa_scan_busy = bool(visible)
    win._qa_progress.setVisible(win._qa_scan_busy)
    win._qa_refresh_btn.setEnabled(not win._qa_scan_busy)


def _set_qa_findings(win, findings: Sequence[_QAFinding]) -> None:
    win._qa_findings = tuple(findings)
    if win._left_stack.currentIndex() == 3:
        win._refresh_qa_panel_results()


def _set_qa_scan_note(win, note: str) -> None:
    win._qa_scan_note = str(note).strip()
    if win._left_stack.currentIndex() == 3:
        win._refresh_qa_panel_results()


def _set_qa_panel_message(win, text: str) -> None:
    win._qa_scan_note = ""
    win._set_qa_list_placeholder(text)


def _refresh_qa_panel_results(win) -> None:
    if not hasattr(win, "_qa_results_list") or win._qa_results_list is None:
        return
    plan = win._qa_service.build_panel_plan(
        findings=win._qa_findings,
        root=win._root,
        result_limit=win._qa_panel_result_limit,
    )
    status_message = plan.status_message
    if win._qa_scan_note:
        status_message = f"{status_message} {win._qa_scan_note}"
    if not plan.items:
        win._set_qa_list_placeholder(status_message)
        return
    win._qa_results_list.clear()
    for row in plan.items:
        item = QListWidgetItem(row.label)
        finding = row.finding
        item.setData(Qt.UserRole, (str(finding.file), int(finding.row)))
        win._qa_results_list.addItem(item)


def _open_qa_result_item(win, item: QListWidgetItem) -> None:
    payload = item.data(Qt.UserRole)
    if not isinstance(payload, tuple) or len(payload) != 2:
        return
    raw_path, raw_row = payload
    try:
        match = _SearchMatch(Path(str(raw_path)), int(raw_row))
    except Exception:
        return
    win._select_match(match)


def _focus_qa_finding_item(win, finding: _QAFinding) -> None:
    if not hasattr(win, "_qa_results_list") or win._qa_results_list is None:
        return
    target = (str(finding.file), int(finding.row))
    for idx in range(win._qa_results_list.count()):
        item = win._qa_results_list.item(idx)
        payload = item.data(Qt.UserRole)
        if payload != target:
            continue
        win._qa_results_list.setCurrentItem(item)
        win._qa_results_list.scrollToItem(item)
        return


def _navigate_qa_finding(win, direction: int) -> None:
    if not win._qa_findings:
        win.statusBar().showMessage("Run QA first to navigate findings.", 3000)
        return
    current = win.table.currentIndex()
    current_row = current.row() if current.isValid() else None
    current_path = win._current_pf.path if win._current_pf is not None else None
    plan = win._qa_service.build_navigation_plan(
        findings=win._qa_findings,
        current_path=current_path,
        current_row=current_row,
        direction=direction,
        root=win._root,
    )
    if plan.finding is None:
        win.statusBar().showMessage(plan.status_message, 3000)
        return
    match = _SearchMatch(plan.finding.file, plan.finding.row)
    if not win._select_match(match):
        win.statusBar().showMessage("Unable to navigate to QA finding.", 3000)
        return
    if win._left_stack.currentIndex() == 3:
        win._focus_qa_finding_item(plan.finding)
    win.statusBar().showMessage(plan.status_message, 4000)


def _qa_next_finding(win) -> None:
    win._navigate_qa_finding(direction=1)


def _qa_prev_finding(win) -> None:
    win._navigate_qa_finding(direction=-1)


def _next_priority_status_row(win) -> int | None:
    if not win._current_model:
        return None
    total = win._current_model.rowCount()
    if total <= 0:
        return None
    current = win.table.currentIndex()
    current_row = current.row() if current.isValid() else -1
    for status in STATUS_ORDER:
        candidates = [
            row
            for row in range(total)
            if win._current_model.status_for_row(row) == status
        ]
        if not candidates:
            continue
        for row in candidates:
            if row > current_row:
                return row
        return candidates[0]
    return None


def _go_to_next_priority_status(win) -> None:
    if not win._current_model:
        return
    target_row = win._next_priority_status_row()
    if target_row is None:
        if hasattr(win, "_show_info_box"):
            win._show_info_box(
                "Status triage complete",
                "Proofreading is complete for this file.",
            )
        else:
            QMessageBox.information(
                win,
                "Status triage complete",
                "Proofreading is complete for this file.",
            )
        return
    current = win.table.currentIndex()
    target_column = current.column() if current.isValid() else 2
    target_column = max(0, min(target_column, win._current_model.columnCount() - 1))
    target = win._current_model.index(target_row, target_column)
    win.table.selectionModel().setCurrentIndex(
        target,
        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
    )
    win.table.scrollTo(target, QAbstractItemView.PositionAtCenter)


def _run_search(win) -> None:
    win._search_from_anchor(direction=1, anchor_row=-1)


def _search_next(win) -> None:
    if win._search_timer.isActive():
        win._search_timer.stop()
    win._search_from_anchor(direction=1)


def _search_prev(win) -> None:
    if win._search_timer.isActive():
        win._search_timer.stop()
    win._search_from_anchor(direction=-1)


def _copy_selection(win) -> None:
    sel = win.table.selectionModel()
    if sel is None or not sel.hasSelection():
        return
    full_rows = [
        idx.row()
        for idx in sel.selectedRows()
        if sel.isRowSelected(idx.row(), idx.parent())
    ]
    if full_rows:
        lines: list[str] = []
        for row in sorted(set(full_rows)):
            cols = [
                (
                    win._current_model.index(row, col).data(
                        Qt.EditRole if col in (1, 2) else Qt.DisplayRole
                    )
                    if win._current_model
                    else ""
                )
                for col in range(4)
            ]
            line = "\t".join("" if c is None else str(c) for c in cols)
            lines.append(line)
        QGuiApplication.clipboard().setText("\n".join(lines))
        return
    idx = win.table.currentIndex()
    if not idx.isValid():
        return
    text = idx.data(Qt.EditRole) if idx.column() in (1, 2) else idx.data(Qt.DisplayRole)
    QGuiApplication.clipboard().setText("" if text is None else str(text))


def _cut_selection(win) -> None:
    idx = win.table.currentIndex()
    if not idx.isValid() or idx.column() != 2:
        return
    win._copy_selection()
    if win._current_model:
        win._current_model.setData(idx, "", Qt.EditRole)


def _paste_selection(win) -> None:
    idx = win.table.currentIndex()
    if not idx.isValid() or idx.column() != 2:
        return
    if not win._current_model:
        return
    text = QGuiApplication.clipboard().text()
    rows = win._selected_rows()
    if len(rows) <= 1:
        win._current_model.setData(idx, text, Qt.EditRole)
        return
    stack = win._current_model.undo_stack
    stack.beginMacro("Set translation for selection")
    try:
        for row in rows:
            model_index = win._current_model.index(row, 2)
            win._current_model.setData(model_index, text, Qt.EditRole)
    finally:
        stack.endMacro()


def _toggle_wrap_text(win, checked: bool) -> None:
    win._wrap_text_user = bool(checked)
    win._apply_wrap_mode()
    win._persist_preferences()


def _apply_wrap_mode(win) -> None:
    effective = win._wrap_text_user
    if win._wrap_text != effective:
        win._wrap_text = effective
        win.table.setWordWrap(win._wrap_text)
        win._apply_row_height_mode()
        win._clear_row_height_cache()
        if win._wrap_text:
            win._schedule_row_resize()
    if getattr(win, "act_wrap", None):
        win.act_wrap.blockSignals(True)
        try:
            win.act_wrap.setChecked(win._wrap_text)
        finally:
            win.act_wrap.blockSignals(False)
        if win._large_file_mode:
            win.act_wrap.setToolTip("Wrap enabled; large-file mode active")
        else:
            win.act_wrap.setToolTip("Wrap long strings in table")


def _update_large_file_mode(win) -> None:
    active = win._is_large_file() if win._large_text_optimizations else False
    if active != win._large_file_mode:
        win._large_file_mode = active
        win._apply_wrap_mode()
        win._apply_text_visual_options()


def _apply_row_height_mode(win) -> None:
    header = win.table.verticalHeader()
    header.setDefaultSectionSize(win._default_row_height)
    if hasattr(win.table, "setUniformRowHeights"):
        # Available on some Qt/PySide builds; avoid AttributeError on others.
        win.table.setUniformRowHeights(not win._wrap_text)
    if win._wrap_text:
        header.setSectionResizeMode(QHeaderView.Interactive)
    else:
        # No-wrap uses fixed row height to avoid sizeHint churn.
        header.setSectionResizeMode(QHeaderView.Fixed)


def _text_visual_options_table(win) -> tuple[bool, bool, bool]:
    show_ws = win._visual_whitespace
    highlight = win._visual_highlight
    return show_ws, highlight, win._large_text_optimizations


def _text_visual_options_detail(win) -> tuple[bool, bool, bool]:
    return (
        win._visual_whitespace,
        win._visual_highlight,
        win._large_text_optimizations,
    )


def _apply_text_visual_options(win) -> None:
    win._apply_detail_whitespace_options()
    for highlighter in (
        win._detail_source_highlighter,
        win._detail_translation_highlighter,
    ):
        if highlighter:
            highlighter.rehighlight()
    if win.table.viewport():
        win.table.viewport().update()


def _apply_detail_whitespace_options(win) -> None:
    show_ws, _highlight, optimize = win._text_visual_options_detail()
    for editor in (win._detail_source, win._detail_translation):
        if not editor:
            continue
        if optimize and editor.document().characterCount() >= MAX_VISUAL_CHARS:
            apply_ws = False
        else:
            apply_ws = show_ws
        option = editor.document().defaultTextOption()
        flags = option.flags()
        if apply_ws:
            flags |= (
                QTextOption.ShowTabsAndSpaces
                | QTextOption.ShowLineAndParagraphSeparators
            )
        else:
            flags &= ~(
                QTextOption.ShowTabsAndSpaces
                | QTextOption.ShowLineAndParagraphSeparators
            )
        option.setFlags(flags)
        editor.document().setDefaultTextOption(option)


def _toggle_prompt_on_exit(win, checked: bool) -> None:
    win._prompt_write_on_exit = bool(checked)
    win._persist_preferences()


def _persist_preferences(win) -> None:
    geometry = ""
    try:
        geometry = bytes(win.saveGeometry().toBase64()).decode("ascii")
    except Exception:
        geometry = ""
    win._preferences_service.persist_main_window_preferences(
        prompt_write_on_exit=win._prompt_write_on_exit,
        wrap_text=win._wrap_text_user,
        large_text_optimizations=win._large_text_optimizations,
        qa_check_trailing=win._qa_check_trailing,
        qa_check_newlines=win._qa_check_newlines,
        qa_check_escapes=win._qa_check_escapes,
        qa_check_same_as_source=win._qa_check_same_as_source,
        qa_auto_refresh=win._qa_auto_refresh,
        qa_auto_mark_for_review=win._qa_auto_mark_for_review,
        qa_auto_mark_translated_for_review=(win._qa_auto_mark_translated_for_review),
        qa_auto_mark_proofread_for_review=(win._qa_auto_mark_proofread_for_review),
        last_root=str(win._root),
        last_locales=list(win._selected_locales),
        window_geometry=geometry,
        default_root=win._default_root,
        tm_import_dir=win._tm_import_dir,
        search_scope=win._search_scope,
        replace_scope=win._replace_scope,
        extras=dict(win._prefs_extras),
        **_lt_adapter.build_persist_kwargs(win),
    )


def _on_model_data_changed(win, top_left, bottom_right, roles=None) -> None:
    if not win._current_model:
        return
    current = win.table.currentIndex()
    if not current.isValid():
        win._update_status_combo_from_selection()
        return
    row = current.row()
    if top_left.row() <= row <= bottom_right.row() and (
        roles is None or Qt.EditRole in roles or Qt.DisplayRole in roles
    ):
        win._update_status_combo_from_selection()
        if win._wrap_text:
            win._clear_row_height_cache(range(top_left.row(), bottom_right.row() + 1))
            win._schedule_row_resize()
        if win._detail_panel.isVisible() and not win._detail_translation.hasFocus():
            win._sync_detail_editors()
        if win._qa_auto_refresh:
            win._schedule_qa_refresh()
        else:
            win._set_qa_findings(())
            if win._left_stack.currentIndex() == 3:
                win._set_qa_panel_message("Edited. Click Run QA to refresh findings.")


def _on_selection_changed(win, current, previous) -> None:
    perf_trace = PERF_TRACE
    perf_start = perf_trace.start("selection")
    try:
        if previous is not None and previous.isValid():
            win._commit_detail_translation(previous)
        win._update_status_combo_from_selection()
        if win._detail_panel.isVisible():
            win._sync_detail_editors()
        win._update_status_bar()
        win._schedule_tm_update()
    finally:
        perf_trace.stop("selection", perf_start, items=1, unit="events")


def _schedule_tm_update(win) -> None:
    if win._tm_apply_in_progress:
        return
    plan = win._tm_workflow.build_update_plan(
        has_store=win._tm_store is not None,
        panel_index=win._left_stack.currentIndex(),
        timer_active=win._tm_update_timer.isActive(),
        tm_panel_index=1,
    )
    if not plan.run_update:
        return
    if plan.stop_timer:
        win._tm_update_timer.stop()
    if plan.start_timer:
        win._tm_update_timer.start()


def _set_tm_progress_visible(win, visible: bool) -> None:
    win._tm_progress.setVisible(bool(visible))


def _set_tm_list_placeholder(win, text: str) -> None:
    """Show a non-selectable placeholder row inside the TM results list."""
    win._tm_list.clear()
    message = str(text).strip() or "Select row to see Translation Memory suggestions."
    item = QListWidgetItem(message)
    item.setFlags(Qt.ItemIsEnabled)
    item.setData(int(Qt.UserRole) + 7, True)
    win._tm_list.insertItem(0, item)


def _set_search_list_placeholder(win, text: str) -> None:
    """Show a non-selectable placeholder row inside the Search results list."""
    if not hasattr(win, "_search_results_list") or win._search_results_list is None:
        return
    win._search_results_list.clear()
    message = str(text).strip() or "Press Enter in the search box to populate results."
    item = QListWidgetItem(message)
    item.setFlags(Qt.ItemIsEnabled)
    item.setData(int(Qt.UserRole) + 7, True)
    win._search_results_list.insertItem(0, item)


def _set_qa_list_placeholder(win, text: str) -> None:
    """Show a non-selectable placeholder row inside the QA results list."""
    if not hasattr(win, "_qa_results_list") or win._qa_results_list is None:
        return
    win._qa_results_list.clear()
    message = str(text).strip() or "Select a file to run QA checks."
    item = QListWidgetItem(message)
    item.setFlags(Qt.ItemIsEnabled)
    item.setData(int(Qt.UserRole) + 7, True)
    win._qa_results_list.insertItem(0, item)


def _update_tm_apply_state(win) -> None:
    items = win._tm_list.selectedItems()
    match = items[0].data(Qt.UserRole) if items else None
    plan = win._tm_workflow.build_selection_plan(
        match=match if isinstance(match, TMMatch) else None,
        lookup=win._current_tm_lookup(),
    )
    win._tm_apply_btn.setEnabled(plan.apply_enabled)
    win._set_tm_preview(plan)


def _set_tm_preview(win, plan: _TMSelectionPlan) -> None:
    if not plan.apply_enabled:
        win._tm_source_preview.clear()
        win._tm_target_preview.clear()
        win._tm_source_preview.setExtraSelections([])
        win._tm_target_preview.setExtraSelections([])
        return
    win._tm_source_preview.setPlainText(plan.source_preview)
    win._tm_target_preview.setPlainText(plan.target_preview)
    terms = _prepare_tm_preview_terms(plan.query_terms)
    with contextlib.suppress(Exception):
        _apply_tm_preview_highlights(win._tm_source_preview, terms)
        _apply_tm_preview_highlights(win._tm_target_preview, terms)


def _on_tm_item_double_clicked(win, _item: QListWidgetItem) -> None:
    # Defer apply to avoid mutating list/model during Qt double-click delivery.
    QTimer.singleShot(0, win._apply_tm_selection)


def _tm_query_policy(win) -> TMQueryPolicy:
    return win._tm_workflow.build_filter_plan(
        source_locale=win._tm_source_locale,
        min_score=win._tm_min_score,
        origin_project=win._tm_origin_project,
        origin_import=win._tm_origin_import,
    ).policy


def _tm_apply_filter_plan(win, plan) -> None:
    win._tm_min_score = plan.policy.min_score
    win._tm_origin_project = plan.policy.origin_project
    win._tm_origin_import = plan.policy.origin_import
    win._prefs_extras.update(plan.prefs_extras)
    if win._tm_score_spin.value() != win._tm_min_score:
        win._tm_score_spin.blockSignals(True)
        try:
            win._tm_score_spin.setValue(win._tm_min_score)
        finally:
            win._tm_score_spin.blockSignals(False)
    if win._tm_origin_project_cb.isChecked() != win._tm_origin_project:
        win._tm_origin_project_cb.blockSignals(True)
        try:
            win._tm_origin_project_cb.setChecked(win._tm_origin_project)
        finally:
            win._tm_origin_project_cb.blockSignals(False)
    if win._tm_origin_import_cb.isChecked() != win._tm_origin_import:
        win._tm_origin_import_cb.blockSignals(True)
        try:
            win._tm_origin_import_cb.setChecked(win._tm_origin_import)
        finally:
            win._tm_origin_import_cb.blockSignals(False)


def _on_tm_filters_changed(win) -> None:
    plan = win._tm_workflow.build_filter_plan(
        source_locale=win._tm_source_locale,
        min_score=int(win._tm_score_spin.value()),
        origin_project=bool(win._tm_origin_project_cb.isChecked()),
        origin_import=bool(win._tm_origin_import_cb.isChecked()),
    )
    win._tm_apply_filter_plan(plan)
    win._persist_preferences()
    win._update_tm_suggestions()


def _current_tm_lookup(win) -> tuple[str, str] | None:
    if not (win._current_model and win._current_pf):
        return None
    current = win.table.currentIndex()
    if not current.isValid():
        return None
    source_index = win._current_model.index(current.row(), 1)
    source_text = str(source_index.data(Qt.EditRole) or "")
    locale = win._locale_for_path(win._current_pf.path)
    return win._tm_workflow.build_lookup(
        source_text=source_text,
        target_locale=locale,
    )


def _apply_tm_selection(win) -> None:
    if win._tm_apply_in_progress:
        return
    if not (win._current_model and win._current_pf):
        return
    items = win._tm_list.selectedItems()
    if not items:
        return
    match = items[0].data(Qt.UserRole)
    plan = win._tm_workflow.build_apply_plan(
        match if isinstance(match, TMMatch) else None
    )
    if plan is None:
        return
    current = win.table.currentIndex()
    if not current.isValid():
        return
    win._tm_apply_in_progress = True
    try:
        value_index = win._current_model.index(current.row(), 2)
        win._current_model.setData(value_index, plan.target_text, Qt.EditRole)
        win._update_status_combo_from_selection()
        win._flush_tm_updates(paths=[win._current_pf.path])
        win._tm_workflow.clear_cache()
    finally:
        win._tm_apply_in_progress = False
    if win._left_stack.currentIndex() == 1:
        win._update_tm_suggestions()
    else:
        win._schedule_tm_update()


def _update_tm_suggestions(win) -> None:
    policy = win._tm_query_policy()
    lookup = win._current_tm_lookup()
    refresh = win._tm_workflow.build_refresh_plan(
        has_store=win._tm_store is not None,
        panel_index=win._left_stack.currentIndex(),
        lookup=lookup,
        policy=policy,
        has_current_file=win._current_pf is not None,
        tm_panel_index=1,
    )
    if not refresh.run_update:
        return
    assert win._tm_store is not None
    if refresh.flush_current_file and win._current_pf:
        win._flush_tm_updates(paths=[win._current_pf.path])
    assert refresh.query_plan is not None
    plan = refresh.query_plan
    if plan.mode == "cached" and plan.matches is not None:
        win._show_tm_matches(plan.matches)
        return
    win._set_tm_list_placeholder(plan.message)
    win._tm_apply_btn.setEnabled(False)
    win._set_tm_preview(win._tm_workflow.build_selection_plan(match=None, lookup=None))
    if plan.mode == "query" and plan.cache_key is not None:
        win._start_tm_query(plan.cache_key)


def _start_tm_query(win, cache_key: TMQueryKey) -> None:
    if not win._tm_store or win._tm_query_pool is None:
        return
    if (
        win._tm_query_key == cache_key
        and win._tm_query_future is not None
        and not win._tm_query_future.done()
    ):
        return
    win._tm_query_key = cache_key
    request = win._tm_workflow.build_query_request(cache_key)
    win._tm_query_future = win._tm_query_pool.submit(
        TMStore.query_path,
        win._tm_store.db_path,
        request.source_text,
        source_locale=request.source_locale,
        target_locale=request.target_locale,
        limit=request.limit,
        min_score=request.min_score,
        origins=request.origins,
    )
    win._set_tm_progress_visible(True)
    if not win._tm_query_timer.isActive():
        win._tm_query_timer.start()


def _poll_tm_query(win) -> None:
    future = win._tm_query_future
    cache_key = win._tm_query_key
    if future is None:
        win._tm_query_timer.stop()
        win._set_tm_progress_visible(win._tm_rebuild_future is not None)
        return
    if not future.done():
        return
    win._tm_query_timer.stop()
    win._tm_query_future = None
    win._tm_query_key = None
    win._set_tm_progress_visible(win._tm_rebuild_future is not None)
    if cache_key is None:
        return
    try:
        matches = future.result()
    except Exception:
        win._set_tm_list_placeholder("TM lookup failed.")
        win._tm_apply_btn.setEnabled(False)
        return
    lookup = win._current_tm_lookup()
    show_current = win._tm_workflow.accept_query_result(
        cache_key=cache_key,
        matches=matches,
        lookup=lookup,
        policy=win._tm_query_policy(),
    )
    if not show_current:
        return
    win._show_tm_matches(matches)


def _show_tm_matches(win, matches: list[TMMatch]) -> None:
    win._tm_list.clear()
    view = win._tm_workflow.build_suggestions_view(
        matches=matches,
        policy=win._tm_query_policy(),
        source_preview_limit=60,
        target_preview_limit=80,
    )
    if not view.items:
        win._set_tm_list_placeholder(view.message)
        win._tm_apply_btn.setEnabled(False)
        win._set_tm_preview(
            win._tm_workflow.build_selection_plan(match=None, lookup=None)
        )
        return
    for view_item in view.items:
        item = QListWidgetItem(view_item.label)
        item.setData(Qt.UserRole, view_item.match)
        item.setToolTip(view_item.tooltip_html)
        win._tm_list.addItem(item)
    if win._tm_list.count():
        win._tm_list.setCurrentRow(0)
    else:
        win._set_tm_list_placeholder(view.message)
        win._set_tm_preview(
            win._tm_workflow.build_selection_plan(match=None, lookup=None)
        )
        win._tm_apply_btn.setEnabled(False)


def _tooltip_html(win, text: str) -> str:
    escaped = html.escape(text)
    return f'<span style="white-space: pre-wrap;">{escaped}</span>'


def _update_status_combo_from_selection(win) -> None:
    if not win._current_model:
        win._set_status_combo(None)
        return
    rows = win._selected_rows()
    if not rows:
        win._set_status_combo(None)
        return
    statuses = {win._current_model.status_for_row(row) for row in rows}
    statuses.discard(None)
    if len(statuses) == 1:
        win._set_status_combo(statuses.pop())
    else:
        win._set_status_combo(None)


def _set_status_combo(win, status: Status | None) -> None:
    win._updating_status_combo = True
    try:
        if status is None:
            win.status_combo.setEnabled(bool(win._selected_rows()))
            win.status_combo.setCurrentIndex(-1)
            return
        win.status_combo.setEnabled(True)
        for i in range(win.status_combo.count()):
            if win.status_combo.itemData(i) == status:
                win.status_combo.setCurrentIndex(i)
                return
        win.status_combo.setCurrentIndex(-1)
    finally:
        win._updating_status_combo = False


def _status_combo_changed(win, _index: int) -> None:
    if win._updating_status_combo:
        return
    if not win._current_model:
        return
    status = win.status_combo.currentData()
    if status is None:
        return
    rows = win._selected_rows()
    if not rows:
        return
    if len(rows) == 1:
        model_index = win._current_model.index(rows[0], 3)
        win._current_model.setData(model_index, status, Qt.EditRole)
        return
    if not any(win._current_model.status_for_row(row) != status for row in rows):
        return
    stack = win._current_model.undo_stack
    stack.beginMacro("Set status for selection")
    try:
        for row in rows:
            model_index = win._current_model.index(row, 3)
            win._current_model.setData(model_index, status, Qt.EditRole)
    finally:
        stack.endMacro()


def _set_saved_status(win) -> None:
    win._last_saved_text = time.strftime("Saved %H:%M:%S")
    win._update_status_bar()


def _selected_rows(win) -> list[int]:
    sel = win.table.selectionModel()
    if sel is None:
        return []
    current = win.table.currentIndex()
    if current.isValid() and not sel.isSelected(current):
        return [current.row()]
    rows = {idx.row() for idx in sel.selectedRows()}
    if not rows:
        rows = {idx.row() for idx in sel.selectedIndexes()}
    return sorted(rows)


def _update_status_bar(win) -> None:
    parts: list[str] = []
    if win._last_saved_text:
        parts.append(win._last_saved_text)
    if win._search_progress_text:
        parts.append(win._search_progress_text)
    if win._current_model:
        idx = win.table.currentIndex()
        if idx.isValid():
            parts.append(f"Row {idx.row() + 1} / {win._current_model.rowCount()}")
    if win._current_pf:
        try:
            rel = win._current_pf.path.relative_to(win._root)
            parts.append(str(rel))
        except ValueError:
            parts.append(str(win._current_pf.path))
    progress = _progress_segment(win)
    if progress:
        parts.append(progress)
    if not parts:
        parts.append("Ready")
    win.statusBar().showMessage(" | ".join(parts))
    win._update_scope_indicators()


def _update_scope_indicators(win) -> None:
    if not win._search_scope_widget or not win._replace_scope_widget:
        return
    search_active = bool(win.search_edit.text().strip())
    replace_active = win.replace_toolbar.isVisible()
    win._set_scope_indicator(
        win._search_scope_widget,
        win._search_scope_icon,
        win._search_scope,
        search_active,
        "Search scope",
    )
    win._set_scope_indicator(
        win._replace_scope_widget,
        win._replace_scope_icon,
        win._replace_scope,
        replace_active,
        "Replace scope",
    )


def _set_scope_indicator(
    win,
    widget: QWidget,
    icon_label: QLabel,
    scope: str,
    active: bool,
    title: str,
) -> None:
    if not active:
        widget.setVisible(False)
        return
    icon = _scope_icon_for(win, scope)
    icon_label.setPixmap(icon.pixmap(14, 14))
    widget.setToolTip(f"{title}: {scope.title()}")
    widget.setVisible(True)


def _apply_status_to_rows(
    win,
    rows: Sequence[int],
    *,
    status: Status,
    label: str,
) -> None:
    if not win._current_model:
        return
    unique_rows = sorted({int(row) for row in rows if int(row) >= 0})
    if not unique_rows:
        return
    rows_to_change = [
        row for row in unique_rows if win._current_model.status_for_row(row) != status
    ]
    if not rows_to_change:
        return
    if len(rows_to_change) == 1:
        model_index = win._current_model.index(rows_to_change[0], 3)
        win._current_model.setData(model_index, status, Qt.EditRole)
        return
    stack = win._current_model.undo_stack
    stack.beginMacro(label)
    try:
        for row in rows_to_change:
            model_index = win._current_model.index(row, 3)
            win._current_model.setData(model_index, status, Qt.EditRole)
    finally:
        stack.endMacro()


def _apply_qa_auto_mark(win, findings: Sequence[_QAFinding]) -> None:
    if win._current_model is None:
        return
    rows = win._qa_service.auto_mark_rows(findings)
    allow_translated = bool(getattr(win, "_qa_auto_mark_translated_for_review", False))
    allow_proofread = bool(getattr(win, "_qa_auto_mark_proofread_for_review", False))
    rows = tuple(
        row
        for row in rows
        if (
            (status := win._current_model.status_for_row(row)) == Status.UNTOUCHED
            or (allow_translated and status == Status.TRANSLATED)
            or (allow_proofread and status == Status.PROOFREAD)
        )
    )
    win._apply_status_to_rows(
        rows,
        status=Status.FOR_REVIEW,
        label="QA auto-mark For review",
    )


def _apply_status_to_selection(win, status: Status, label: str) -> None:
    if not (win._current_pf and win._current_model):
        return
    rows = win._selected_rows()
    if not rows:
        return
    win._apply_status_to_rows(rows, status=status, label=label)
    win._update_status_combo_from_selection()


def _mark_proofread(win) -> None:
    win._apply_status_to_selection(Status.PROOFREAD, "Mark proofread")


def _mark_translated(win) -> None:
    win._apply_status_to_selection(Status.TRANSLATED, "Mark translated")


def _mark_for_review(win) -> None:
    win._apply_status_to_selection(Status.FOR_REVIEW, "Mark for review")
