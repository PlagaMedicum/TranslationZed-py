"""Test module for source reference header interactions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QComboBox, QTableView, QWidget

from translationzed_py.gui.source_reference_header import (
    handle_header_click,
    refresh_header_label,
)


class _Win(QWidget):
    """Minimal Qt container used as a dialog-parent and attribute bag."""


def _build_win() -> _Win:
    win = _Win()
    win.table = QTableView(win)
    model = QStandardItemModel(1, 2, win.table)
    win.table.setModel(model)
    win.source_ref_combo = QComboBox(win)
    win._source_reference_mode = "EN"
    win._current_pf = None
    win._locale_for_path = lambda _path: ""
    return win


def test_refresh_header_label_handles_missing_table_or_model() -> None:
    """Verify header refresh exits safely when table/model is unavailable."""
    refresh_header_label(object())

    class _HeaderOnlyWin:
        """Lightweight object that exposes a table with no model."""

        def __init__(self) -> None:
            self.table = SimpleNamespace(model=lambda: None)
            self.source_ref_combo = SimpleNamespace(currentData=lambda: None)
            self._source_reference_mode = "EN"

    win = _HeaderOnlyWin()
    win._source_reference_mode = "EN"
    refresh_header_label(win)


def test_refresh_header_label_uses_combo_mode_or_fallback(qtbot) -> None:
    """Verify header text uses combo data and falls back to stored mode."""
    win = _build_win()
    qtbot.addWidget(win)

    win.source_ref_combo.addItem("RU", "RU")
    refresh_header_label(win)
    model = win.table.model()
    assert model is not None
    assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Source [RU] v"

    win.source_ref_combo.clear()
    win._source_reference_mode = "BE"
    refresh_header_label(win)
    assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Source [BE] v"


def test_handle_header_click_updates_combo_from_triggered_action(
    qtbot,
    monkeypatch,
) -> None:
    """Verify menu action triggers source-reference combo index update."""
    win = _build_win()
    qtbot.addWidget(win)
    win.source_ref_combo.addItem("EN", "EN")
    win.source_ref_combo.addItem("BE", "BE")
    win.source_ref_combo.addItem("RU", "RU")
    win.source_ref_combo.setCurrentIndex(0)
    win._current_pf = SimpleNamespace(path=Path("/tmp/proj/BE/ui.txt"))
    win._locale_for_path = lambda _path: "BE"

    class _Signal:
        """Minimal signal stub with connect/emit behavior."""

        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback):  # type: ignore[no-untyped-def]
            """Register callback."""
            self._callbacks.append(callback)

        def emit(self) -> None:
            """Run connected callbacks."""
            for callback in self._callbacks:
                callback()

    class _Action:
        """Minimal QAction-like stub used by the fake menu."""

        def __init__(self, text: str) -> None:
            self._text = text
            self.triggered = _Signal()

        def text(self) -> str:
            """Return action text."""
            return self._text

        def setCheckable(self, _value: bool) -> None:
            """Ignore checkable flag in the stub."""

        def setChecked(self, _value: bool) -> None:
            """Ignore checked flag in the stub."""

        def trigger(self) -> None:
            """Trigger connected callbacks."""
            self.triggered.emit()

    seen = {"exec_called": False}

    class _Menu:
        """Minimal QMenu replacement for deterministic tests."""

        def __init__(self, _parent) -> None:
            self._actions: list[_Action] = []

        def addAction(self, text: str) -> _Action:
            """Add and return a stub action."""
            action = _Action(text)
            self._actions.append(action)
            return action

        def actions(self) -> list[_Action]:
            """Return stub actions."""
            return list(self._actions)

        def exec(self, _pos) -> None:  # noqa: A003
            """Simulate opening menu and selecting the last action."""
            seen["exec_called"] = True
            assert [action.text() for action in self._actions] == ["EN", "RU"]
            self._actions[-1].trigger()

    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_header.QMenu",
        _Menu,
    )

    handle_header_click(win, 1)

    assert seen["exec_called"] is True
    assert win.source_ref_combo.currentData() == "RU"


def test_handle_header_click_early_returns_when_no_menu_actions(
    qtbot,
    monkeypatch,
) -> None:
    """Verify click handling exits when index invalid or all actions filtered out."""
    win = _build_win()
    qtbot.addWidget(win)
    win.source_ref_combo.addItem("BE", "BE")
    win.source_ref_combo.setCurrentIndex(0)
    win._current_pf = SimpleNamespace(path=Path("/tmp/proj/BE/ui.txt"))
    win._locale_for_path = lambda _path: "BE"

    class _Menu:
        """Menu stub that fails if exec is called unexpectedly."""

        def __init__(self, _parent) -> None:
            self._actions: list[object] = []

        def addAction(self, _text: str):  # type: ignore[no-untyped-def]
            self._actions.append(object())
            return self._actions[-1]

        def actions(self) -> list[object]:
            """Return stub actions."""
            return list(self._actions)

        def exec(self, _pos) -> None:  # noqa: A003
            """Fail if menu tries to show when no actions should exist."""
            raise AssertionError("menu.exec should not be called")

    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_header.QMenu",
        _Menu,
    )

    handle_header_click(win, 0)
    handle_header_click(win, 1)
