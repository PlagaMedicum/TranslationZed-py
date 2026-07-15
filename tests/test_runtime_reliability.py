"""Tests for GUI exception containment and one-writer project sessions."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import runtime_reliability as reliability
from translationzed_py.gui.main_window import MainWindow


def _project(root: Path) -> Path:
    for locale in ("EN", "BE"):
        path = root / locale
        path.mkdir(parents=True)
        (path / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (path / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    return root


def test_project_session_lock_blocks_concurrent_writer_and_releases(
    qapp, tmp_path: Path
) -> None:
    """Only one process may own a project's draft/session persistence at a time."""
    root = tmp_path / "project"
    root.mkdir()

    first = reliability.acquire_project_session_lock(
        root=root,
        cache_dir=".tzp/cache",
    )
    assert first.acquired is True
    assert first.previous_session_unclean is False

    second = reliability.acquire_project_session_lock(
        root=root,
        cache_dir=".tzp/cache",
    )
    assert second.acquired is False
    assert second.error_title == "Project already open"

    owner = SimpleNamespace(_project_session_lock=first.lock)
    reliability.release_project_session_lock(owner)
    third = reliability.acquire_project_session_lock(
        root=root,
        cache_dir=".tzp/cache",
    )
    assert third.acquired is True
    assert third.previous_session_unclean is False
    assert third.lock is not None
    third.lock.unlock()


def test_project_session_lock_marks_replaced_stale_marker_as_unclean(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    """A lock marker present before successful acquisition activates recovery."""
    root = tmp_path / "project"
    lock_path = root / ".tzp" / "cache" / reliability.SESSION_LOCK_FILENAME
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("stale", encoding="utf-8")

    class _FakeLock:
        def __init__(self, path: str) -> None:
            self.path = path
            self.stale_ms = -1

        def setStaleLockTime(self, value: int) -> None:  # noqa: N802
            self.stale_ms = value

        def tryLock(self, _timeout: int) -> bool:  # noqa: N802
            return True

    monkeypatch.setattr(reliability, "QLockFile", _FakeLock)

    result = reliability.acquire_project_session_lock(
        root=root,
        cache_dir=".tzp/cache",
    )

    assert result.acquired is True
    assert result.previous_session_unclean is True
    assert result.lock is not None
    assert result.lock.stale_ms == 0


def test_project_session_lock_reports_directory_and_lock_failures(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    """Lock setup failures stop opening with an actionable, non-crashing error."""

    def _deny_directory(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read-only cache")

    monkeypatch.setattr(Path, "mkdir", _deny_directory)
    directory_failure = reliability.acquire_project_session_lock(
        root=tmp_path,
        cache_dir=".tzp/cache",
    )
    assert directory_failure.acquired is False
    assert "concurrent draft writes" in directory_failure.error_message

    monkeypatch.undo()

    class _BrokenLock:
        def __init__(self, _path: str) -> None:
            pass

        def setStaleLockTime(self, _value: int) -> None:  # noqa: N802
            pass

        def tryLock(self, _timeout: int) -> bool:  # noqa: N802
            raise RuntimeError("lock backend failed")

    monkeypatch.setattr(reliability, "QLockFile", _BrokenLock)
    acquisition_failure = reliability.acquire_project_session_lock(
        root=tmp_path,
        cache_dir=".tzp/cache",
    )
    assert acquisition_failure.acquired is False
    assert "lock backend failed" in acquisition_failure.error_message


def test_exception_boundary_logs_and_opens_copyable_report(qapp, monkeypatch) -> None:
    """Uncaught Python GUI errors are contained and routed to one report dialog."""
    shown: list[tuple[object, object]] = []
    parent = object()
    boundary = reliability.GuiExceptionBoundary(log_path=None)
    boundary.set_parent(parent)  # type: ignore[arg-type]
    monkeypatch.setattr(
        reliability,
        "show_issue_report",
        lambda report_parent, *, exc_info, log_path: shown.append(
            (report_parent, exc_info)
        ),
    )

    original = sys.excepthook
    boundary.install()
    try:
        error = RuntimeError("contained")
        sys.excepthook(RuntimeError, error, error.__traceback__)
    finally:
        boundary.restore()

    assert sys.excepthook is original
    assert shown and shown[0][0] is parent
    assert shown[0][1][1].args == ("contained",)


def test_log_exception_uses_valid_logger_arguments(monkeypatch) -> None:
    """Caught failures retain context without causing a logging-format error."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    logger = SimpleNamespace(
        error=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(reliability, "get_logger", lambda: logger)
    error = RuntimeError("parse failed")

    reliability.log_exception("Parse error", error)

    args, kwargs = calls[0]
    assert args[0] % args[1:] == "Parse error: parse failed"
    assert kwargs["exc_info"] == (RuntimeError, error, None)


def test_exception_boundary_falls_back_if_report_rendering_fails(
    qapp, monkeypatch
) -> None:
    """A diagnostics-dialog failure is delegated without recursive error handling."""
    delegated: list[tuple[type[BaseException], BaseException]] = []
    boundary = reliability.GuiExceptionBoundary(log_path=None)
    boundary._previous_hook = (  # noqa: SLF001 - verify the process fallback contract
        lambda exc_type, exc, _tb: delegated.append((exc_type, exc))
    )

    def _fail_report(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("dialog failed")

    monkeypatch.setattr(reliability, "show_issue_report", _fail_report)

    error = ValueError("original failure")
    boundary.handle(ValueError, error, None)
    interrupt = KeyboardInterrupt()
    boundary.handle(KeyboardInterrupt, interrupt, None)

    assert delegated == [(ValueError, error), (KeyboardInterrupt, interrupt)]
    assert boundary._handling is False  # noqa: SLF001


def test_startup_exception_boundary_contains_and_reports(qapp, monkeypatch) -> None:
    """Python startup failures use the same report path and restore the hook."""
    shown: list[BaseException] = []
    monkeypatch.setattr(
        reliability,
        "show_issue_report",
        lambda _parent, *, exc_info, log_path: shown.append(exc_info[1]),
    )
    original = sys.excepthook

    with reliability.gui_exception_boundary(log_path=None):
        raise RuntimeError("startup failed")

    assert [str(exc) for exc in shown] == ["startup failed"]
    assert sys.excepthook is original


def test_issue_report_dialog_copies_normal_and_exception_reports(
    qapp, monkeypatch
) -> None:
    """The support report remains selectable and copyable in both entry paths."""
    titles: list[str] = []
    monkeypatch.setattr(
        reliability,
        "build_runtime_issue_report",
        lambda *_args, **_kwargs: "copyable report",
    )

    def _exec(dialog):  # type: ignore[no-untyped-def]
        titles.append(dialog.windowTitle())
        editor = dialog.findChild(reliability.QPlainTextEdit)
        buttons = dialog.findChild(reliability.QDialogButtonBox)
        assert editor is not None
        assert buttons is not None
        copy_button = next(
            button for button in buttons.buttons() if button.text() == "Copy report"
        )
        copy_button.click()
        return 0

    monkeypatch.setattr(reliability.QDialog, "exec", _exec)

    reliability.show_issue_report(None)
    error = RuntimeError("contained")
    reliability.show_issue_report(None, exc_info=(RuntimeError, error, None))

    assert titles == ["TranslationZed-Py issue report", "Unexpected error"]
    assert qapp.clipboard().text() == "copyable report"


def test_help_menu_exposes_copyable_issue_report(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Keep support diagnostics discoverable in the existing Help menu."""
    win = MainWindow(str(_project(tmp_path / "project")), selected_locales=["BE"])
    qtbot.addWidget(win)
    shown: list[object] = []
    monkeypatch.setattr(
        reliability,
        "show_issue_report",
        lambda parent: shown.append(parent),
    )
    action = next(
        item for item in win.menu_help.actions() if "Issue Report" in item.text()
    )

    action.trigger()

    assert shown == [win]
