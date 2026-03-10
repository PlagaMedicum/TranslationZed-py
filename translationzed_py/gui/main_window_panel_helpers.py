"""Extracted MainWindow panel/selection/status helper methods."""

from __future__ import annotations

import contextlib
import html
import os
import re
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import xxhash
from PySide6.QtCore import QItemSelectionModel, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from translationzed_py.core import parse, parse_lazy
from translationzed_py.core.file_workflow import (
    StatusCommentWritebackOptions as _StatusCommentWritebackOptions,
)
from translationzed_py.core.model import STATUS_ORDER, Entry, Status
from translationzed_py.core.project_session import (
    CrashRecoveryApplyExecution as _CrashRecoveryApplyExecution,
)
from translationzed_py.core.project_session import (
    CrashRecoveryReport as _CrashRecoveryReport,
)
from translationzed_py.core.qa_service import QA_RULE_LABELS as _QA_RULE_LABELS
from translationzed_py.core.qa_service import QA_RULE_ORDER as _QA_RULE_ORDER
from translationzed_py.core.qa_service import QA_RULE_STATE_TEXT as _QA_RULE_STATE_TEXT
from translationzed_py.core.qa_service import QAFinding as _QAFinding
from translationzed_py.core.qa_service import QARuleState as _QARuleState
from translationzed_py.core.saver import save as _save
from translationzed_py.core.search import Match as _SearchMatch
from translationzed_py.core.search import SearchField as _SearchField
from translationzed_py.core.search import SearchQueryPlan as _SearchQueryPlan
from translationzed_py.core.search import SearchRow as _SearchRow
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileParseError as _ReplaceAllFileParseError,
)
from translationzed_py.core.search_replace_service import (
    ReplaceAllFilePreviewCallbacks as _ReplaceAllFilePreviewCallbacks,
)
from translationzed_py.core.search_replace_service import (
    ReplaceAllRowsPreviewCallbacks as _ReplaceAllRowsPreviewCallbacks,
)
from translationzed_py.core.status_cache import read as _read_status_cache
from translationzed_py.core.tm_query import TMQueryKey, TMQueryPolicy
from translationzed_py.core.tm_store import TMMatch, TMStore
from translationzed_py.core.tm_workflow_service import (
    TMSelectionPlan as _TMSelectionPlan,
)

from . import languagetool_adapter as _lt_adapter
from .delegates import MAX_VISUAL_CHARS
from .dialogs import ReplaceFilesDialog
from .manual_scenario_dialog import ManualScenarioChecklistDialog
from .manual_scenario_runtime import (
    SCENARIO_ENV_FILE,
    SCENARIO_ENV_RESULTS_DIR,
    ManualScenarioError,
    ManualScenarioRuntime,
    load_manual_runtime,
)
from .perf_trace import PERF_TRACE
from .progress_metrics import (
    StatusProgress,
    from_statuses,
)
from .progress_widgets import ProgressStripRow
from .search_scope_ui import scope_icon_for as _scope_icon_for
from .tm_preview import apply_tm_preview_highlights as _apply_tm_preview_highlights
from .tm_preview import prepare_tm_preview_terms as _prepare_tm_preview_terms

_PROGRESS_POLL_INTERVAL_MS = 70
_SESSION_RESUME_WRITE_DEBOUNCE_MS = 280


def display_path_for_root(root: Path, path: Path) -> str:
    """Return path relative to root when possible, otherwise absolute-ish string."""
    with contextlib.suppress(ValueError):
        return str(path.relative_to(root))
    return str(path)


def _replace_all_preview_in_model(
    win,
    *,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
) -> tuple[tuple[int, str, str], ...] | None:
    model = getattr(win, "_current_model", None)
    if model is None:
        return ()
    callbacks = _ReplaceAllRowsPreviewCallbacks(
        row_count=model.rowCount,
        read_text=lambda row: model.index(row, 2).data(Qt.EditRole),
    )
    try:
        return win._search_replace_service.preview_replace_all_in_rows(
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
        )
    except re.error as exc:
        QMessageBox.warning(win, "Replace failed", str(exc))
        return None


def _replace_all_preview_in_file(
    win,
    *,
    path: Path,
    pattern: re.Pattern[str],
    replacement: str,
    use_regex: bool,
    matches_empty: bool,
    has_group_ref: bool,
) -> tuple[tuple[int, str, str], ...] | None:
    locale = win._locale_for_path(path)
    meta = win._locales.get(locale)
    encoding = getattr(meta, "charset", "utf-8")
    callbacks = _ReplaceAllFilePreviewCallbacks(
        parse_file=lambda file_path: parse(file_path, encoding=encoding),
        read_cache=lambda file_path: _read_status_cache(win._root, file_path),
    )
    try:
        return win._search_replace_service.preview_replace_all_in_file(
            path,
            pattern=pattern,
            replacement=replacement,
            use_regex=use_regex,
            matches_empty=matches_empty,
            has_group_ref=has_group_ref,
            callbacks=callbacks,
            hash_for_entry=lambda entry, cache_map: win._hash_for_cache(
                entry, cache_map
            ),
        )
    except _ReplaceAllFileParseError as exc:
        win._report_parse_error(exc.path, exc.original)
        return None
    except re.error as exc:
        QMessageBox.warning(win, "Replace failed", str(exc))
        return None


def build_replace_all_impact_preview(
    win,
    *,
    run_plan,
    files: list[Path],
    current_path: Path | None,
    display_name,
    request,
):
    """Build A37 replace-all impact preview using existing window adapters."""
    return win._search_replace_service.build_replace_all_impact_preview(
        run_plan=run_plan,
        files=files,
        current_file=current_path,
        display_name=display_name,
        preview_in_current=lambda: _replace_all_preview_in_model(
            win,
            pattern=request.pattern,
            replacement=request.replacement,
            use_regex=request.use_regex,
            matches_empty=request.matches_empty,
            has_group_ref=request.has_group_ref,
        ),
        preview_in_file=lambda path: _replace_all_preview_in_file(
            win,
            path=path,
            pattern=request.pattern,
            replacement=request.replacement,
            use_regex=request.use_regex,
            matches_empty=request.matches_empty,
            has_group_ref=request.has_group_ref,
        ),
        row_cap=1000,
    )


def run_replace_all(win) -> None:
    """Execute replace-all orchestration for MainWindow."""
    if not win._current_model:
        return
    request = win._prepare_replace_request()
    if request is None:
        return
    scope = win._replace_scope
    files = win._files_for_scope(scope)
    if not files:
        return
    current_path = win._current_pf.path if win._current_pf else None
    locale = win._locale_for_path(current_path) if current_path is not None else None

    def display_name(path: Path) -> str:
        return display_path_for_root(win._root, path)

    run_plan = win._search_replace_service.build_replace_all_run_plan(
        scope=scope,
        current_locale=locale,
        selected_locale_count=len(win._selected_locales),
        files=files,
        current_file=current_path,
        display_name=display_name,
        count_in_current=lambda: win._replace_all_count_in_model(
            request.pattern,
            request.replacement,
            request.use_regex,
            request.matches_empty,
            request.has_group_ref,
        ),
        count_in_file=lambda path: win._replace_all_count_in_file(
            path,
            request.pattern,
            request.replacement,
            request.use_regex,
            request.matches_empty,
            request.has_group_ref,
        ),
    )
    if run_plan is None or not run_plan.run_replace:
        return
    if run_plan.show_confirmation:
        impact_preview = build_replace_all_impact_preview(
            win,
            run_plan=run_plan,
            files=files,
            current_path=current_path,
            display_name=display_name,
            request=request,
        )
        if impact_preview is None:
            return
        dialog = ReplaceFilesDialog(
            list(run_plan.counts),
            run_plan.scope_label,
            total_matches=run_plan.total_matches,
            affected_files=run_plan.affected_files,
            impact_preview=impact_preview,
            parent=win,
        )
        dialog.exec()
        if not dialog.confirmed():
            return
    applied = win._search_replace_service.apply_replace_all(
        files=files,
        current_file=current_path,
        apply_in_current=lambda: win._replace_all_in_model(
            request.pattern,
            request.replacement,
            request.use_regex,
            request.matches_empty,
            request.has_group_ref,
        ),
        apply_in_file=lambda path: win._replace_all_in_file(
            path,
            request.pattern,
            request.replacement,
            request.use_regex,
            request.matches_empty,
            request.has_group_ref,
        ),
    )
    if not applied:
        return
    win._schedule_search()


def _run_startup_recovery(win) -> bool:
    plan = win._project_session_service.build_crash_recovery_detection_plan(
        root=win._root,
        selected_locales=win._selected_locales,
        startup_accepted=True,
        previous_session_unclean=False,
        interrupted_draft_marker=False,
    )
    report = plan.report
    if not plan.run_recovery_flow or report is None:
        return True
    decision = _prompt_startup_crash_recovery(win, report)
    apply_plan = win._project_session_service.build_crash_recovery_apply_plan(
        root=win._root,
        report=report,
        decision=decision,
    )
    execution = win._project_session_service.execute_crash_recovery_apply_plan(
        plan=apply_plan
    )
    if not execution.continue_startup:
        _abort_pending_post_locale_startup(win)
        return False
    if execution.failed_cache_paths and not _prompt_startup_discard_failure(
        win, execution
    ):
        _abort_pending_post_locale_startup(win)
        return False
    return True


def _abort_pending_post_locale_startup(win) -> None:
    if win._post_locale_timer.isActive():
        win._post_locale_timer.stop()
    win._pending_post_locale_plan = None


def _prompt_startup_discard_failure(
    win,
    execution: _CrashRecoveryApplyExecution,
) -> bool:
    msg = QMessageBox(win)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("Discard incomplete")
    msg.setText("Could not remove some recovery cache files.")
    msg.setInformativeText(
        "Continue opens the project with remaining cache entries. Cancel aborts project open."
    )
    if execution.failure_message:
        msg.setDetailedText(execution.failure_message)
    msg.setStandardButtons(
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )
    return int(msg.exec()) != int(QMessageBox.StandardButton.Cancel)


def _prompt_startup_crash_recovery(
    win,
    report: _CrashRecoveryReport,
) -> str:
    msg = QMessageBox(win)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("Recovery options")
    msg.setText(f"Found unsaved draft cache in {report.total_files} file(s).")
    msg.setInformativeText(
        "Restore keeps draft cache, Discard skips recovery for now, Cancel aborts project open."
    )
    msg.setDetailedText(_crash_recovery_details_text(report))
    msg.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    restore_btn = msg.button(QMessageBox.StandardButton.Save)
    if restore_btn is not None:
        restore_btn.setText("Restore")
    result = int(msg.exec())
    if result == int(QMessageBox.StandardButton.Discard):
        return "discard"
    if result == int(QMessageBox.StandardButton.Cancel):
        return "cancel"
    return "restore"


def _crash_recovery_details_text(report: _CrashRecoveryReport) -> str:
    lines = [
        f"Project root: {report.project_root}",
        f"Generated at (ms): {report.generated_at_ms}",
        (
            "Totals: "
            f"files={report.total_files} "
            f"draft_values={report.total_draft_values} "
            f"status_only={report.total_status_only}"
        ),
        "",
        "Affected files:",
    ]
    for item in report.affected_files:
        line = (
            f"{item.file_path} [{item.locale}] "
            f"drafts={item.draft_value_count} "
            f"status_only={item.status_only_count} "
            f"cache_mtime_ns={item.cache_mtime_ns}"
        )
        if item.warning:
            line = f"{line} warning={item.warning}"
        lines.append(line)
    return "\n".join(lines)


def _hash_for_cache_key(key: str | Entry, cache_map: dict[int, object]) -> int:
    if isinstance(key, Entry):
        digest = key.key_hash
        key_text = key.key
    else:
        digest = None
        key_text = str(key)
    if digest is None:
        digest = int(xxhash.xxh64(key_text.encode("utf-8")).intdigest())
    bits = getattr(cache_map, "hash_bits", 64)
    if bits == 16:
        return digest & 0xFFFF
    return digest & 0xFFFFFFFFFFFFFFFF


def _progress_from_model(win) -> StatusProgress | None:
    model = getattr(win, "_current_model", None)
    current = getattr(win, "_current_pf", None)
    if (
        model is None
        or current is None
        or not hasattr(model, "canonical_status_counts")
    ):
        return None
    cached = getattr(win, "_progress_current_model_cache", None)
    if (
        isinstance(cached, tuple)
        and len(cached) == 2
        and cached[0] is model
        and not getattr(win, "_progress_current_model_dirty", False)
    ):
        return cached[1]
    progress = StatusProgress.from_tuple(model.canonical_status_counts())
    win._progress_current_model_cache = (model, progress)
    win._progress_current_model_dirty = False
    return progress


def _progress_from_disk(path: Path, *, root: Path, encoding: str) -> StatusProgress:
    try:
        parsed = parse_lazy(path, encoding=encoding)
    except Exception:
        return StatusProgress()
    cache_map = _read_status_cache(root, path)
    statuses: list[Status] = []
    for entry in parsed.entries:
        status = entry.status
        cached_entry = cache_map.get(_hash_for_cache_key(entry, cache_map))
        if cached_entry is not None:
            status = cached_entry.status
        statuses.append(status)
    return from_statuses(statuses)


def _progress_for_file(win, path: Path) -> StatusProgress:
    file_cache = getattr(win, "_progress_file_progress_cache", None)
    if file_cache is None:
        file_cache = {}
        win._progress_file_progress_cache = file_cache
    current = getattr(win, "_current_pf", None)
    if current is not None and current.path == path:
        model_progress = _progress_from_model(win)
        if model_progress is not None:
            file_cache[path] = model_progress
            return model_progress
    cached_progress = file_cache.get(path)
    if cached_progress is not None:
        return cached_progress
    locale = win._locale_for_path(path)
    encoding = (
        win._locales.get(locale, None).charset if locale in win._locales else None
    ) or "utf-8"
    progress = _progress_from_disk(path, root=win._root, encoding=encoding)
    file_cache[path] = progress
    return progress


def _sum_progress(values: Sequence[StatusProgress]) -> StatusProgress:
    untouched = 0
    for_review = 0
    translated = 0
    proofread = 0
    for value in values:
        untouched += value.untouched
        for_review += value.for_review
        translated += value.translated
        proofread += value.proofread
    return StatusProgress(
        untouched=untouched,
        for_review=for_review,
        translated=translated,
        proofread=proofread,
    )


def _apply_progress_delta(
    total: StatusProgress, before: StatusProgress, after: StatusProgress
) -> StatusProgress:
    """Return *total* adjusted by replacing *before* contribution with *after*."""
    return StatusProgress(
        untouched=max(0, total.untouched - before.untouched + after.untouched),
        for_review=max(0, total.for_review - before.for_review + after.for_review),
        translated=max(0, total.translated - before.translated + after.translated),
        proofread=max(0, total.proofread - before.proofread + after.proofread),
    )


def _compute_locale_progress_task(
    *,
    root: Path,
    locale: str,
    files: tuple[Path, ...],
    locale_encoding: str,
    current_path: Path | None,
    current_counts: tuple[int, int, int, int] | None,
) -> tuple[str, tuple[int, int, int, int]]:
    values: list[StatusProgress] = []
    current_progress = StatusProgress.from_tuple(current_counts)
    for path in files:
        if (
            current_path is not None
            and current_counts is not None
            and path == current_path
        ):
            values.append(current_progress)
            continue
        values.append(_progress_from_disk(path, root=root, encoding=locale_encoding))
    return locale, _sum_progress(values).as_tuple()


def _ensure_progress_workers(win) -> None:
    if getattr(win, "_progress_locale_pool", None) is None:
        win._progress_locale_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tzp-progress"
        )
    timer = getattr(win, "_progress_locale_timer", None)
    if timer is None:
        timer = QTimer(win)
        timer.setInterval(_PROGRESS_POLL_INTERVAL_MS)
        timer.timeout.connect(lambda: _poll_locale_progress(win))
        win._progress_locale_timer = timer


def _target_locale_for_progress(win) -> str | None:
    current = getattr(win, "_current_pf", None)
    if current is not None:
        locale = win._locale_for_path(current.path)
        if locale:
            return locale
    selected = getattr(win, "_selected_locales", [])
    if selected:
        return selected[0]
    return None


def _schedule_locale_progress_refresh(win, locale: str) -> None:
    locale_cache = getattr(win, "_progress_locale_progress_cache", None)
    if locale_cache is None:
        locale_cache = {}
        win._progress_locale_progress_cache = locale_cache
    if not locale:
        return None
    win._progress_locale_target = locale
    if locale in locale_cache:
        return None
    future = getattr(win, "_progress_locale_future", None)
    if isinstance(future, Future) and not future.done():
        return None
    _ensure_progress_workers(win)
    files = tuple(win._files_for_locale(locale))
    current = getattr(win, "_current_pf", None)
    current_path = current.path if current is not None else None
    current_counts = None
    model_progress = _progress_from_model(win)
    if current_path is not None and model_progress is not None:
        current_counts = model_progress.as_tuple()
    win._progress_locale_pending_current_path = current_path
    win._progress_locale_pending_current_counts = current_counts
    locale_encoding = (
        win._locales.get(locale, None).charset if locale in win._locales else None
    ) or "utf-8"
    win._progress_locale_future = win._progress_locale_pool.submit(
        _compute_locale_progress_task,
        root=win._root,
        locale=locale,
        files=files,
        locale_encoding=locale_encoding,
        current_path=current_path,
        current_counts=current_counts,
    )
    win._progress_locale_pending = locale
    timer = getattr(win, "_progress_locale_timer", None)
    if timer is not None and not timer.isActive():
        timer.start()
    return None


def _poll_locale_progress(win) -> None:
    future = getattr(win, "_progress_locale_future", None)
    timer = getattr(win, "_progress_locale_timer", None)
    if not isinstance(future, Future):
        if timer is not None and timer.isActive():
            timer.stop()
        return
    if not future.done():
        return
    locale_cache = getattr(win, "_progress_locale_progress_cache", None)
    if locale_cache is None:
        locale_cache = {}
        win._progress_locale_progress_cache = locale_cache
    pending_locale = getattr(win, "_progress_locale_pending", None)
    pending_path = getattr(win, "_progress_locale_pending_current_path", None)
    pending_counts = getattr(win, "_progress_locale_pending_current_counts", None)
    try:
        locale, counts = future.result()
    except Exception:
        if pending_locale:
            locale_cache.pop(pending_locale, None)
        locale = None
    else:
        progress = StatusProgress.from_tuple(counts)
        file_cache = getattr(win, "_progress_file_progress_cache", None)
        if file_cache is None:
            file_cache = {}
            win._progress_file_progress_cache = file_cache
        if pending_path is not None and pending_counts is not None:
            scheduled_progress = StatusProgress.from_tuple(pending_counts)
            latest_progress = file_cache.get(pending_path)
            current = getattr(win, "_current_pf", None)
            if current is not None and current.path == pending_path:
                latest_model_progress = _progress_from_model(win)
                if latest_model_progress is not None:
                    latest_progress = latest_model_progress
            if latest_progress is not None and latest_progress != scheduled_progress:
                progress = _apply_progress_delta(
                    progress,
                    scheduled_progress,
                    latest_progress,
                )
                file_cache[pending_path] = latest_progress
        locale_cache[locale] = progress
    win._progress_locale_future = None
    win._progress_locale_pending = None
    win._progress_locale_pending_current_path = None
    win._progress_locale_pending_current_counts = None
    if timer is not None and timer.isActive():
        timer.stop()
    target_locale = getattr(win, "_progress_locale_target", None)
    if target_locale and target_locale not in locale_cache:
        _schedule_locale_progress_refresh(win, target_locale)
    _refresh_progress_ui(win)


def _set_tree_progress(
    win,
    *,
    locale: str | None,
    locale_progress: StatusProgress | None,
    file_path: Path | None,
    file_progress: StatusProgress | None,
) -> None:
    fs_model = getattr(win, "fs_model", None)
    if fs_model is None:
        return
    prev_locale = getattr(win, "_progress_tree_locale", None)
    prev_file = getattr(win, "_progress_tree_file", None)
    if prev_locale and prev_locale != locale:
        fs_model.set_locale_progress(prev_locale, None)
    if prev_file and prev_file != file_path:
        fs_model.set_file_progress(prev_file, None)
    if locale:
        fs_model.set_locale_progress(
            locale,
            locale_progress.as_tuple() if locale_progress is not None else None,
        )
    if file_path is not None:
        fs_model.set_file_progress(
            file_path,
            file_progress.as_tuple() if file_progress is not None else None,
        )
    win._progress_tree_locale = locale
    win._progress_tree_file = file_path


def _refresh_progress_ui(win) -> None:
    locale = _target_locale_for_progress(win)
    current = getattr(win, "_current_pf", None)
    file_cache = getattr(win, "_progress_file_progress_cache", None)
    if file_cache is None:
        file_cache = {}
        win._progress_file_progress_cache = file_cache
    previous_file_progress = None
    file_progress = _progress_from_model(win) if current is not None else None
    if current is not None and file_progress is not None:
        previous_file_progress = file_cache.get(current.path)
        file_cache[current.path] = file_progress
    locale_cache = getattr(win, "_progress_locale_progress_cache", None)
    if locale_cache is None:
        locale_cache = {}
        win._progress_locale_progress_cache = locale_cache
    locale_progress = locale_cache.get(locale) if locale else None
    if (
        locale
        and locale_progress is not None
        and current is not None
        and file_progress is not None
        and previous_file_progress is not None
        and previous_file_progress != file_progress
        and win._locale_for_path(current.path) == locale
    ):
        locale_progress = _apply_progress_delta(
            locale_progress,
            previous_file_progress,
            file_progress,
        )
        locale_cache[locale] = locale_progress
    locale_loading = bool(locale and locale_progress is None)
    if locale_loading:
        _schedule_locale_progress_refresh(win, locale)
    locale_row = getattr(win, "_progress_locale_row", None)
    if locale_row is not None:
        locale_row.setVisible(bool(locale))
        locale_row.set_progress(locale_progress, loading=locale_loading)
    file_row = getattr(win, "_progress_file_row", None)
    if file_row is not None:
        file_row.setVisible(current is not None)
        if current is not None:
            file_row.set_progress(file_progress, loading=False)
    _set_tree_progress(
        win,
        locale=locale,
        locale_progress=locale_progress,
        file_path=current.path if current is not None else None,
        file_progress=file_progress,
    )


def _invalidate_progress_for_path(
    win, path: Path | None, *, invalidate_locale: bool = False
) -> None:
    if path is None:
        return
    file_cache = getattr(win, "_progress_file_progress_cache", None)
    if file_cache is not None:
        file_cache.pop(path, None)
    locale_cache = getattr(win, "_progress_locale_progress_cache", None)
    if invalidate_locale and locale_cache is not None:
        locale = win._locale_for_path(path)
        if locale:
            locale_cache.pop(locale, None)
    if getattr(win, "_current_pf", None) is not None and win._current_pf.path == path:
        win._progress_current_model_dirty = True


def _init_progress_strip(win, panel_layout: QVBoxLayout) -> None:
    # Session-only progress cache; no persisted progress state is used.
    win._progress_current_model_cache = None
    win._progress_current_model_dirty = False
    win._progress_file_progress_cache = {}
    win._progress_locale_progress_cache = {}
    win._progress_locale_target = None
    win._progress_locale_pending_current_path = None
    win._progress_locale_pending_current_counts = None
    strip_parent = panel_layout.parentWidget() or win._left_panel
    strip = QWidget(strip_parent)
    layout = QVBoxLayout(strip)
    layout.setContentsMargins(6, 4, 6, 2)
    layout.setSpacing(2)
    win._progress_locale_row = ProgressStripRow("Locale", strip)
    win._progress_file_row = ProgressStripRow("Current file", strip)
    title_width = max(
        win._progress_locale_row.title_label.sizeHint().width(),
        win._progress_file_row.title_label.sizeHint().width(),
    )
    percent_width = max(
        win._progress_locale_row.percent_label.fontMetrics().horizontalAdvance(
            "T:100% P:100%"
        )
        + 2,
        win._progress_locale_row.percent_label.sizeHint().width(),
    )
    win._progress_locale_row.set_title_column_width(title_width)
    win._progress_file_row.set_title_column_width(title_width)
    win._progress_locale_row.set_percent_column_width(percent_width)
    win._progress_file_row.set_percent_column_width(percent_width)
    locale_icon = win.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
    file_icon = win.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
    win._progress_locale_row.icon_label.setPixmap(locale_icon.pixmap(14, 14))
    win._progress_file_row.icon_label.setPixmap(file_icon.pixmap(14, 14))
    win._progress_file_row.setVisible(False)
    layout.addWidget(win._progress_locale_row)
    layout.addWidget(win._progress_file_row)
    panel_layout.addWidget(strip)
    win._progress_strip = strip
    _refresh_progress_ui(win)


def _init_empty_table_placeholder(win) -> None:
    placeholder = QWidget(win)
    layout = QVBoxLayout(placeholder)
    layout.setContentsMargins(24, 18, 24, 18)
    layout.setSpacing(8)
    title = QLabel("Open a file from Project files", placeholder)
    title.setObjectName("emptyStateTitle")
    steps = QLabel(
        "1. Choose a locale file in the left tree.\n"
        "2. Edit translation strings in the table.\n"
        "3. Save changes and track progress in the sidebar.",
        placeholder,
    )
    steps.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(steps)
    layout.addStretch(1)
    win._empty_table_placeholder = placeholder
    win._right_stack.addWidget(placeholder)
    win._right_stack.setCurrentWidget(placeholder)


def _set_table_empty_state(win, empty: bool) -> None:
    if not hasattr(win, "_right_stack") or win._right_stack is None:
        return
    if getattr(win, "_merge_active", False):
        return
    if empty and getattr(win, "_empty_table_placeholder", None) is not None:
        win._right_stack.setCurrentWidget(win._empty_table_placeholder)
        return
    if getattr(win, "_table_container", None) is not None:
        win._right_stack.setCurrentWidget(win._table_container)


def _clear_table_model_for_empty_state(win) -> None:
    win.table.setModel(None)
    _set_table_empty_state(win, True)


def _shutdown_progress_workers(win) -> None:
    timer = getattr(win, "_progress_locale_timer", None)
    if timer is not None and timer.isActive():
        timer.stop()
    future = getattr(win, "_progress_locale_future", None)
    if isinstance(future, Future):
        with contextlib.suppress(Exception):
            future.cancel()
    win._progress_locale_future = None
    win._progress_locale_pending = None
    win._progress_locale_pending_current_path = None
    win._progress_locale_pending_current_counts = None
    pool = getattr(win, "_progress_locale_pool", None)
    if pool is None:
        return
    with contextlib.suppress(Exception):
        pool.shutdown(wait=False, cancel_futures=True)
    win._progress_locale_pool = None


def _set_qa_progress_visible(win, visible: bool) -> None:
    win._qa_scan_busy = bool(visible)
    win._qa_progress.setVisible(win._qa_scan_busy)
    win._qa_refresh_btn.setEnabled(not win._qa_scan_busy)


def _set_qa_progress_snapshots(win, snapshots: Sequence[object]) -> None:
    win._qa_progress_snapshots = tuple(snapshots)
    win._qa_progress_snapshot = (
        win._qa_progress_snapshots[-1] if win._qa_progress_snapshots else None
    )
    _render_qa_checklist(win)


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
    _render_qa_checklist(win)


def _refresh_qa_panel_results(win) -> None:
    if not hasattr(win, "_qa_results_list") or win._qa_results_list is None:
        return
    _render_qa_checklist(win)
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


def _render_qa_checklist(win) -> None:
    label = getattr(win, "_qa_checklist_label", None)
    if label is None:
        return
    snapshot = getattr(win, "_qa_progress_snapshot", None)
    if snapshot is None:
        label.setText("Run QA to see rule-by-rule progress.")
        return
    by_rule = {record.rule_id: record for record in snapshot.ordered_rules}
    lines: list[str] = []
    for rule_id in _QA_RULE_ORDER:
        record = by_rule.get(rule_id)
        rule_label = _QA_RULE_LABELS.get(rule_id, str(rule_id))
        if record is None:
            lines.append(
                f"{rule_label}: {_QA_RULE_STATE_TEXT.get(_QARuleState.QUEUED, 'Queued')}"
            )
            continue
        state_label = _QA_RULE_STATE_TEXT.get(record.state, record.state.value)
        row = f"{rule_label}: {state_label}"
        note = str(record.note).strip()
        if note:
            row = f"{row} ({note})"
        lines.append(row)
    summary = str(snapshot.final_summary).strip()
    if summary:
        lines.append(summary)
    label.setText("\n".join(lines) if lines else "Run QA to see rule-by-rule progress.")


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


def _search_files_for_scope(win) -> list[Path]:
    return list(win._files_for_scope(win._search_scope))


def _find_match_in_rows(
    win,
    rows: Iterable[_SearchRow],
    query: str,
    field: _SearchField,
    use_regex: bool,
    *,
    start_row: int,
    direction: int,
    case_sensitive: bool,
    prepared_plan: _SearchQueryPlan | None = None,
) -> _SearchMatch | None:
    if prepared_plan is None:
        return win._search_replace_service.find_match_in_rows(
            rows,
            query,
            field,
            use_regex,
            start_row=start_row,
            direction=direction,
            case_sensitive=case_sensitive,
        )
    return win._search_replace_service.find_match_in_rows(
        rows,
        query,
        field,
        use_regex,
        start_row=start_row,
        direction=direction,
        case_sensitive=case_sensitive,
        prepared_plan=prepared_plan,
    )


def _search_rows_for_file(
    win,
    path: Path,
    *,
    include_source: bool,
    include_value: bool,
) -> Iterable[_SearchRow]:
    locale = win._locale_for_path(path)
    is_current = bool(win._current_pf and path == win._current_pf.path)
    plan = win._search_replace_service.build_rows_source_plan(
        locale_known=bool(locale),
        is_current_file=is_current,
        has_current_model=bool(win._current_model),
    )
    if not plan.has_rows:
        return ()
    if plan.use_active_model_rows:
        return win._rows_from_model(
            include_source=include_source,
            include_value=include_value,
        )
    assert locale is not None
    return win._cached_rows_from_file(
        path,
        locale,
        include_source=include_source,
        include_value=include_value,
    )


def _find_match_in_file(
    win,
    path: Path,
    *,
    query: str,
    field: _SearchField,
    use_regex: bool,
    include_source: bool,
    include_value: bool,
    start_row: int,
    direction: int,
    prepared_plan: _SearchQueryPlan | None = None,
) -> _SearchMatch | None:
    rows = win._search_rows_for_file(
        path,
        include_source=include_source,
        include_value=include_value,
    )
    return win._find_match_in_rows(
        rows,
        query,
        field,
        use_regex,
        start_row=start_row,
        direction=direction,
        case_sensitive=win._search_case_sensitive,
        prepared_plan=prepared_plan,
    )


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


def _prepare_manual_scenario(
    win, selected_locales: list[str] | None
) -> list[str] | None:
    runtime_path = str(os.environ.get(SCENARIO_ENV_FILE, "")).strip()
    if not runtime_path:
        return selected_locales
    try:
        runtime = load_manual_runtime(Path(runtime_path))
    except ManualScenarioError as exc:
        QMessageBox.warning(win, "Manual scenario ignored", str(exc))
        return selected_locales
    win._manual_scenario_runtime = runtime
    win._manual_scenario_dialog_shown = False
    win._manual_scenario_dialog = None
    if runtime.scenario.prefs_extras:
        win._prefs_extras.update(runtime.scenario.prefs_extras)
    if selected_locales is not None:
        return selected_locales
    if runtime.scenario.selected_locales:
        return list(runtime.scenario.selected_locales)
    return selected_locales


def _manual_scenario_results_dir() -> Path:
    raw = str(os.environ.get(SCENARIO_ENV_RESULTS_DIR, "")).strip()
    if raw:
        return Path(raw).resolve()
    return (Path.cwd() / "artifacts" / "manual-ui").resolve()


def _show_manual_scenario_dialog(win) -> None:
    runtime = getattr(win, "_manual_scenario_runtime", None)
    if not isinstance(runtime, ManualScenarioRuntime):
        return
    active_dialog = getattr(win, "_manual_scenario_dialog", None)
    if active_dialog is not None:
        with contextlib.suppress(RuntimeError, AttributeError):
            if active_dialog.isVisible():
                active_dialog.raise_()
                active_dialog.activateWindow()
                return
    if bool(getattr(win, "_manual_scenario_dialog_shown", False)):
        return
    win._manual_scenario_dialog_shown = True
    dialog = ManualScenarioChecklistDialog(
        runtime,
        results_dir=_manual_scenario_results_dir(),
        parent=win,
    )
    win._manual_scenario_dialog = dialog
    dialog.setModal(False)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def _on_finished(_result_code: int) -> None:
        result = dialog.final_result
        if result:
            win.statusBar().showMessage(
                f"Manual scenario '{runtime.scenario.id}' marked {result}.",
                8000,
            )
        win._manual_scenario_dialog = None

    dialog.finished.connect(_on_finished)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def _schedule_post_startup_hooks(win) -> None:
    win._schedule_post_locale_tasks()
    if isinstance(
        getattr(win, "_manual_scenario_runtime", None), ManualScenarioRuntime
    ):
        QTimer.singleShot(0, lambda: _show_manual_scenario_dialog(win))


def _init_session_resume_runtime(win) -> None:
    if hasattr(win, "_session_resume_timer") and win._session_resume_timer is not None:
        return
    win._session_resume_timer = QTimer(win)
    win._session_resume_timer.setSingleShot(True)
    win._session_resume_timer.setInterval(_SESSION_RESUME_WRITE_DEBOUNCE_MS)
    win._session_resume_timer.timeout.connect(
        lambda: _flush_session_resume_snapshot(win)
    )
    win._session_resume_startup_pending = True
    win._session_resume_apply_in_progress = False
    win._session_resume_write_pending = False


def _complete_session_resume_startup(win) -> None:
    if not bool(getattr(win, "_session_resume_startup_pending", False)):
        return
    win._session_resume_startup_pending = False
    _schedule_session_resume_snapshot(win)


def _schedule_session_resume_snapshot(win) -> None:
    timer = getattr(win, "_session_resume_timer", None)
    if timer is None:
        return
    if bool(getattr(win, "_startup_aborted", False)):
        return
    if bool(getattr(win, "_session_resume_startup_pending", False)):
        return
    if bool(getattr(win, "_session_resume_apply_in_progress", False)):
        return
    win._session_resume_write_pending = True
    if timer.isActive():
        timer.stop()
    timer.start()


def _flush_session_resume_snapshot(win) -> None:
    if not bool(getattr(win, "_session_resume_write_pending", False)):
        return
    win._session_resume_write_pending = False
    if bool(getattr(win, "_session_resume_startup_pending", False)):
        return
    if bool(getattr(win, "_session_resume_apply_in_progress", False)):
        return
    try:
        snapshot = _build_session_resume_snapshot(win)
        win._project_session_service.write_session_resume_snapshot(
            root=win._root,
            snapshot=snapshot,
        )
    except Exception:
        return


def _build_session_resume_snapshot(win):
    current = getattr(win, "_current_pf", None)
    active_file_relpath = None
    if current is not None:
        with contextlib.suppress(Exception):
            active_file_relpath = current.path.relative_to(win._root).as_posix()
    active_row = None
    if getattr(win, "_current_model", None) is not None:
        current_index = win.table.currentIndex()
        if current_index.isValid():
            active_row = int(current_index.row())
    left_panel_index = 0
    left_stack = getattr(win, "_left_stack", None)
    if left_stack is not None:
        left_panel_index = max(0, int(left_stack.currentIndex()))
    detail_panel = getattr(win, "_detail_panel", None)
    detail_visible = bool(detail_panel is not None and detail_panel.isVisible())
    search_text = win.search_edit.text() if getattr(win, "search_edit", None) else ""
    replace_text = win.replace_edit.text() if getattr(win, "replace_edit", None) else ""
    return win._project_session_service.build_session_resume_snapshot(
        generated_at_ms=int(time.time() * 1000),
        selected_locales=list(getattr(win, "_selected_locales", [])),
        active_file_relpath=active_file_relpath,
        active_row=active_row,
        left_panel_index=left_panel_index,
        detail_visible=detail_visible,
        search_text=search_text,
        replace_text=replace_text,
        search_case_sensitive=bool(getattr(win, "_search_case_sensitive", False)),
        tm_min_score=int(getattr(win, "_tm_min_score", 50)),
        tm_grouping_mode=str(getattr(win, "_tm_grouping", "none")),
        tm_origin_project=bool(getattr(win, "_tm_origin_project", True)),
        tm_origin_import=bool(getattr(win, "_tm_origin_import", True)),
    )


def _apply_session_resume_snapshot(win) -> bool:
    if not bool(getattr(win, "_session_resume_startup_pending", False)):
        return False
    snapshot = win._project_session_service.read_session_resume_snapshot(root=win._root)
    if snapshot is None:
        return False
    win._session_resume_apply_in_progress = True
    try:
        _apply_session_resume_locales(win, snapshot.selected_locales)
        _apply_session_resume_panel_state(win, int(snapshot.left_panel_index))
        _apply_session_resume_detail_visibility(win, bool(snapshot.detail_visible))
        _apply_session_resume_search_state(
            win,
            search_text=str(snapshot.search_text),
            replace_text=str(snapshot.replace_text),
            search_case_sensitive=bool(snapshot.search_case_sensitive),
        )
        _apply_session_resume_tm_state(
            win,
            tm_min_score=int(snapshot.tm_min_score),
            tm_grouping_mode=str(snapshot.tm_grouping_mode),
            tm_origin_project=bool(snapshot.tm_origin_project),
            tm_origin_import=bool(snapshot.tm_origin_import),
        )
        return _apply_session_resume_active_context(
            win,
            active_file_relpath=snapshot.active_file_relpath,
            active_row=snapshot.active_row,
        )
    except Exception:
        return False
    finally:
        win._session_resume_apply_in_progress = False


def _apply_session_resume_locales(win, selected_locales: Sequence[str]) -> None:
    if not selected_locales:
        return
    plan = win._project_session_service.build_locale_switch_plan(
        requested_locales=selected_locales,
        available_locales=win._locales.keys(),
        current_locales=win._selected_locales,
    )
    if plan is None or not plan.should_apply:
        return
    win._selected_locales = list(plan.selected_locales)
    win._sync_source_reference_mode(persist=False)
    if plan.reset_session_state:
        reset_plan = win._project_session_service.build_locale_reset_plan()
        win._apply_locale_reset_plan(reset_plan)
    tree_plan = win._project_session_service.build_tree_rebuild_plan(
        selected_locales=win._selected_locales,
        resize_splitter=False,
    )
    win._rebuild_tree_for_selected_locales(tree_plan=tree_plan)
    win._tm_bootstrap_pending = plan.tm_bootstrap_pending


def _apply_session_resume_panel_state(win, panel_index: int) -> None:
    if not hasattr(win, "_left_stack"):
        return
    count = int(win._left_stack.count())
    if count <= 0:
        return
    target_index = max(0, min(int(panel_index), count - 1))
    button = win._left_group.button(target_index)
    if button is None:
        win._left_stack.setCurrentIndex(target_index)
        return
    if not button.isChecked():
        button.setChecked(True)
    win._on_left_panel_changed(button)


def _apply_session_resume_detail_visibility(win, detail_visible: bool) -> None:
    if not hasattr(win, "detail_toggle"):
        return
    if bool(win.detail_toggle.isChecked()) != bool(detail_visible):
        win.detail_toggle.setChecked(bool(detail_visible))
    else:
        win._toggle_detail_panel(bool(detail_visible))


def _apply_session_resume_search_state(
    win,
    *,
    search_text: str,
    replace_text: str,
    search_case_sensitive: bool,
) -> None:
    if hasattr(win, "search_edit") and win.search_edit.text() != search_text:
        win.search_edit.setText(search_text)
    if hasattr(win, "replace_edit") and win.replace_edit.text() != replace_text:
        win.replace_edit.setText(replace_text)
    win._search_case_sensitive = bool(search_case_sensitive)
    win._prefs_extras["SEARCH_CASE_SENSITIVE"] = (
        "true" if win._search_case_sensitive else "false"
    )
    if hasattr(win, "search_case_btn"):
        win.search_case_btn.blockSignals(True)
        try:
            win.search_case_btn.setChecked(win._search_case_sensitive)
        finally:
            win.search_case_btn.blockSignals(False)
    win._update_case_toggle_ui()
    win._on_search_controls_changed()


def _apply_session_resume_tm_state(
    win,
    *,
    tm_min_score: int,
    tm_grouping_mode: str,
    tm_origin_project: bool,
    tm_origin_import: bool,
) -> None:
    plan = win._tm_workflow.build_filter_plan(
        source_locale=win._tm_source_locale,
        min_score=int(tm_min_score),
        origin_project=bool(tm_origin_project),
        origin_import=bool(tm_origin_import),
        grouping=tm_grouping_mode,
    )
    win._tm_apply_filter_plan(plan)
    win._schedule_tm_update()


def _apply_session_resume_active_context(
    win,
    *,
    active_file_relpath: str | None,
    active_row: int | None,
) -> bool:
    path = win._project_session_service.resolve_session_resume_active_path(
        root=win._root,
        active_file_relpath=active_file_relpath,
    )
    if path is None or not path.exists():
        return False
    index = win.fs_model.index_for_path(path)
    if not index.isValid():
        return False
    win._file_chosen(index)
    if (
        win._current_pf is None
        or win._current_pf.path != path
        or win._current_model is None
    ):
        return False
    if active_row is None:
        return True
    row = int(active_row)
    if row < 0 or row >= win._current_model.rowCount():
        return False
    column = 2 if win._current_model.columnCount() > 2 else 0
    model_index = win._current_model.index(row, column)
    selection = win.table.selectionModel()
    if selection is None:
        return False
    selection.setCurrentIndex(
        model_index,
        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
    )
    win.table.scrollTo(model_index, QAbstractItemView.PositionAtCenter)
    return True


def _save_parsed_file_with_writeback(
    _win,
    parsed_file,
    changed_values,
    encoding: str,
    writeback: _StatusCommentWritebackOptions,
):
    return _save(
        parsed_file,
        changed_values,
        encoding=encoding,
        write_tzp_status_comments=writeback.enabled,
        tzp_comment_prefix=writeback.comment_prefix,
        status_by_key=writeback.status_by_key,
    )


def _status_comment_writeback_options(
    win,
    include_current_model_overrides: bool = False,
) -> _StatusCommentWritebackOptions:
    raw_enabled = str(win._prefs_extras.get("TZP_STATUS_COMMENT_WRITEBACK", "")).strip()
    enabled = raw_enabled.lower() in {"1", "true", "yes", "on"}
    raw_prefix = str(win._prefs_extras.get("TZP_STATUS_COMMENT_PREFIX", "")).strip()
    comment_prefix = (
        raw_prefix
        or str(win._app_config.comment_prefix).strip()
        or _StatusCommentWritebackOptions.comment_prefix
    )
    status_by_key: dict[str, Status] | None = None
    if include_current_model_overrides and win._current_model is not None:
        status_by_key = {}
        for (
            key,
            _source,
            _value,
            status_code,
        ) in win._current_model.changed_rows_with_source():
            with contextlib.suppress(ValueError):
                status_by_key[key] = Status(int(status_code))
        if not status_by_key:
            status_by_key = None
    return _StatusCommentWritebackOptions(
        enabled=enabled,
        comment_prefix=comment_prefix,
        status_by_key=status_by_key,
    )


def _tzp_writeback_preferences_payload(win) -> dict[str, object]:
    raw_enabled = str(win._prefs_extras.get("TZP_STATUS_COMMENT_WRITEBACK", "")).strip()
    enabled = raw_enabled.lower() in {"1", "true", "yes", "on"}
    prefix = (
        str(win._prefs_extras.get("TZP_STATUS_COMMENT_PREFIX", "")).strip()
        or str(win._app_config.comment_prefix).strip()
        or _StatusCommentWritebackOptions.comment_prefix
    )
    return {
        "tzp_writeback_enabled": enabled,
        "tzp_comment_prefix": prefix,
    }


def _apply_tzp_writeback_preferences_for_window(win, values: dict[str, object]) -> None:
    enabled = bool(values.get("tzp_writeback_enabled", False))
    prefix = str(values.get("tzp_comment_prefix", "")).strip()
    if enabled:
        win._prefs_extras["TZP_STATUS_COMMENT_WRITEBACK"] = "true"
    else:
        win._prefs_extras.pop("TZP_STATUS_COMMENT_WRITEBACK", None)
    if prefix:
        win._prefs_extras["TZP_STATUS_COMMENT_PREFIX"] = prefix
    else:
        win._prefs_extras.pop("TZP_STATUS_COMMENT_PREFIX", None)


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
    if roles is None or Qt.EditRole in roles or Qt.DisplayRole in roles:
        win._progress_current_model_dirty = True
        _refresh_progress_ui(win)
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
        _schedule_session_resume_snapshot(win)
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


def _ensure_tm_quick_actions(win) -> None:
    if getattr(win, "_tm_quick_actions_ready", False):
        return

    def _next() -> None:
        _tm_select_neighbor(win, step=1)

    def _prev() -> None:
        _tm_select_neighbor(win, step=-1)

    def _apply() -> None:
        if win._left_stack.currentIndex() != 1:
            return
        win._apply_tm_selection()

    win._tm_next_shortcut = QShortcut(QKeySequence("Alt+Down"), win)
    win._tm_next_shortcut.activated.connect(_next)
    win._tm_prev_shortcut = QShortcut(QKeySequence("Alt+Up"), win)
    win._tm_prev_shortcut.activated.connect(_prev)
    win._tm_apply_shortcut = QShortcut(QKeySequence("Ctrl+Return"), win)
    win._tm_apply_shortcut.activated.connect(_apply)
    win._tm_apply_shortcut_numpad = QShortcut(QKeySequence("Ctrl+Enter"), win)
    win._tm_apply_shortcut_numpad.activated.connect(_apply)
    win._tm_quick_actions_ready = True


def _tm_select_neighbor(win, *, step: int) -> None:
    if win._left_stack.currentIndex() != 1:
        return
    total = win._tm_list.count()
    if total <= 0:
        return
    current = win._tm_list.currentRow()
    start = current if current >= 0 else (-1 if step > 0 else total)
    for offset in range(1, total + 1):
        row = (start + (offset * step)) % total
        data = win._tm_list.item(row).data(Qt.UserRole)
        if isinstance(data, TMMatch):
            win._tm_list.setCurrentRow(row)
            return


def _set_tm_list_placeholder(win, text: str) -> None:
    """Show a non-selectable placeholder row inside the TM results list."""
    win._tm_list.clear()
    message = str(text).strip() or "Select row to see Translation Memory suggestions."
    item = QListWidgetItem(message)
    item.setFlags(Qt.ItemIsEnabled)
    item.setData(int(Qt.UserRole) + 7, True)
    win._tm_list.insertItem(0, item)


def _init_search_panel_controls(
    win,
    *,
    search_layout: QVBoxLayout,
    search_header: QHBoxLayout,
    placeholder_text: str,
) -> None:
    win._search_panel_query_edit = QLineEdit(win._search_panel)
    win._search_panel_query_edit.setPlaceholderText("Search")
    win._search_panel_query_edit.textChanged.connect(
        lambda _text: _sync_search_toolbar_from_sidebar(win)
    )
    win._search_panel_query_edit.returnPressed.connect(win._trigger_search)
    win._search_panel_prev_btn = QToolButton(win._search_panel)
    win._search_panel_prev_btn.setAutoRaise(True)
    win._search_panel_prev_btn.setIcon(
        win.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
    )
    win._search_panel_prev_btn.setToolTip("Find previous match")
    win._search_panel_prev_btn.clicked.connect(win._search_prev)
    win._search_panel_next_btn = QToolButton(win._search_panel)
    win._search_panel_next_btn.setAutoRaise(True)
    win._search_panel_next_btn.setIcon(
        win.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
    )
    win._search_panel_next_btn.setToolTip("Find next match")
    win._search_panel_next_btn.clicked.connect(win._search_next)
    win._search_panel_replace_edit = QLineEdit(win._search_panel)
    win._search_panel_replace_edit.setPlaceholderText("Replace")
    win._search_panel_replace_edit.textChanged.connect(
        lambda _text: _sync_search_toolbar_from_sidebar(win)
    )
    win._search_panel_replace_btn = QToolButton(win._search_panel)
    win._search_panel_replace_btn.setAutoRaise(True)
    win._search_panel_replace_btn.setIcon(
        win.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
    )
    win._search_panel_replace_btn.setToolTip("Replace current match in Trans")
    win._search_panel_replace_btn.clicked.connect(win._replace_current)
    win._search_panel_replace_all_btn = QToolButton(win._search_panel)
    win._search_panel_replace_all_btn.setAutoRaise(True)
    win._search_panel_replace_all_btn.setText("All")
    win._search_panel_replace_all_btn.setToolTip(
        "Replace all matches in the active replace scope"
    )
    win._search_panel_replace_all_btn.clicked.connect(win._replace_all)
    win._search_panel_regex_check = QCheckBox("Regex", win._search_panel)
    win._search_panel_regex_check.toggled.connect(
        lambda _checked: _sync_search_toolbar_from_sidebar(win)
    )
    win._search_panel_case_btn = QToolButton(win._search_panel)
    win._search_panel_case_btn.setCheckable(True)
    win._search_panel_case_btn.setAutoRaise(True)
    win._search_panel_case_btn.setText("Aa")
    win._search_panel_case_btn.toggled.connect(
        lambda _checked: _sync_search_toolbar_from_sidebar(win)
    )
    win._search_panel_mode_combo = QComboBox(win._search_panel)
    win._search_panel_mode_combo.addItem("Key", 0)
    win._search_panel_mode_combo.addItem("Source", 1)
    win._search_panel_mode_combo.addItem("Trans", 2)
    win._search_panel_mode_combo.currentIndexChanged.connect(
        lambda _index: _sync_search_toolbar_from_sidebar(win)
    )

    search_query_row = QHBoxLayout()
    search_query_row.setContentsMargins(0, 0, 0, 0)
    search_query_row.setSpacing(4)
    search_query_row.addWidget(win._search_panel_query_edit, 1)
    search_query_row.addWidget(win._search_panel_prev_btn)
    search_query_row.addWidget(win._search_panel_next_btn)
    search_replace_row = QHBoxLayout()
    search_replace_row.setContentsMargins(0, 0, 0, 0)
    search_replace_row.setSpacing(4)
    search_replace_row.addWidget(win._search_panel_replace_edit, 1)
    search_replace_row.addWidget(win._search_panel_replace_btn)
    search_replace_row.addWidget(win._search_panel_replace_all_btn)
    search_options_row = QHBoxLayout()
    search_options_row.setContentsMargins(0, 0, 0, 0)
    search_options_row.setSpacing(6)
    search_options_row.addWidget(win._search_panel_regex_check)
    search_options_row.addWidget(win._search_panel_case_btn)
    search_options_row.addWidget(QLabel("Search in:", win._search_panel))
    search_options_row.addWidget(win._search_panel_mode_combo)
    search_options_row.addStretch(1)
    search_header.addWidget(win._search_prefs_btn)
    win._search_results_list = QListWidget(win._search_panel)
    win._search_results_list.setSelectionMode(QAbstractItemView.SingleSelection)
    win._search_results_list.itemActivated.connect(win._open_search_result_item)
    win._search_results_list.itemClicked.connect(win._open_search_result_item)
    _set_search_list_placeholder(win, placeholder_text)
    search_layout.addLayout(search_header)
    search_layout.addLayout(search_query_row)
    search_layout.addLayout(search_replace_row)
    search_layout.addLayout(search_options_row)
    search_layout.addWidget(win._search_results_list)
    _sync_search_sidebar_from_toolbar(win)
    _sync_search_sidebar_enabled_state(win)


def _sync_search_sidebar_from_toolbar(win) -> None:
    if win._search_control_sync_in_progress:
        return
    if not hasattr(win, "_search_panel_query_edit"):
        return
    win._search_control_sync_in_progress = True
    try:
        query = win.search_edit.text()
        replacement = win.replace_edit.text()
        regex_checked = win.regex_check.isChecked()
        case_checked = win.search_case_btn.isChecked()
        mode_index = win.search_mode.currentIndex()
        if win._search_panel_query_edit.text() != query:
            win._search_panel_query_edit.setText(query)
        if win._search_panel_replace_edit.text() != replacement:
            win._search_panel_replace_edit.setText(replacement)
        if win._search_panel_regex_check.isChecked() != regex_checked:
            win._search_panel_regex_check.setChecked(regex_checked)
        if win._search_panel_case_btn.isChecked() != case_checked:
            win._search_panel_case_btn.setChecked(case_checked)
        if win._search_panel_mode_combo.currentIndex() != mode_index:
            win._search_panel_mode_combo.setCurrentIndex(mode_index)
    finally:
        win._search_control_sync_in_progress = False
    _sync_search_sidebar_enabled_state(win)


def _sync_search_toolbar_from_sidebar(win) -> None:
    if win._search_control_sync_in_progress:
        return
    if not hasattr(win, "_search_panel_query_edit"):
        return
    win._search_control_sync_in_progress = True
    try:
        query = win._search_panel_query_edit.text()
        replacement = win._search_panel_replace_edit.text()
        regex_checked = win._search_panel_regex_check.isChecked()
        case_checked = win._search_panel_case_btn.isChecked()
        mode_index = win._search_panel_mode_combo.currentIndex()
        if win.search_edit.text() != query:
            win.search_edit.setText(query)
        if win.replace_edit.text() != replacement:
            win.replace_edit.setText(replacement)
        if win.regex_check.isChecked() != regex_checked:
            win.regex_check.setChecked(regex_checked)
        if win.search_case_btn.isChecked() != case_checked:
            win.search_case_btn.setChecked(case_checked)
        if win.search_mode.currentIndex() != mode_index:
            win.search_mode.setCurrentIndex(mode_index)
    finally:
        win._search_control_sync_in_progress = False
    _sync_search_sidebar_enabled_state(win)


def _sync_search_sidebar_enabled_state(win) -> None:
    if not hasattr(win, "_search_panel_replace_edit"):
        return
    win._search_panel_replace_edit.setEnabled(win.replace_edit.isEnabled())
    win._search_panel_replace_btn.setEnabled(win.replace_btn.isEnabled())
    win._search_panel_replace_all_btn.setEnabled(win.replace_all_btn.isEnabled())


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
    _ensure_tm_explanation_panel(win)
    explain = getattr(win, "_tm_explain_preview", None)
    if not plan.apply_enabled:
        win._tm_source_preview.clear()
        win._tm_target_preview.clear()
        win._tm_source_preview.setExtraSelections([])
        win._tm_target_preview.setExtraSelections([])
        if isinstance(explain, QPlainTextEdit):
            explain.setPlainText(
                getattr(
                    plan,
                    "explanation_preview",
                    "Select a TM suggestion to see explanation.",
                )
            )
        return
    win._tm_source_preview.setPlainText(plan.source_preview)
    win._tm_target_preview.setPlainText(plan.target_preview)
    if isinstance(explain, QPlainTextEdit):
        explain.setPlainText(
            getattr(
                plan,
                "explanation_preview",
                "No explainability details for this suggestion.",
            )
        )
    terms = _prepare_tm_preview_terms(plan.query_terms)
    with contextlib.suppress(Exception):
        _apply_tm_preview_highlights(win._tm_source_preview, terms)
        _apply_tm_preview_highlights(win._tm_target_preview, terms)


def _ensure_tm_explanation_panel(win) -> None:
    if hasattr(win, "_tm_explain_preview"):
        return
    container = getattr(win, "_tm_preview_container", None)
    if not isinstance(container, QWidget):
        return
    layout = container.layout()
    if not isinstance(layout, QVBoxLayout):
        return
    label = QLabel("TM Explanation", container)
    preview = QPlainTextEdit(container)
    preview.setReadOnly(True)
    preview.setPlaceholderText("Why this suggestion matched")
    preview.setMinimumHeight(56)
    layout.addWidget(label)
    layout.addWidget(preview, 1)
    win._tm_explain_label = label
    win._tm_explain_preview = preview


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
    win._tm_grouping = plan.grouping
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
    combo = getattr(win, "_tm_grouping_combo", None)
    if combo is not None:
        grouping_index = combo.findData(win._tm_grouping)
        if grouping_index >= 0 and combo.currentIndex() != grouping_index:
            combo.blockSignals(True)
            try:
                combo.setCurrentIndex(grouping_index)
            finally:
                combo.blockSignals(False)


def _on_tm_filters_changed(win) -> None:
    grouping = "none"
    combo = getattr(win, "_tm_grouping_combo", None)
    if combo is not None:
        grouping = str(combo.currentData() or "none")
    plan = win._tm_workflow.build_filter_plan(
        source_locale=win._tm_source_locale,
        min_score=int(win._tm_score_spin.value()),
        origin_project=bool(win._tm_origin_project_cb.isChecked()),
        origin_import=bool(win._tm_origin_import_cb.isChecked()),
        grouping=grouping,
    )
    win._tm_apply_filter_plan(plan)
    win._persist_preferences()
    win._update_tm_suggestions()
    _schedule_session_resume_snapshot(win)


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
    _ensure_tm_quick_actions(win)
    win._tm_list.clear()
    view = win._tm_workflow.build_suggestions_view(
        matches=matches,
        policy=win._tm_query_policy(),
        source_preview_limit=60,
        target_preview_limit=80,
        grouping=getattr(win, "_tm_grouping", "none"),
    )
    if not view.items:
        win._set_tm_list_placeholder(view.message)
        win._tm_apply_btn.setEnabled(False)
        win._set_tm_preview(
            win._tm_workflow.build_selection_plan(match=None, lookup=None)
        )
        return
    for view_item in view.items:
        group_label = getattr(view_item, "group_label", None)
        if group_label:
            group_item = QListWidgetItem(group_label)
            group_item.setFlags(Qt.ItemIsEnabled)
            group_item.setData(int(Qt.UserRole) + 7, True)
            win._tm_list.addItem(group_item)
        item = QListWidgetItem(view_item.label)
        item.setData(Qt.UserRole, view_item.match)
        item.setToolTip(view_item.tooltip_html)
        win._tm_list.addItem(item)
    first_match_row = -1
    for row in range(win._tm_list.count()):
        data = win._tm_list.item(row).data(Qt.UserRole)
        if isinstance(data, TMMatch):
            first_match_row = row
            break
    if first_match_row >= 0:
        win._tm_list.setCurrentRow(first_match_row)
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


def _mixed_selection_status_text(win) -> str | None:
    if not win._current_model:
        return None
    status_for_row = getattr(win._current_model, "status_for_row", None)
    if not callable(status_for_row):
        return None
    rows = win._selected_rows()
    if len(rows) < 2:
        return None
    statuses = {status_for_row(row) for row in rows}
    statuses.discard(None)
    if len(statuses) <= 1:
        return None
    return f"Selection: mixed ({len(rows)} rows)"


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
    if mixed_selection := _mixed_selection_status_text(win):
        parts.append(mixed_selection)
    if win._current_pf:
        try:
            rel = win._current_pf.path.relative_to(win._root)
            parts.append(rel.as_posix())
        except ValueError:
            parts.append(win._current_pf.path.as_posix())
    if not parts:
        parts.append("Ready to edit")
    win.statusBar().showMessage(" | ".join(parts))
    _refresh_progress_ui(win)
    win._update_scope_indicators()
    _schedule_session_resume_snapshot(win)


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
