"""Test module for main-window bootstrap and helper utilities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent

from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal two-locale project fixture."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    return root


def test_in_test_mode_and_pref_parsers_handle_common_inputs(monkeypatch) -> None:
    """Verify helper parsers normalize booleans/ints and detect test mode flags."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TZP_TESTING", raising=False)
    assert mw._in_test_mode() is False

    monkeypatch.setenv("TZP_TESTING", "1")
    assert mw._in_test_mode() is True

    assert mw._bool_from_pref(True, default=False) is True
    assert mw._bool_from_pref("yes", default=False) is True
    assert mw._bool_from_pref("off", default=True) is False
    assert mw._bool_from_pref("unknown", default=True) is True

    assert mw._int_from_pref("10", default=3, min_value=0, max_value=99) == 10
    assert mw._int_from_pref("999", default=3, min_value=0, max_value=50) == 50
    assert mw._int_from_pref("-5", default=3, min_value=0, max_value=50) == 0
    assert mw._int_from_pref("bad", default=7, min_value=0, max_value=50) == 7


def test_patch_message_boxes_uses_test_shortcuts_and_non_test_fallback(
    monkeypatch,
) -> None:
    """Verify message-box patching returns Ok in test mode and defers otherwise."""
    monkeypatch.setattr(mw, "_TEST_DIALOGS_PATCHED", False)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_EXEC", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_WARNING", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_CRITICAL", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_INFORMATION", None)

    test_mode = {"enabled": True}
    monkeypatch.setattr(mw, "_in_test_mode", lambda: test_mode["enabled"])

    class _FakeMessageBox:
        """QMessageBox replacement used to validate patched handlers."""

        class StandardButton:
            Ok = 42

        @staticmethod
        def exec(_self) -> int:
            return 10

        @staticmethod
        def warning(*_args, **_kwargs) -> int:
            return 11

        @staticmethod
        def critical(*_args, **_kwargs) -> int:
            return 12

        @staticmethod
        def information(*_args, **_kwargs) -> int:
            return 13

    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    mw._patch_message_boxes_for_tests()

    assert mw._TEST_DIALOGS_PATCHED is True
    assert mw.QMessageBox.exec(object()) == int(_FakeMessageBox.StandardButton.Ok)
    assert mw.QMessageBox.warning(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )
    assert mw.QMessageBox.critical(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )
    assert mw.QMessageBox.information(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )

    test_mode["enabled"] = False
    assert mw.QMessageBox.exec(object()) == 10
    assert mw.QMessageBox.warning(object(), "t", "m") == 11
    assert mw.QMessageBox.critical(object(), "t", "m") == 12
    assert mw.QMessageBox.information(object(), "t", "m") == 13


def test_commit_plain_text_edit_focus_hooks_trigger_callbacks(qtbot) -> None:
    """Verify focus in/out events call configured commit and focus callbacks."""
    events: list[str] = []
    widget = mw._CommitPlainTextEdit(
        commit_cb=lambda: events.append("commit"),
        focus_cb=lambda: events.append("focus"),
    )
    qtbot.addWidget(widget)

    widget.focusInEvent(QFocusEvent(QEvent.FocusIn))
    widget.focusOutEvent(QFocusEvent(QEvent.FocusOut))

    assert events == ["focus", "commit"]


def test_main_window_startup_aborts_when_picker_cancelled(monkeypatch) -> None:
    """Verify startup returns early when root picker is cancelled."""

    class _Prefs:
        """Preferences stub that requests startup directory picker."""

        def resolve_startup_root(self, *, project_root):  # type: ignore[no-untyped-def]
            _ = project_root
            return SimpleNamespace(root=None, default_root="", requires_picker=True)

    monkeypatch.setattr(mw, "_PreferencesService", _Prefs)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: ""),
    )
    win = mw.MainWindow(project_root=None)
    assert win._startup_aborted is True


def test_main_window_startup_warns_for_missing_picked_root(
    tmp_path,
    monkeypatch,
) -> None:
    """Verify startup warns and aborts when selected project root is missing."""
    selected = tmp_path / "missing-root"
    persisted: list[str] = []
    warnings: list[tuple[str, str]] = []

    class _Prefs:
        """Preferences stub with picker-driven startup flow."""

        def resolve_startup_root(self, *, project_root):  # type: ignore[no-untyped-def]
            _ = project_root
            return SimpleNamespace(root=None, default_root="", requires_picker=True)

        def persist_default_root(self, value: str) -> None:
            persisted.append(value)

    monkeypatch.setattr(mw, "_PreferencesService", _Prefs)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: str(selected)),
    )
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        staticmethod(lambda _self, title, text: warnings.append((title, text))),
    )

    win = mw.MainWindow(project_root=None)
    assert win._startup_aborted is True
    assert persisted == [str(selected.resolve())]
    assert warnings == [("Invalid project root", str(selected.resolve()))]


def test_init_locales_handles_scan_exceptions(qtbot, tmp_path, monkeypatch) -> None:
    """Verify locale init handles scan failures with critical error fallback."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    errors: list[tuple[str, str]] = []

    def _raise_scan(_root: Path):  # type: ignore[no-untyped-def]
        raise RuntimeError("scan failed")

    monkeypatch.setattr(mw, "scan_root_with_errors", _raise_scan)
    monkeypatch.setattr(
        mw.QMessageBox,
        "critical",
        staticmethod(lambda _parent, title, text: errors.append((title, text))),
    )

    win._init_locales(selected_locales=["BE"])
    assert errors == [("Invalid language.txt", "scan failed")]
    assert win._locales == {}
    assert win._selected_locales == []


def test_init_locales_covers_malformed_warning_and_empty_selectable_branch(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify locale init warns on malformed files and handles EN-only scans."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _WarningBox:
        """Message-box stub used to capture malformed-language warnings."""

        Warning = 1
        instances: list[_WarningBox] = []

        def __init__(self, *_args, **_kwargs):
            self.title = ""
            self.text = ""
            self.detail = ""
            self.executed = False
            _WarningBox.instances.append(self)

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, title: str) -> None:
            self.title = title

        def setText(self, text: str) -> None:
            self.text = text

        def setDetailedText(self, detail: str) -> None:
            self.detail = detail

        def exec(self) -> None:
            self.executed = True

    calls: list[str] = []
    monkeypatch.setattr(mw, "QMessageBox", _WarningBox)
    monkeypatch.setattr(win, "_schedule_cache_migration", lambda: calls.append("migrate"))
    monkeypatch.setattr(win, "_schedule_post_locale_tasks", lambda: calls.append("post"))
    monkeypatch.setattr(win, "_warn_orphan_caches", lambda: calls.append("warn"))
    monkeypatch.setattr(mw.QTimer, "singleShot", lambda _ms, callback: callback())

    def _scan_with_errors(_root: Path):  # type: ignore[no-untyped-def]
        return {"EN": "English", "BE": "Belarusian"}, ["BE/language.txt: malformed"]

    monkeypatch.setattr(mw, "scan_root_with_errors", _scan_with_errors)
    win._init_locales(selected_locales=["BE"])

    assert _WarningBox.instances
    warning = _WarningBox.instances[-1]
    assert warning.executed is True
    assert warning.title == "Malformed language.txt"
    assert "skipped" in warning.text
    assert warning.detail == "BE/language.txt: malformed"
    assert win._selected_locales == ["BE"]
    assert calls == ["migrate", "warn", "post"]

    monkeypatch.setattr(mw, "scan_root_with_errors", lambda _root: ({"EN": "English"}, []))
    win._selected_locales = ["BE"]
    win._init_locales(selected_locales=None)
    assert win._selected_locales == []
