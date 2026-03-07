"""Test module for GUI QA async helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from translationzed_py.core.qa_service import (
    QA_CODE_LANGUAGETOOL,
    QA_CODE_NEWLINES,
    QA_CODE_TOKENS,
    QA_CODE_TRAILING,
    QAFinding,
    QARuleState,
    QAService,
)
from translationzed_py.gui import qa_async


class _Timer:
    """Small timer stub with active/start/stop behavior."""

    def __init__(self, *, active: bool = False) -> None:
        self.active = active
        self.start_calls = 0
        self.stop_calls = 0

    def isActive(self) -> bool:
        """Return whether timer is currently active."""
        return self.active

    def start(self) -> None:
        """Start timer."""
        self.active = True
        self.start_calls += 1

    def stop(self) -> None:
        """Stop timer."""
        self.active = False
        self.stop_calls += 1


class _Future:
    """Future stub with configurable completion and payload."""

    def __init__(
        self,
        *,
        done: bool,
        payload=None,
        error: Exception | None = None,
    ) -> None:
        self._done = done
        self._payload = payload
        self._error = error

    def done(self) -> bool:
        """Return completion status."""
        return self._done

    def result(self):  # type: ignore[no-untyped-def]
        """Return payload or raise configured error."""
        if self._error is not None:
            raise self._error
        return self._payload


class _Pool:
    """Thread pool stub that captures submit arguments."""

    def __init__(self) -> None:
        self.submit_calls: list[tuple[object, tuple[object, ...]]] = []
        self.future = _Future(done=False)

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        """Capture submit payload and return stub future."""
        self.submit_calls.append((fn, args))
        return self.future


def _scan_rule_from_kwargs(kwargs: dict[str, object]) -> str:
    """Return rule id from scan_rows kwargs flags."""
    if bool(kwargs.get("check_trailing")):
        return "trailing"
    if bool(kwargs.get("check_newlines")):
        return "newlines"
    if bool(kwargs.get("check_tokens")):
        return "tokens"
    if bool(kwargs.get("check_same_as_source")):
        return "same_source"
    return "unknown"


class _QaService:
    """QA service stub that records scan requests and delegates progress helpers."""

    def __init__(
        self, *, findings_by_rule: dict[str, tuple[QAFinding, ...]] | None = None
    ):
        self.calls: list[dict[str, object]] = []
        self.findings_by_rule = findings_by_rule or {}
        self._delegate = QAService()

    def scan_rows(self, **kwargs):  # type: ignore[no-untyped-def]
        """Capture call and return configured findings list."""
        self.calls.append(kwargs)
        rule = _scan_rule_from_kwargs(kwargs)
        return list(self.findings_by_rule.get(rule, ()))

    def build_progress_records(self, **kwargs):  # type: ignore[no-untyped-def]
        return self._delegate.build_progress_records(**kwargs)

    def transition_rule_state(self, **kwargs):  # type: ignore[no-untyped-def]
        return self._delegate.transition_rule_state(**kwargs)

    def build_progress_snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
        return self._delegate.build_progress_snapshot(**kwargs)


class _Model:
    """Model stub for iterating search rows."""

    def __init__(self, rows) -> None:  # type: ignore[no-untyped-def]
        self._rows = rows

    def iter_search_rows(self, **_kwargs):  # type: ignore[no-untyped-def]
        """Yield configured rows."""
        return iter(self._rows)


class _Win:
    """Window-like object exposing attributes used by qa_async."""

    def __init__(self) -> None:
        self._current_pf = SimpleNamespace(path=Path("/tmp/project/BE/ui.txt"))
        self._current_model = _Model(
            [
                SimpleNamespace(row=1, source="src", value="dst"),
                SimpleNamespace(row=2, source=None, value=None),
            ]
        )
        self._qa_service = _QaService()
        self._qa_scan_future = None
        self._qa_scan_pool = None
        self._qa_scan_path = None
        self._qa_scan_run_id = ""
        self._qa_scan_timer = _Timer()
        self._qa_check_trailing = True
        self._qa_check_newlines = False
        self._qa_check_escapes = True
        self._qa_check_same_as_source = False
        self._qa_check_languagetool = False
        self._qa_languagetool_max_rows = 500
        self._qa_panel_result_limit = 500
        self._qa_languagetool_automark = False
        self._qa_auto_mark_for_review = False
        self._lt_server_url = "http://127.0.0.1:8081"
        self._lt_timeout_ms = 1200
        self._lt_picky_mode = False
        self._qa_scan_languagetool_language = "en-US"
        self._test_mode = False
        self.messages: list[str] = []
        self.notes: list[str] = []
        self.findings_history: list[tuple[object, ...]] = []
        self.progress_history: list[bool] = []
        self.auto_mark_history: list[tuple[object, ...]] = []
        self.snapshot_history: list[tuple[object, ...]] = []

    def _set_qa_findings(self, findings) -> None:  # type: ignore[no-untyped-def]
        """Capture applied findings."""
        self.findings_history.append(tuple(findings))

    def _set_qa_panel_message(self, message: str) -> None:
        """Capture status messages."""
        self.messages.append(message)

    def _set_qa_scan_note(self, note: str) -> None:
        """Capture scan note updates."""
        self.notes.append(note)

    def _set_qa_progress_visible(self, visible: bool) -> None:
        """Capture progress visibility updates."""
        self.progress_history.append(visible)

    def _set_qa_progress_snapshots(self, snapshots) -> None:  # type: ignore[no-untyped-def]
        """Capture progress snapshots updates."""
        self.snapshot_history.append(tuple(snapshots))

    def _apply_qa_auto_mark(self, findings) -> None:  # type: ignore[no-untyped-def]
        """Capture auto-mark finding set."""
        self.auto_mark_history.append(tuple(findings))

    def _resolve_lt_language_for_path(self, _path: Path) -> str:
        """Resolve LanguageTool language for QA scan stubs."""
        return "en-US"


def _job_result_for(
    path: Path, *, run_id: str, findings: tuple[QAFinding, ...], note: str
):
    """Build QA scan job result with one final snapshot."""
    service = QAService()
    records = service.build_progress_records(
        run_id=run_id,
        enabled_rules=("trailing",),
        skip_disabled_rules=True,
    )
    records = service.transition_rule_state(
        records=records,
        run_id=run_id,
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=1,
    )
    records = service.transition_rule_state(
        records=records,
        run_id=run_id,
        rule_id="trailing",
        new_state=QARuleState.DONE,
        timestamp_ms=2,
        findings_count=len(findings),
    )
    snapshot = service.build_progress_snapshot(
        run_id=run_id,
        file_path=path,
        ordered_rules=records,
        final_summary="summary",
    )
    return qa_async.QAScanJobResult(
        run_id=run_id,
        path=path,
        findings=findings,
        note=note,
        snapshots=(snapshot,),
    )


def test_collect_input_rows_returns_empty_without_model() -> None:
    """Verify row collector returns empty tuple when model is missing."""
    win = _Win()
    win._current_model = None
    assert qa_async._collect_input_rows(win) == ()


def test_run_scan_job_returns_progress_snapshots_and_rule_findings() -> None:
    """Verify run-scan payload includes snapshots and per-rule findings."""
    file_path = Path("/tmp/project/BE/ui.txt")
    trailing = QAFinding(file=file_path, row=1, code=QA_CODE_TRAILING, excerpt="t")
    tokens = QAFinding(file=file_path, row=2, code=QA_CODE_TOKENS, excerpt="k")
    win = _Win()
    win._qa_service = _QaService(
        findings_by_rule={
            "trailing": (trailing,),
            "tokens": (tokens,),
        }
    )
    rows = qa_async._collect_input_rows(win)
    result = qa_async._run_scan_job(
        win,
        file_path,
        rows,
        "run-1",
        True,
        False,
        True,
        False,
    )
    assert result.path == file_path
    assert result.run_id == "run-1"
    assert result.findings == (trailing, tokens)
    assert result.note == ""
    assert result.snapshots
    assert result.snapshots[-1].run_id == "run-1"
    assert len(win._qa_service.calls) == 2
    assert _scan_rule_from_kwargs(win._qa_service.calls[0]) == "trailing"
    assert _scan_rule_from_kwargs(win._qa_service.calls[1]) == "tokens"


def test_start_scan_sets_no_file_message_without_path_or_model() -> None:
    """Verify scan start exits with no-file message when inputs are missing."""
    win = _Win()
    win._current_pf = None
    qa_async.start_scan(win)
    assert win.findings_history == [()]
    assert win.notes[-1] == ""
    assert win.messages[-1] == "No file selected."
    assert win.snapshot_history[-1] == ()

    win = _Win()
    win._current_model = None
    qa_async.start_scan(win)
    assert win.findings_history == [()]
    assert win.notes[-1] == ""
    assert win.messages[-1] == "No file selected."
    assert win.snapshot_history[-1] == ()


def test_start_scan_reports_already_running_when_future_pending() -> None:
    """Verify scan start warns when an active scan future is still running."""
    win = _Win()
    win._qa_scan_future = _Future(done=False)
    qa_async.start_scan(win)
    assert win.messages[-1] == "QA is already running..."


def test_start_scan_submits_job_and_respects_timer_activity(monkeypatch) -> None:
    """Verify scan start creates pool, submits job, and starts timer when needed."""
    created_pools: list[_Pool] = []

    def _make_pool(**_kwargs):  # type: ignore[no-untyped-def]
        pool = _Pool()
        created_pools.append(pool)
        return pool

    monkeypatch.setattr("translationzed_py.gui.qa_async.ThreadPoolExecutor", _make_pool)

    win = _Win()
    qa_async.start_scan(win)

    assert created_pools
    assert win._qa_scan_pool is created_pools[0]
    assert win._qa_scan_future is created_pools[0].future
    assert win._qa_scan_path == win._current_pf.path
    assert win._qa_scan_run_id.startswith("qa-")
    assert win.notes[-1] == ""
    assert win._qa_scan_languagetool_language == "en-US"
    assert win.progress_history == [True]
    assert win.messages[-1] == "Running QA checks..."
    assert win._qa_scan_timer.start_calls == 1
    assert win.snapshot_history

    fn, args = created_pools[0].submit_calls[0]
    assert fn is qa_async._run_scan_job
    assert args[3] == win._qa_scan_run_id

    win._qa_scan_future = None
    win._qa_scan_timer = _Timer(active=True)
    qa_async.start_scan(win)
    assert win._qa_scan_timer.start_calls == 0


def test_poll_scan_handles_future_none_pending_and_exception() -> None:
    """Verify poll flow handles absent future, pending state, and raised errors."""
    win = _Win()
    qa_async.poll_scan(win)
    assert win._qa_scan_timer.stop_calls == 1
    assert win.progress_history == [False]

    win = _Win()
    win._qa_scan_future = _Future(done=False)
    qa_async.poll_scan(win)
    assert win._qa_scan_timer.stop_calls == 0
    assert win.progress_history == []

    win = _Win()
    win._qa_scan_future = _Future(done=True, error=RuntimeError("boom"))
    qa_async.poll_scan(win)
    assert win._qa_scan_future is None
    assert win.notes[-1] == ""
    assert win.messages[-1] == "QA failed: boom"
    assert win.progress_history == [False]


def test_poll_scan_ignores_stale_result_and_applies_current_result() -> None:
    """Verify poll ignores stale path/run_id and applies current-file matching result."""
    stale_win = _Win()
    stale_win._qa_scan_run_id = "run-live"
    stale_path = Path("/tmp/project/RU/ui.txt")
    stale_finding = QAFinding(
        file=stale_path,
        row=3,
        code=QA_CODE_NEWLINES,
        excerpt="bad",
    )
    stale_win._qa_scan_future = _Future(
        done=True,
        payload=_job_result_for(
            stale_path,
            run_id="run-old",
            findings=(stale_finding,),
            note="stale note",
        ),
    )
    qa_async.poll_scan(stale_win)
    assert stale_win.findings_history == []
    assert stale_win.auto_mark_history == []

    win = _Win()
    win._qa_auto_mark_for_review = True
    win._qa_scan_run_id = "run-live"
    path = win._current_pf.path
    finding = QAFinding(file=path, row=4, code=QA_CODE_TRAILING, excerpt="trim")
    win._qa_scan_future = _Future(
        done=True,
        payload=_job_result_for(
            path,
            run_id="run-live",
            findings=(finding,),
            note="LanguageTool scanned first 10 row(s) due to cap.",
        ),
    )
    qa_async.poll_scan(win)
    assert win.notes[-1].startswith("LanguageTool scanned first")
    assert win.findings_history == [(finding,)]
    assert win.auto_mark_history == [(finding,)]
    assert win.snapshot_history[-1]


def test_run_scan_job_skips_languagetool_when_disabled(monkeypatch) -> None:
    """Verify LT checks are skipped entirely when QA LT toggle is disabled."""
    win = _Win()

    def _unexpected_lt_call(**_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LanguageTool should not be called")

    monkeypatch.setattr(qa_async, "_lt_check_text", _unexpected_lt_call)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        qa_async._collect_input_rows(win),
        "run-1",
        True,
        True,
        True,
        True,
    )
    assert result.path == win._current_pf.path
    assert result.note == ""
    assert all(finding.code != QA_CODE_LANGUAGETOOL for finding in result.findings)
    lt_record = next(
        record
        for record in result.snapshots[-1].ordered_rules
        if record.rule_id == "languagetool"
    )
    assert lt_record.state == QARuleState.SKIPPED
    assert lt_record.note == "Rule disabled in settings."


def test_run_scan_job_includes_languagetool_findings_when_enabled(monkeypatch) -> None:
    """Verify QA scan includes LT findings when QA LT is enabled."""
    win = _Win()
    win._qa_check_languagetool = True

    def _fake_lt_check_text(**_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            status="ok",
            matches=[SimpleNamespace(message="LT issue")],
            warning="",
        )

    monkeypatch.setattr(qa_async, "_lt_check_text", _fake_lt_check_text)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        qa_async._collect_input_rows(win),
        "run-1",
        False,
        False,
        False,
        False,
    )
    assert result.note == ""
    assert any(finding.code == QA_CODE_LANGUAGETOOL for finding in result.findings)
    lt_record = next(
        record
        for record in result.snapshots[-1].ordered_rules
        if record.rule_id == "languagetool"
    )
    assert lt_record.state == QARuleState.DONE


def test_run_scan_job_reports_languagetool_row_cap_note(monkeypatch) -> None:
    """Verify LT QA scan reports cap note when rows are truncated."""
    win = _Win()
    win._qa_check_languagetool = True
    win._qa_languagetool_max_rows = 1

    def _fake_lt_check_text(**_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            status="ok",
            matches=[],
            warning="",
        )

    monkeypatch.setattr(qa_async, "_lt_check_text", _fake_lt_check_text)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        qa_async._collect_input_rows(win),
        "run-1",
        False,
        False,
        False,
        False,
    )
    assert result.note == "LanguageTool scanned first 1 row(s) due to cap."


def test_run_scan_job_skips_languagetool_when_standard_limit_is_full(
    monkeypatch,
) -> None:
    """Verify LT stage is skipped when standard findings already fill panel cap."""
    win = _Win()
    win._qa_panel_result_limit = 1
    win._qa_check_languagetool = True
    win._qa_service = _QaService(
        findings_by_rule={
            "trailing": (
                QAFinding(
                    file=win._current_pf.path,
                    row=1,
                    code=QA_CODE_TRAILING,
                    excerpt="base",
                ),
            )
        }
    )

    def _unexpected_lt_call(**_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LanguageTool should not run when no panel slots remain")

    monkeypatch.setattr(qa_async, "_lt_check_text", _unexpected_lt_call)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        qa_async._collect_input_rows(win),
        "run-1",
        True,
        False,
        False,
        False,
    )
    assert len(result.findings) == 1
    assert result.findings[0].code == QA_CODE_TRAILING
    assert (
        result.note
        == "LanguageTool skipped: QA result limit reached by standard checks."
    )


def test_run_scan_job_stops_languagetool_when_result_limit_reached(monkeypatch) -> None:
    """Verify LT stage stops early once remaining QA result slots are exhausted."""
    win = _Win()
    win._qa_check_languagetool = True
    win._qa_panel_result_limit = 2
    win._qa_service = _QaService(
        findings_by_rule={
            "trailing": (
                QAFinding(
                    file=win._current_pf.path,
                    row=0,
                    code=QA_CODE_TRAILING,
                    excerpt="base",
                ),
            )
        }
    )
    rows = (
        qa_async.QAInputRow(row=1, source_text="src", target_text="dst"),
        qa_async.QAInputRow(row=2, source_text="src2", target_text="dst2"),
    )
    calls = {"count": 0}

    def _fake_lt_check_text(**_kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return SimpleNamespace(
            status="ok",
            matches=[SimpleNamespace(message="A"), SimpleNamespace(message="B")],
            warning="",
        )

    monkeypatch.setattr(qa_async, "_lt_check_text", _fake_lt_check_text)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        rows,
        "run-1",
        True,
        False,
        False,
        False,
    )
    assert calls["count"] == 1
    assert len(result.findings) == 2
    assert [f.code for f in result.findings] == [QA_CODE_TRAILING, QA_CODE_LANGUAGETOOL]
    assert "LanguageTool scanned first 1 row(s) due to cap." in result.note
    assert "LanguageTool stopped at 1 finding(s) due to QA result limit." in result.note


def test_run_scan_job_languagetool_exceptions_do_not_fail_whole_scan(
    monkeypatch,
) -> None:
    """Verify LT exceptions are isolated to LT rule and do not abort full scan."""
    win = _Win()
    win._qa_check_languagetool = True
    win._qa_service = _QaService(
        findings_by_rule={
            "trailing": (
                QAFinding(
                    file=win._current_pf.path,
                    row=0,
                    code=QA_CODE_TRAILING,
                    excerpt="base",
                ),
            )
        }
    )

    def _lt_raises(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("lt unavailable")

    monkeypatch.setattr(qa_async, "_lt_check_text", _lt_raises)
    result = qa_async._run_scan_job(
        win,
        win._current_pf.path,
        qa_async._collect_input_rows(win),
        "run-1",
        True,
        False,
        False,
        False,
    )
    assert result.findings[0].code == QA_CODE_TRAILING
    assert "LanguageTool rule failed for one or more rows." in result.note
    lt_record = next(
        record
        for record in result.snapshots[-1].ordered_rules
        if record.rule_id == "languagetool"
    )
    assert lt_record.state == QARuleState.FAILED


def test_poll_scan_filters_languagetool_auto_mark_by_toggle() -> None:
    """Verify LT findings are auto-marked only when LT auto-mark toggle is enabled."""
    win = _Win()
    win._qa_auto_mark_for_review = True
    win._qa_scan_run_id = "run-1"
    path = win._current_pf.path
    lt_finding = QAFinding(
        file=path,
        row=1,
        code=QA_CODE_LANGUAGETOOL,
        excerpt="lt",
    )
    base_finding = QAFinding(
        file=path,
        row=2,
        code=QA_CODE_TRAILING,
        excerpt="base",
    )
    win._qa_languagetool_automark = False
    win._qa_scan_future = _Future(
        done=True,
        payload=_job_result_for(
            path,
            run_id="run-1",
            findings=(lt_finding, base_finding),
            note="",
        ),
    )
    qa_async.poll_scan(win)
    assert win.auto_mark_history[-1] == (base_finding,)

    win._qa_languagetool_automark = True
    win._qa_scan_run_id = "run-2"
    win._qa_scan_future = _Future(
        done=True,
        payload=_job_result_for(
            path,
            run_id="run-2",
            findings=(lt_finding, base_finding),
            note="",
        ),
    )
    qa_async.poll_scan(win)
    assert win.auto_mark_history[-1] == (lt_finding, base_finding)


def test_refresh_sync_for_test_polls_until_future_completes(monkeypatch) -> None:
    """Verify sync refresh polls repeatedly only when running in test mode."""
    calls: list[str] = []

    def _fake_start_scan(win) -> None:  # type: ignore[no-untyped-def]
        calls.append("start")
        win._qa_scan_future = _Future(done=False)

    def _fake_poll(win) -> None:  # type: ignore[no-untyped-def]
        calls.append("poll")
        win._qa_scan_future = None

    monkeypatch.setattr(qa_async, "start_scan", _fake_start_scan)
    monkeypatch.setattr(qa_async, "poll_scan", _fake_poll)

    win = _Win()
    win._test_mode = False
    qa_async.refresh_sync_for_test(win)
    assert calls == ["start"]

    calls.clear()
    win._test_mode = True
    qa_async.refresh_sync_for_test(win)
    assert calls == ["start", "poll"]
