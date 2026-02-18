"""Test module for main-window TM diagnostics, rebuild polling, and preferences flow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core.tm_rebuild import TMRebuildResult
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create EN/BE project fixture for main-window tests."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (("EN", "English"), ("BE", "Belarusian")):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Добра"\n', encoding="utf-8")
    return root


class _Future:
    """Small future stub with configurable done/result/exception behavior."""

    def __init__(self, *, done: bool, result=None, error: Exception | None = None) -> None:
        self._done = done
        self._result = result
        self._error = error

    def done(self) -> bool:
        """Return done status."""
        return self._done

    def result(self):  # type: ignore[no-untyped-def]
        """Return payload or raise configured error."""
        if self._error is not None:
            raise self._error
        return self._result


class _MessageBox:
    """QMessageBox stub used for warning/information assertions."""

    _warnings: list[tuple[str, str]] = []
    _infos: list[tuple[str, str]] = []

    @staticmethod
    def warning(_parent, title: str, text: str) -> int:
        _MessageBox._warnings.append((title, text))
        return 0

    @staticmethod
    def information(_parent, title: str, text: str) -> int:
        _MessageBox._infos.append((title, text))
        return 0


def test_tm_diagnostics_and_bootstrap_guards_cover_early_return_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify diagnostics and bootstrap helpers cover guard branches and success path."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _MessageBox)
    _MessageBox._warnings.clear()

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._show_tm_diagnostics()
    assert ("TM unavailable", "TM store is not available.") in _MessageBox._warnings

    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    win._tm_store = object()  # type: ignore[assignment]
    win._tm_workflow = type(
        "_Workflow",
        (),
        {
            "diagnostics_report_for_store": staticmethod(
                lambda **_kwargs: "diagnostics text"
            )
        },
    )()
    monkeypatch.setattr(
        win,
        "_show_copyable_report",
        lambda title, text: calls.append((title, text)),
    )
    monkeypatch.setattr(win, "_tm_query_policy", lambda: object())
    monkeypatch.setattr(win, "_current_tm_lookup", lambda: ("HELLO", "value"))
    win._show_tm_diagnostics()
    assert calls == [("TM diagnostics", "diagnostics text")]

    start_calls: list[tuple[list[str], bool, bool]] = []
    monkeypatch.setattr(
        win,
        "_start_tm_rebuild",
        lambda locales, interactive, force: start_calls.append(
            (list(locales), bool(interactive), bool(force))
        ),
    )
    win._test_mode = True
    win._maybe_bootstrap_tm()
    win._test_mode = False
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._maybe_bootstrap_tm()
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    win._selected_locales = []
    win._maybe_bootstrap_tm()
    win._selected_locales = ["EN"]
    win._maybe_bootstrap_tm()
    win._selected_locales = ["EN", "BE"]
    win._maybe_bootstrap_tm()
    assert start_calls == [(["BE"], False, False)]


def test_start_and_poll_tm_rebuild_cover_running_failure_and_success_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM rebuild start/poll handles running, failure, and success branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _MessageBox)
    _MessageBox._infos.clear()
    _MessageBox._warnings.clear()

    shown: list[tuple[str, int]] = []
    monkeypatch.setattr(win.statusBar(), "showMessage", lambda text, ms=0: shown.append((text, ms)))

    win._tm_store = None
    win._start_tm_rebuild(["BE"], interactive=True, force=False)

    win._tm_store = object()  # type: ignore[assignment]
    win._tm_rebuild_future = _Future(done=False)
    win._start_tm_rebuild(["BE"], interactive=True, force=False)
    assert shown[-1] == ("TM rebuild already running.", 3000)

    class _Spec:
        locale = "BE"

    win._tm_rebuild_future = None
    win._tm_workflow = type(
        "_Workflow",
        (),
        {
            "collect_rebuild_locales": staticmethod(lambda **_kwargs: ([], "utf-8")),
            "rebuild_project_tm": staticmethod(lambda *_args, **_kwargs: None),
            "clear_cache": staticmethod(lambda: None),
            "format_rebuild_status": staticmethod(lambda _result: "rebuilt"),
        },
    )()
    win._start_tm_rebuild(["BE"], interactive=True, force=False)
    assert ("TM rebuild", "No TM entries found.") in _MessageBox._infos

    submitted: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    class _Pool:
        def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
            submitted.append((fn, args, kwargs))
            return _Future(done=False)

    win._tm_workflow = type(
        "_Workflow",
        (),
        {
            "collect_rebuild_locales": staticmethod(lambda **_kwargs: ([_Spec()], "utf-8")),
            "rebuild_project_tm": staticmethod(lambda *_args, **_kwargs: None),
            "clear_cache": staticmethod(lambda: shown.append(("clear", 0))),
            "format_rebuild_status": staticmethod(lambda _result: "rebuilt"),
        },
    )()
    win._tm_rebuild_pool = _Pool()  # type: ignore[assignment]
    win._tm_rebuild_timer.stop()
    win._start_tm_rebuild(["BE"], interactive=False, force=False)
    assert submitted
    assert win._tm_rebuild_timer.isActive() is True

    progress: list[bool] = []
    monkeypatch.setattr(win, "_set_tm_progress_visible", lambda visible: progress.append(bool(visible)))
    win._tm_rebuild_future = None
    win._tm_query_future = None
    win._poll_tm_rebuild()
    assert progress[-1] is False

    win._tm_rebuild_future = _Future(done=False)
    win._poll_tm_rebuild()

    win._tm_rebuild_interactive = True
    win._tm_rebuild_future = _Future(done=True, error=RuntimeError("boom"))
    win._poll_tm_rebuild()
    assert any(title == "TM rebuild failed" for title, _ in _MessageBox._warnings)

    finished: list[TMRebuildResult] = []
    monkeypatch.setattr(win, "_finish_tm_rebuild", lambda result: finished.append(result))
    result = TMRebuildResult(files=1, entries=2)
    win._tm_rebuild_future = _Future(done=True, result=result)
    win._poll_tm_rebuild()
    assert finished == [result]


def test_finish_rebuild_open_preferences_show_about_and_theme_reactivity(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify rebuild completion, preferences dialog flow, about dialog, and theme sync."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    status_msgs: list[tuple[str, int]] = []
    monkeypatch.setattr(win.statusBar(), "showMessage", lambda text, ms=0: status_msgs.append((text, ms)))

    updates: list[str] = []
    win._tm_workflow = type(
        "_Workflow",
        (),
        {
            "clear_cache": staticmethod(lambda: updates.append("clear")),
            "format_rebuild_status": staticmethod(lambda _result: "done"),
        },
    )()
    win._left_stack.setCurrentIndex(1)
    monkeypatch.setattr(win, "_update_tm_suggestions", lambda: updates.append("suggest"))
    win._finish_tm_rebuild(TMRebuildResult(files=2, entries=3))
    assert updates == ["clear", "suggest"]
    assert status_msgs[-1] == ("done", 8000)

    applied: list[dict[str, object]] = []

    class _PrefsDialogReject:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(mw, "PreferencesDialog", _PrefsDialogReject)
    monkeypatch.setattr(win, "_apply_preferences", lambda values: applied.append(dict(values)))
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    win._tm_store = type("_Store", (), {"list_import_files": staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("nope")))})()
    win._open_preferences()
    assert applied == []

    class _PrefsDialogAccept(_PrefsDialogReject):
        def exec(self) -> int:
            return self.DialogCode.Accepted

        def values(self) -> dict[str, object]:
            return {"wrap_text": True}

    monkeypatch.setattr(mw, "PreferencesDialog", _PrefsDialogAccept)
    win._open_preferences()
    assert applied == [{"wrap_text": True}]

    shown: list[str] = []

    class _About:
        def __init__(self, _parent) -> None:  # type: ignore[no-untyped-def]
            pass

        def exec(self) -> int:
            shown.append("about")
            return 0

    monkeypatch.setattr(mw, "AboutDialog", _About)
    win._show_about()
    assert shown == ["about"]

    theme_calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        win,
        "_apply_theme_mode",
        lambda mode, *, persist: theme_calls.append((str(mode), bool(persist))),
    )
    win._theme_mode = "DARK"
    win._on_system_color_scheme_changed()
    win._theme_mode = "SYSTEM"
    win._on_system_color_scheme_changed()
    assert theme_calls == [("SYSTEM", False)]
