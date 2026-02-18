"""Test module for main-window bootstrap and helper utilities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent

from translationzed_py.gui import main_window as mw


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
