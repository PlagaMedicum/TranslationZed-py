"""Test module for GUI app singleton and launch helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import app as gui_app
from translationzed_py.gui import launch


def test_get_app_uses_existing_qapplication_instance(qapp, monkeypatch) -> None:
    """Verify app singleton binds to an existing QApplication instance."""
    monkeypatch.setattr(gui_app, "_APP", None)
    assert gui_app.get_app() is qapp
    assert gui_app.get_app() is qapp


def test_launch_exits_early_when_startup_aborted(monkeypatch) -> None:
    """Verify launch returns without showing/executing when startup aborts."""
    calls: dict[str, int] = {"show": 0, "exec": 0}

    class _FakeApp:
        """Application stub recording exec calls."""

        def exec(self) -> int:
            """Capture exec invocation."""
            calls["exec"] += 1
            return 0

    class _FakeWindow:
        """Window stub that reports startup aborted."""

        def __init__(self, project_root):  # type: ignore[no-untyped-def]
            self.project_root = project_root
            self._startup_aborted = True

        def show(self) -> None:
            """Capture show invocation."""
            calls["show"] += 1

    monkeypatch.setattr("translationzed_py.gui.get_app", lambda: _FakeApp())
    monkeypatch.setattr("translationzed_py.gui.MainWindow", _FakeWindow)

    launch("root/path")
    assert calls == {"show": 0, "exec": 0}


def test_launch_runs_window_and_schedules_smoke_timeout(monkeypatch) -> None:
    """Verify launch shows window, executes app, and configures smoke timeout."""
    calls: dict[str, object] = {"show": 0, "exec": 0, "single_shot": None}

    class _FakeApp:
        """Application stub recording quit/exec calls."""

        def __init__(self) -> None:
            self.quit_calls = 0

        def exec(self) -> int:
            """Capture exec call."""
            calls["exec"] = int(calls["exec"]) + 1
            return 0

        def quit(self) -> None:
            """Capture quit callback execution."""
            self.quit_calls += 1

    class _FakeWindow:
        """Window stub recording show calls."""

        def __init__(self, project_root):  # type: ignore[no-untyped-def]
            self.project_root = project_root
            self._startup_aborted = False

        def show(self) -> None:
            """Capture window show call."""
            calls["show"] = int(calls["show"]) + 1

    app = _FakeApp()

    def _single_shot(timeout_ms: int, callback) -> None:  # type: ignore[no-untyped-def]
        calls["single_shot"] = (timeout_ms, callback)

    monkeypatch.setattr("translationzed_py.gui.get_app", lambda: app)
    monkeypatch.setattr("translationzed_py.gui.MainWindow", _FakeWindow)
    monkeypatch.setattr("translationzed_py.gui.QTimer.singleShot", _single_shot)
    monkeypatch.setenv("TZP_SMOKE", "1")
    monkeypatch.setenv("TZP_SMOKE_TIMEOUT_MS", "100")

    launch("root/path")

    assert calls["show"] == 1
    assert calls["exec"] == 1
    assert calls["single_shot"] is not None
    timeout_ms, callback = calls["single_shot"]
    assert timeout_ms == 250
    assert callback == app.quit
