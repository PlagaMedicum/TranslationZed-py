"""Asynchronous QA scan orchestration helpers for the main window."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from translationzed_py.core.qa_service import QAFinding, QAInputRow


def _collect_input_rows(win: Any) -> tuple[QAInputRow, ...]:
    model = win._current_model
    if model is None:
        return ()
    rows: list[QAInputRow] = []
    for row in model.iter_search_rows(include_source=True, include_value=True):
        rows.append(
            QAInputRow(
                row=row.row,
                source_text=str(row.source or ""),
                target_text=str(row.value or ""),
            )
        )
    return tuple(rows)


def _run_scan_job(
    win: Any,
    path: Path,
    rows: tuple[QAInputRow, ...],
    check_trailing: bool,
    check_newlines: bool,
    check_tokens: bool,
    check_same_as_source: bool,
) -> tuple[Path, list[QAFinding]]:
    findings = win._qa_service.scan_rows(
        file=path,
        rows=rows,
        check_trailing=check_trailing,
        check_newlines=check_newlines,
        check_tokens=check_tokens,
        check_same_as_source=check_same_as_source,
    )
    return path, findings


def start_scan(win: Any) -> None:
    """Start a background QA scan for the currently opened file."""
    path = win._current_pf.path if win._current_pf is not None else None
    if path is None or win._current_model is None:
        win._set_qa_findings(())
        win._set_qa_panel_message("No file selected.")
        return
    if win._qa_scan_future is not None and not win._qa_scan_future.done():
        win._set_qa_panel_message("QA is already running...")
        return
    rows = _collect_input_rows(win)
    if win._qa_scan_pool is None:
        win._qa_scan_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="tzp-qa-scan",
        )
    win._qa_scan_path = path
    win._set_qa_progress_visible(True)
    win._set_qa_panel_message("Running QA checks...")
    win._qa_scan_future = win._qa_scan_pool.submit(
        _run_scan_job,
        win,
        path,
        rows,
        win._qa_check_trailing,
        win._qa_check_newlines,
        win._qa_check_escapes,
        win._qa_check_same_as_source,
    )
    if not win._qa_scan_timer.isActive():
        win._qa_scan_timer.start()


def poll_scan(win: Any) -> None:
    """Poll the running QA scan and apply results when available."""
    future = win._qa_scan_future
    if future is None:
        win._qa_scan_timer.stop()
        win._set_qa_progress_visible(False)
        return
    if not future.done():
        return
    win._qa_scan_timer.stop()
    win._qa_scan_future = None
    win._set_qa_progress_visible(False)
    try:
        path, findings = future.result()
    except Exception as exc:
        win._set_qa_panel_message(f"QA failed: {exc}")
        return
    if win._current_pf is None or win._current_pf.path != path:
        return
    win._set_qa_findings(findings)
    if win._qa_auto_mark_for_review:
        win._apply_qa_auto_mark(findings)


def refresh_sync_for_test(win: Any) -> None:
    """Run QA scan synchronously while tests execute in test mode."""
    start_scan(win)
    if not win._test_mode:
        return
    while win._qa_scan_future is not None:
        poll_scan(win)
