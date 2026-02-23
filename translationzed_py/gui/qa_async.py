"""Asynchronous QA scan orchestration helpers for the main window."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from translationzed_py.core.languagetool import LT_LEVEL_DEFAULT
from translationzed_py.core.languagetool import LT_LEVEL_PICKY
from translationzed_py.core.languagetool import LT_STATUS_OFFLINE
from translationzed_py.core.languagetool import LT_STATUS_OK
from translationzed_py.core.languagetool import check_text as _lt_check_text
from translationzed_py.core.qa_service import QAFinding, QAInputRow
from translationzed_py.core.qa_service import QA_CODE_LANGUAGETOOL


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


def _normalize_languagetool_row_cap(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 500
    return max(1, min(5000, parsed))


def _scan_languagetool_rows(
    *,
    file: Path,
    rows: tuple[QAInputRow, ...],
    enabled: bool,
    max_rows: int,
    server_url: str,
    timeout_ms: int,
    picky_mode: bool,
    language: str,
) -> tuple[list[QAFinding], str]:
    if not enabled:
        return [], ""
    cap = _normalize_languagetool_row_cap(max_rows)
    scanned_rows = rows[:cap]
    findings: list[QAFinding] = []
    fallback_warned = False
    offline_errors = 0
    level = LT_LEVEL_PICKY if picky_mode else LT_LEVEL_DEFAULT
    for row in scanned_rows:
        text = str(row.target_text or "").strip()
        if not text:
            continue
        result = _lt_check_text(
            server_url=server_url,
            language=language,
            text=text,
            level=level,
            timeout_ms=timeout_ms,
        )
        if result.warning:
            fallback_warned = True
        if result.status == LT_STATUS_OFFLINE:
            offline_errors += 1
            continue
        if result.status != LT_STATUS_OK:
            continue
        for match in result.matches:
            excerpt = str(match.message).strip() or "LanguageTool issue"
            findings.append(
                QAFinding(
                    file=file,
                    row=row.row,
                    code=QA_CODE_LANGUAGETOOL,
                    excerpt=excerpt,
                    severity="warning",
                    group="language",
                )
            )
    notes: list[str] = []
    if len(rows) > cap:
        notes.append(f"LanguageTool scanned first {cap} row(s) due to cap.")
    if fallback_warned:
        notes.append("LanguageTool picky unsupported; default level used.")
    if offline_errors:
        notes.append("LanguageTool offline for one or more rows.")
    return findings, " ".join(notes).strip()


def _run_scan_job(
    win: Any,
    path: Path,
    rows: tuple[QAInputRow, ...],
    check_trailing: bool,
    check_newlines: bool,
    check_tokens: bool,
    check_same_as_source: bool,
) -> tuple[Path, list[QAFinding], str]:
    findings = win._qa_service.scan_rows(
        file=path,
        rows=rows,
        check_trailing=check_trailing,
        check_newlines=check_newlines,
        check_tokens=check_tokens,
        check_same_as_source=check_same_as_source,
    )
    lt_findings, lt_note = _scan_languagetool_rows(
        file=path,
        rows=rows,
        enabled=bool(getattr(win, "_qa_check_languagetool", False)),
        max_rows=int(getattr(win, "_qa_languagetool_max_rows", 500)),
        server_url=str(getattr(win, "_lt_server_url", "")),
        timeout_ms=int(getattr(win, "_lt_timeout_ms", 1200)),
        picky_mode=bool(getattr(win, "_lt_picky_mode", False)),
        language=str(getattr(win, "_qa_scan_languagetool_language", "en-US")),
    )
    merged = list(findings)
    merged.extend(lt_findings)
    return path, merged, lt_note


def start_scan(win: Any) -> None:
    """Start a background QA scan for the currently opened file."""
    path = win._current_pf.path if win._current_pf is not None else None
    if path is None or win._current_model is None:
        win._set_qa_scan_note("")
        win._set_qa_findings(())
        win._set_qa_panel_message("No file selected.")
        return
    if win._qa_scan_future is not None and not win._qa_scan_future.done():
        win._set_qa_panel_message("QA is already running...")
        return
    rows = _collect_input_rows(win)
    win._qa_scan_languagetool_language = win._resolve_lt_language_for_path(path)
    win._set_qa_scan_note("")
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
        path, findings, note = future.result()
    except Exception as exc:
        win._set_qa_scan_note("")
        win._set_qa_panel_message(f"QA failed: {exc}")
        return
    if win._current_pf is None or win._current_pf.path != path:
        return
    win._set_qa_scan_note(note)
    win._set_qa_findings(findings)
    if win._qa_auto_mark_for_review:
        rows_for_auto_mark = tuple(findings)
        if not bool(getattr(win, "_qa_languagetool_automark", False)):
            rows_for_auto_mark = tuple(
                finding
                for finding in rows_for_auto_mark
                if finding.code != QA_CODE_LANGUAGETOOL
            )
        win._apply_qa_auto_mark(rows_for_auto_mark)


def refresh_sync_for_test(win: Any) -> None:
    """Run QA scan synchronously while tests execute in test mode."""
    start_scan(win)
    if not win._test_mode:
        return
    while win._qa_scan_future is not None:
        poll_scan(win)
