from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu


def refresh_header_label(win: Any) -> None:
    if not hasattr(win, "table"):
        return
    model = win.table.model()
    if model is None:
        return
    mode = str(win.source_ref_combo.currentData() or win._source_reference_mode or "EN")
    model.setHeaderData(
        1,
        Qt.Horizontal,
        f"Source [{mode}] v",
        Qt.DisplayRole,
    )


def handle_header_click(win: Any, logical_index: int) -> None:
    if not hasattr(win, "table"):
        return
    if logical_index != 1 or win.source_ref_combo.count() <= 0:
        return
    header = win.table.horizontalHeader()
    menu = QMenu(win)
    current_mode = str(win.source_ref_combo.currentData() or "")
    current_locale = ""
    if win._current_pf is not None:
        current_locale = str(win._locale_for_path(win._current_pf.path) or "").upper()
    for idx in range(win.source_ref_combo.count()):
        mode = str(win.source_ref_combo.itemData(idx) or "")
        if not mode or mode.upper() == current_locale:
            continue
        action = menu.addAction(mode)
        action.setCheckable(True)
        action.setChecked(mode == current_mode)
        action.triggered.connect(
            lambda _checked=False, i=idx: win.source_ref_combo.setCurrentIndex(i)
        )
    if not menu.actions():
        return
    pos = header.viewport().mapToGlobal(
        QPoint(header.sectionPosition(1), header.height())
    )
    menu.exec(pos)
