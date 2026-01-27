from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate

from translationzed_py.core.model import Status


class StatusDelegate(QStyledItemDelegate):
    """Combo-box editor for the Status column."""

    def createEditor(self, parent, _option, _index):  # noqa: N802
        combo = QComboBox(parent)
        for st in Status:
            combo.addItem(st.name.title(), st)
        combo.setEditable(False)
        return combo

    def setEditorData(self, editor, index):  # noqa: N802
        if not isinstance(editor, QComboBox):
            return
        raw = index.data(Qt.EditRole)
        status = raw if isinstance(raw, Status) else None
        if status is None:
            try:
                status = Status[str(raw).upper()]
            except Exception:
                status = None
        if status is None:
            editor.setCurrentIndex(-1)
            return
        for i in range(editor.count()):
            if editor.itemData(i) == status:
                editor.setCurrentIndex(i)
                return
        editor.setCurrentIndex(-1)

    def setModelData(self, editor, model, index):  # noqa: N802
        if not isinstance(editor, QComboBox):
            return
        status = editor.currentData()
        if status is None:
            text = editor.currentText()
            try:
                status = Status[str(text).upper()]
            except Exception:
                return
        model.setData(index, status, Qt.EditRole)
