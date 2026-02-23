"""Tests for status-column header controls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from translationzed_py.core.model import Status
from translationzed_py.gui.status_header import handle_header_click


class _Model:
    def __init__(self) -> None:
        self._sort = False
        self._filter: set[Status] | None = None

    def set_status_filter(self, statuses: set[Status] | None) -> None:
        self._filter = None if statuses is None else set(statuses)

    def status_filter(self) -> set[Status] | None:
        return None if self._filter is None else set(self._filter)

    def set_status_sort_enabled(self, enabled: bool) -> None:
        self._sort = bool(enabled)

    def status_sort_enabled(self) -> bool:
        return self._sort


class _Action:
    def __init__(self, text: str) -> None:
        self.text = text
        self.checked = False

    def setCheckable(self, _value: bool) -> None:
        return

    def setChecked(self, value: bool) -> None:
        self.checked = bool(value)


def _build_win(model: _Model) -> QWidget:
    win = QWidget()
    win.table = SimpleNamespace(  # type: ignore[attr-defined]
        model=lambda: model,
        horizontalHeader=lambda: SimpleNamespace(
            viewport=lambda: SimpleNamespace(mapToGlobal=lambda pos: pos),
            sectionPosition=lambda _idx: 0,
            height=lambda: 20,
        ),
    )
    win._apply_table_layout = lambda: None  # type: ignore[attr-defined]
    win._schedule_resize_reflow = lambda: None  # type: ignore[attr-defined]
    return win


def test_status_header_sort_toggle(monkeypatch, qapp) -> None:
    """Verify status-header sort action toggles priority sorting."""
    _ = qapp
    model = _Model()
    win = _build_win(model)

    class _Menu:
        def __init__(self, _parent) -> None:
            self._actions: list[_Action] = []

        def addAction(self, text: str) -> _Action:
            action = _Action(text)
            self._actions.append(action)
            return action

        def addSeparator(self) -> None:
            return

        def exec(self, _pos: QPoint):  # noqa: A003
            for action in self._actions:
                if action.text == "Sort by priority":
                    return action
            return None

    monkeypatch.setattr("translationzed_py.gui.status_header.QMenu", _Menu)
    handle_header_click(win, 3)
    assert model.status_sort_enabled() is True


def test_status_header_filter_toggle_and_show_all(monkeypatch, qapp) -> None:
    """Verify status-header filters toggle and reset via show-all action."""
    _ = qapp
    model = _Model()
    win = _build_win(model)
    steps = iter(["Untouched", "Show all statuses"])

    class _Menu:
        def __init__(self, _parent) -> None:
            self._actions: list[_Action] = []

        def addAction(self, text: str) -> _Action:
            action = _Action(text)
            self._actions.append(action)
            return action

        def addSeparator(self) -> None:
            return

        def exec(self, _pos: QPoint):  # noqa: A003
            wanted = next(steps)
            for action in self._actions:
                if action.text == wanted:
                    return action
            return None

    monkeypatch.setattr("translationzed_py.gui.status_header.QMenu", _Menu)

    handle_header_click(win, 3)
    assert model.status_filter() == {
        Status.FOR_REVIEW,
        Status.TRANSLATED,
        Status.PROOFREAD,
    }

    handle_header_click(win, 3)
    assert model.status_filter() is None


def test_status_header_ignores_non_status_column(qapp) -> None:
    """Verify non-status header clicks do not mutate status triage state."""
    _ = qapp
    model = _Model()
    win = _build_win(model)
    handle_header_click(win, 1)
    assert model.status_sort_enabled() is False
    assert model.status_filter() is None
