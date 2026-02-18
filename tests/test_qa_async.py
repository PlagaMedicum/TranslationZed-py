"""Test module for GUI QA async helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from translationzed_py.core.qa_service import QAFinding
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


class _QaService:
    """QA service stub that records scan requests."""

    def __init__(self, *, findings: tuple[QAFinding, ...] = ()) -> None:
        self.calls: list[dict[str, object]] = []
        self.findings = findings

    def scan_rows(self, **kwargs):  # type: ignore[no-untyped-def]
        """Capture call and return configured findings list."""
        self.calls.append(kwargs)
        return list(self.findings)


class _Model:
    """Model stub for iterating search rows."""

    def __init__(self, rows) -> None:  # type: ignore[no-untyped-def]
        self._rows = rows

    def iter_search_rows(self, **_kwargs):  # type: ignore[no-untyped-def]
        """Yield configured rows."""
        return iter(self._rows)


class _Win:
    """Window-like object exposing the attributes used by qa_async."""

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
        self._qa_scan_timer = _Timer()
        self._qa_check_trailing = True
        self._qa_check_newlines = False
        self._qa_check_escapes = True
        self._qa_check_same_as_source = False
        self._qa_auto_mark_for_review = False
        self._test_mode = False
        self.messages: list[str] = []
        self.findings_history: list[tuple[object, ...]] = []
        self.progress_history: list[bool] = []
        self.auto_mark_history: list[tuple[object, ...]] = []

    def _set_qa_findings(self, findings) -> None:  # type: ignore[no-untyped-def]
        """Capture applied findings."""
        self.findings_history.append(tuple(findings))

    def _set_qa_panel_message(self, message: str) -> None:
        """Capture status messages."""
        self.messages.append(message)

    def _set_qa_progress_visible(self, visible: bool) -> None:
        """Capture progress visibility updates."""
        self.progress_history.append(visible)

    def _apply_qa_auto_mark(self, findings) -> None:  # type: ignore[no-untyped-def]
        """Capture auto-mark finding set."""
        self.auto_mark_history.append(tuple(findings))


def test_collect_input_rows_returns_empty_without_model() -> None:
    """Verify row collector returns empty tuple when model is missing."""
    win = _Win()
    win._current_model = None
    assert qa_async._collect_input_rows(win) == ()


def test_run_scan_job_delegates_to_qa_service() -> None:
    """Verify scan job forwards all QA options and returns path/findings."""
    file_path = Path("/tmp/project/BE/ui.txt")
    finding = QAFinding(file=file_path, row=1, code="qa.tokens", excerpt="x")
    win = _Win()
    win._qa_service = _QaService(findings=(finding,))
    rows = qa_async._collect_input_rows(win)

    path, findings = qa_async._run_scan_job(
        win,
        file_path,
        rows,
        True,
        False,
        True,
        False,
    )

    assert path == file_path
    assert findings == [finding]
    assert win._qa_service.calls
    assert win._qa_service.calls[0]["rows"] == rows


def test_start_scan_sets_no_file_message_without_path_or_model() -> None:
    """Verify scan start exits with no-file message when inputs are missing."""
    win = _Win()
    win._current_pf = None
    qa_async.start_scan(win)
    assert win.findings_history == [()]
    assert win.messages[-1] == "No file selected."

    win = _Win()
    win._current_model = None
    qa_async.start_scan(win)
    assert win.findings_history == [()]
    assert win.messages[-1] == "No file selected."


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
    assert win.progress_history == [True]
    assert win.messages[-1] == "Running QA checks..."
    assert win._qa_scan_timer.start_calls == 1

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
    assert win.messages[-1] == "QA failed: boom"
    assert win.progress_history == [False]


def test_poll_scan_ignores_stale_result_and_applies_current_result() -> None:
    """Verify poll ignores stale path results and applies current-file findings."""
    stale_win = _Win()
    stale_path = Path("/tmp/project/RU/ui.txt")
    stale_finding = QAFinding(file=stale_path, row=3, code="qa.newlines", excerpt="bad")
    stale_win._qa_scan_future = _Future(
        done=True, payload=(stale_path, [stale_finding])
    )
    qa_async.poll_scan(stale_win)
    assert stale_win.findings_history == []
    assert stale_win.auto_mark_history == []

    win = _Win()
    win._qa_auto_mark_for_review = True
    path = win._current_pf.path
    finding = QAFinding(file=path, row=4, code="qa.trailing", excerpt="trim")
    win._qa_scan_future = _Future(done=True, payload=(path, [finding]))
    qa_async.poll_scan(win)
    assert win.findings_history == [(finding,)]
    assert win.auto_mark_history == [(finding,)]


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
