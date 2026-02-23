"""Status-column header interaction helpers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu

from translationzed_py.core.model import STATUS_ORDER, Status

_ALL_STATUSES = set(STATUS_ORDER)


def _model_status_filter(model: Any) -> set[Status] | None:
    getter = getattr(model, "status_filter", None)
    if not callable(getter):
        return None
    value = getter()
    if value is None:
        return None
    return {status for status in value if isinstance(status, Status)}


def _apply_layout_refresh(win: Any) -> None:
    if hasattr(win, "_apply_table_layout"):
        win._apply_table_layout()
    if hasattr(win, "_schedule_resize_reflow"):
        win._schedule_resize_reflow()


def handle_header_click(win: Any, logical_index: int) -> None:
    """Show status sort/filter controls from the Status column header."""
    if logical_index != 3 or not hasattr(win, "table"):
        return
    model = win.table.model()
    if model is None:
        return
    if not hasattr(model, "set_status_filter") or not hasattr(
        model, "set_status_sort_enabled"
    ):
        return

    header = win.table.horizontalHeader()
    menu = QMenu(win)
    sort_enabled = bool(
        model.status_sort_enabled() if hasattr(model, "status_sort_enabled") else False
    )
    active_filter = _model_status_filter(model)
    visible_statuses = _ALL_STATUSES if active_filter is None else active_filter

    sort_action = menu.addAction("Sort by priority")
    sort_action.setCheckable(True)
    sort_action.setChecked(sort_enabled)
    menu.addSeparator()

    show_all_action = menu.addAction("Show all statuses")
    show_all_action.setCheckable(True)
    show_all_action.setChecked(active_filter is None)
    menu.addSeparator()

    status_actions: dict[Status, Any] = {}
    for status in STATUS_ORDER:
        action = menu.addAction(status.label())
        action.setCheckable(True)
        action.setChecked(status in visible_statuses)
        status_actions[status] = action

    pos = header.viewport().mapToGlobal(
        QPoint(header.sectionPosition(3), header.height())
    )
    selected = menu.exec(pos)
    if selected is None:
        return
    if selected is sort_action:
        model.set_status_sort_enabled(not sort_enabled)
        _apply_layout_refresh(win)
        return
    if selected is show_all_action:
        model.set_status_filter(None)
        _apply_layout_refresh(win)
        return

    picked_status = None
    for status, action in status_actions.items():
        if selected is action:
            picked_status = status
            break
    if picked_status is None:
        return
    next_filter = set(visible_statuses)
    if picked_status in next_filter:
        next_filter.remove(picked_status)
    else:
        next_filter.add(picked_status)
    if not next_filter or next_filter == _ALL_STATUSES:
        model.set_status_filter(None)
    else:
        model.set_status_filter(next_filter)
    _apply_layout_refresh(win)
