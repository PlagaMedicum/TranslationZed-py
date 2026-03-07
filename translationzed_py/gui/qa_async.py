"""Asynchronous QA scan orchestration helpers for the main window."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from translationzed_py.core.languagetool import (
    LT_LEVEL_DEFAULT,
    LT_LEVEL_PICKY,
    LT_STATUS_OFFLINE,
    LT_STATUS_OK,
)
from translationzed_py.core.languagetool import check_text as _lt_check_text
from translationzed_py.core.qa_service import (
    QA_CODE_LANGUAGETOOL,
    QA_RULE_ORDER,
    QAFinding,
    QAInputRow,
    QARuleId,
    QARuleProgressRecord,
    QARuleState,
    QAScanProgressSnapshot,
)

_STANDARD_QA_RULES: tuple[QARuleId, ...] = (
    "trailing",
    "newlines",
    "tokens",
    "same_source",
)


@dataclass(frozen=True, slots=True)
class _LTScanResult:
    """Represent LanguageTool scan result state for one QA run."""

    findings: tuple[QAFinding, ...]
    note: str
    state: QARuleState


@dataclass(frozen=True, slots=True)
class QAScanJobResult:
    """Represent one completed QA async scan job payload."""

    run_id: str
    path: Path
    findings: tuple[QAFinding, ...]
    note: str
    snapshots: tuple[QAScanProgressSnapshot, ...]


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


def _normalize_result_limit(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 500
    return max(1, min(5000, parsed))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_qa_run_id() -> str:
    return f"qa-{uuid.uuid4().hex}"


def _enabled_qa_rules(
    *,
    check_trailing: bool,
    check_newlines: bool,
    check_tokens: bool,
    check_same_as_source: bool,
    check_languagetool: bool,
) -> tuple[QARuleId, ...]:
    enabled: list[QARuleId] = []
    if check_trailing:
        enabled.append("trailing")
    if check_newlines:
        enabled.append("newlines")
    if check_tokens:
        enabled.append("tokens")
    if check_same_as_source:
        enabled.append("same_source")
    if check_languagetool:
        enabled.append("languagetool")
    return tuple(enabled)


def _append_snapshot(
    win: Any,
    *,
    run_id: str,
    path: Path,
    records: tuple[QARuleProgressRecord, ...],
    snapshots: list[QAScanProgressSnapshot],
    summary: str,
) -> None:
    snapshot = win._qa_service.build_progress_snapshot(
        run_id=run_id,
        file_path=path,
        ordered_rules=records,
        final_summary=summary,
    )
    snapshots.append(snapshot)


def _transition_rule(
    win: Any,
    *,
    records: tuple[QARuleProgressRecord, ...],
    run_id: str,
    rule_id: QARuleId,
    new_state: QARuleState,
    timestamp_ms: int,
    findings_count: int | None = None,
    note: str | None = None,
) -> tuple[QARuleProgressRecord, ...]:
    return win._qa_service.transition_rule_state(
        records=records,
        run_id=run_id,
        rule_id=rule_id,
        new_state=new_state,
        timestamp_ms=timestamp_ms,
        findings_count=findings_count,
        note=note,
    )


def _mark_rule_skipped(
    win: Any,
    *,
    records: tuple[QARuleProgressRecord, ...],
    run_id: str,
    rule_id: QARuleId,
    note: str,
    path: Path,
    snapshots: list[QAScanProgressSnapshot],
) -> tuple[QARuleProgressRecord, ...]:
    ts = _now_ms()
    progressed = _transition_rule(
        win,
        records=records,
        run_id=run_id,
        rule_id=rule_id,
        new_state=QARuleState.RUNNING,
        timestamp_ms=ts,
    )
    _append_snapshot(
        win,
        run_id=run_id,
        path=path,
        records=progressed,
        snapshots=snapshots,
        summary="Running QA checks...",
    )
    completed = _transition_rule(
        win,
        records=progressed,
        run_id=run_id,
        rule_id=rule_id,
        new_state=QARuleState.SKIPPED,
        timestamp_ms=ts,
        findings_count=0,
        note=note,
    )
    _append_snapshot(
        win,
        run_id=run_id,
        path=path,
        records=completed,
        snapshots=snapshots,
        summary="Running QA checks...",
    )
    return completed


def _scan_standard_rule(
    win: Any,
    *,
    file: Path,
    rows: tuple[QAInputRow, ...],
    rule_id: QARuleId,
) -> tuple[QAFinding, ...]:
    return tuple(
        win._qa_service.scan_rows(
            file=file,
            rows=rows,
            check_trailing=rule_id == "trailing",
            check_newlines=rule_id == "newlines",
            check_tokens=rule_id == "tokens",
            check_same_as_source=rule_id == "same_source",
        )
    )


def _scan_languagetool_rows(
    *,
    file: Path,
    rows: tuple[QAInputRow, ...],
    enabled: bool,
    max_rows: int,
    max_findings: int,
    server_url: str,
    timeout_ms: int,
    picky_mode: bool,
    language: str,
) -> _LTScanResult:
    if not enabled:
        return _LTScanResult(
            findings=(),
            note="LanguageTool disabled in settings.",
            state=QARuleState.SKIPPED,
        )
    if max_findings <= 0:
        return _LTScanResult(
            findings=(),
            note="LanguageTool skipped: QA result limit reached.",
            state=QARuleState.SKIPPED,
        )
    cap = _normalize_languagetool_row_cap(max_rows)
    cap = min(cap, max_findings)
    scanned_rows = rows[:cap]
    findings: list[QAFinding] = []
    fallback_warned = False
    offline_errors = 0
    hard_failures = 0
    capped_by_result_limit = False
    level = LT_LEVEL_PICKY if picky_mode else LT_LEVEL_DEFAULT
    for row in scanned_rows:
        text = str(row.target_text or "").strip()
        if not text:
            continue
        try:
            result = _lt_check_text(
                server_url=server_url,
                language=language,
                text=text,
                level=level,
                timeout_ms=timeout_ms,
            )
        except Exception:
            hard_failures += 1
            continue
        if result.warning:
            fallback_warned = True
        if result.status == LT_STATUS_OFFLINE:
            offline_errors += 1
            continue
        if result.status != LT_STATUS_OK:
            continue
        for match in result.matches:
            if len(findings) >= max_findings:
                capped_by_result_limit = True
                break
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
        if capped_by_result_limit:
            break
    notes: list[str] = []
    if len(rows) > cap:
        notes.append(f"LanguageTool scanned first {cap} row(s) due to cap.")
    if capped_by_result_limit:
        notes.append(
            f"LanguageTool stopped at {max_findings} finding(s) due to QA result limit."
        )
    if fallback_warned:
        notes.append("LanguageTool picky unsupported; default level used.")
    if offline_errors:
        notes.append("LanguageTool offline for one or more rows.")
    if hard_failures:
        notes.append("LanguageTool rule failed for one or more rows.")
    state = QARuleState.DONE
    if hard_failures and not findings and not fallback_warned and not offline_errors:
        state = QARuleState.FAILED
    return _LTScanResult(
        findings=tuple(findings),
        note=" ".join(notes).strip(),
        state=state,
    )


def _run_scan_job(
    win: Any,
    path: Path,
    rows: tuple[QAInputRow, ...],
    run_id: str,
    check_trailing: bool,
    check_newlines: bool,
    check_tokens: bool,
    check_same_as_source: bool,
) -> QAScanJobResult:
    result_limit = _normalize_result_limit(getattr(win, "_qa_panel_result_limit", 500))
    enabled_rules = _enabled_qa_rules(
        check_trailing=check_trailing,
        check_newlines=check_newlines,
        check_tokens=check_tokens,
        check_same_as_source=check_same_as_source,
        check_languagetool=bool(getattr(win, "_qa_check_languagetool", False)),
    )
    records = win._qa_service.build_progress_records(
        run_id=run_id,
        enabled_rules=enabled_rules,
        skip_disabled_rules=True,
        disabled_note="Rule disabled in settings.",
    )
    snapshots: list[QAScanProgressSnapshot] = []
    _append_snapshot(
        win,
        run_id=run_id,
        path=path,
        records=records,
        snapshots=snapshots,
        summary="Running QA checks...",
    )

    findings: list[QAFinding] = []
    notes: list[str] = []

    for rule_id in _STANDARD_QA_RULES:
        if rule_id not in enabled_rules:
            continue
        if len(findings) >= result_limit:
            records = _mark_rule_skipped(
                win,
                records=records,
                run_id=run_id,
                rule_id=rule_id,
                note="Skipped: QA result limit reached.",
                path=path,
                snapshots=snapshots,
            )
            continue
        started = _now_ms()
        records = _transition_rule(
            win,
            records=records,
            run_id=run_id,
            rule_id=rule_id,
            new_state=QARuleState.RUNNING,
            timestamp_ms=started,
        )
        _append_snapshot(
            win,
            run_id=run_id,
            path=path,
            records=records,
            snapshots=snapshots,
            summary="Running QA checks...",
        )
        rule_findings = _scan_standard_rule(win, file=path, rows=rows, rule_id=rule_id)
        slots = max(0, result_limit - len(findings))
        accepted = tuple(rule_findings[:slots])
        findings.extend(accepted)
        end_note = ""
        if len(rule_findings) > slots:
            end_note = "Result cap reached in this rule."
        completed = _now_ms()
        records = _transition_rule(
            win,
            records=records,
            run_id=run_id,
            rule_id=rule_id,
            new_state=QARuleState.DONE,
            timestamp_ms=completed,
            findings_count=len(accepted),
            note=end_note,
        )
        _append_snapshot(
            win,
            run_id=run_id,
            path=path,
            records=records,
            snapshots=snapshots,
            summary="Running QA checks...",
        )

    lt_enabled = "languagetool" in enabled_rules
    if lt_enabled:
        if len(findings) >= result_limit:
            notes.append(
                "LanguageTool skipped: QA result limit reached by standard checks."
            )
            records = _mark_rule_skipped(
                win,
                records=records,
                run_id=run_id,
                rule_id="languagetool",
                note=notes[-1],
                path=path,
                snapshots=snapshots,
            )
        else:
            started = _now_ms()
            records = _transition_rule(
                win,
                records=records,
                run_id=run_id,
                rule_id="languagetool",
                new_state=QARuleState.RUNNING,
                timestamp_ms=started,
            )
            _append_snapshot(
                win,
                run_id=run_id,
                path=path,
                records=records,
                snapshots=snapshots,
                summary="Running QA checks...",
            )
            lt_result = _scan_languagetool_rows(
                file=path,
                rows=rows,
                enabled=True,
                max_rows=int(getattr(win, "_qa_languagetool_max_rows", 500)),
                max_findings=max(0, result_limit - len(findings)),
                server_url=str(getattr(win, "_lt_server_url", "")),
                timeout_ms=int(getattr(win, "_lt_timeout_ms", 1200)),
                picky_mode=bool(getattr(win, "_lt_picky_mode", False)),
                language=str(getattr(win, "_qa_scan_languagetool_language", "en-US")),
            )
            findings.extend(lt_result.findings)
            if lt_result.note:
                notes.append(lt_result.note)
            completed = _now_ms()
            records = _transition_rule(
                win,
                records=records,
                run_id=run_id,
                rule_id="languagetool",
                new_state=lt_result.state,
                timestamp_ms=completed,
                findings_count=len(lt_result.findings),
                note=lt_result.note,
            )
            _append_snapshot(
                win,
                run_id=run_id,
                path=path,
                records=records,
                snapshots=snapshots,
                summary="Running QA checks...",
            )

    done_rules = sum(1 for record in records if record.state == QARuleState.DONE)
    final_summary = (
        "QA completed: "
        f"{len(findings)} finding(s) across {done_rules}/{len(QA_RULE_ORDER)} rules."
    )
    _append_snapshot(
        win,
        run_id=run_id,
        path=path,
        records=records,
        snapshots=snapshots,
        summary=final_summary,
    )
    return QAScanJobResult(
        run_id=run_id,
        path=path,
        findings=tuple(findings),
        note=" ".join(part for part in notes if part).strip(),
        snapshots=tuple(snapshots),
    )


def _set_progress_snapshots(
    win: Any, snapshots: tuple[QAScanProgressSnapshot, ...]
) -> None:
    setter = getattr(win, "_set_qa_progress_snapshots", None)
    if callable(setter):
        setter(snapshots)


def start_scan(win: Any) -> None:
    """Start a background QA scan for the currently opened file."""
    path = win._current_pf.path if win._current_pf is not None else None
    if path is None or win._current_model is None:
        win._set_qa_scan_note("")
        win._set_qa_findings(())
        _set_progress_snapshots(win, ())
        win._set_qa_panel_message("No file selected.")
        return
    if win._qa_scan_future is not None and not win._qa_scan_future.done():
        win._set_qa_panel_message("QA is already running...")
        return
    rows = _collect_input_rows(win)
    run_id = _new_qa_run_id()
    win._qa_scan_run_id = run_id
    win._qa_scan_languagetool_language = win._resolve_lt_language_for_path(path)
    enabled_rules = _enabled_qa_rules(
        check_trailing=bool(win._qa_check_trailing),
        check_newlines=bool(win._qa_check_newlines),
        check_tokens=bool(win._qa_check_escapes),
        check_same_as_source=bool(win._qa_check_same_as_source),
        check_languagetool=bool(getattr(win, "_qa_check_languagetool", False)),
    )
    initial_records = win._qa_service.build_progress_records(
        run_id=run_id,
        enabled_rules=enabled_rules,
        skip_disabled_rules=True,
        disabled_note="Rule disabled in settings.",
    )
    initial_snapshot = win._qa_service.build_progress_snapshot(
        run_id=run_id,
        file_path=path,
        ordered_rules=initial_records,
        final_summary="Running QA checks...",
    )
    _set_progress_snapshots(win, (initial_snapshot,))
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
        run_id,
        bool(win._qa_check_trailing),
        bool(win._qa_check_newlines),
        bool(win._qa_check_escapes),
        bool(win._qa_check_same_as_source),
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
        result = future.result()
    except Exception as exc:
        win._set_qa_scan_note("")
        win._set_qa_panel_message(f"QA failed: {exc}")
        return
    if result.run_id != str(getattr(win, "_qa_scan_run_id", "")):
        return
    if win._current_pf is None or win._current_pf.path != result.path:
        return
    _set_progress_snapshots(win, result.snapshots)
    win._set_qa_scan_note(result.note)
    win._set_qa_findings(result.findings)
    if win._qa_auto_mark_for_review:
        rows_for_auto_mark = tuple(result.findings)
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
