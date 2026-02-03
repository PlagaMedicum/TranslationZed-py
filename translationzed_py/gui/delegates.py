from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QStyledItemDelegate

from translationzed_py.core.model import STATUS_ORDER, Status


class StatusDelegate(QStyledItemDelegate):
    """Combo-box editor for the Status column."""

    def createEditor(self, parent, _option, _index):  # noqa: N802
        combo = QComboBox(parent)
        for st in STATUS_ORDER:
            combo.addItem(st.label(), st)
        combo.setEditable(False)
        return combo

    def setEditorData(self, editor, index):  # noqa: N802
        if not isinstance(editor, QComboBox):
            return
        raw = index.data(Qt.EditRole)
        status = raw if isinstance(raw, Status) else None
        if status is None:
            try:
                status = Status[str(raw).upper().replace(" ", "_")]
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
                status = Status[str(text).upper().replace(" ", "_")]
            except Exception:
                return
        model.setData(index, status, Qt.EditRole)


class KeyDelegate(QStyledItemDelegate):
    """Right-align keys and elide the left side when column is narrow."""

    def initStyleOption(self, option, index):  # noqa: N802
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
        option.textElideMode = Qt.ElideLeft


class MultiLineEditDelegate(QStyledItemDelegate):
    """Expandable editor for multi-line text (editable or read-only)."""

    def __init__(self, parent=None, *, read_only: bool = False) -> None:
        super().__init__(parent)
        self._read_only = read_only

    def createEditor(self, parent, _option, _index):  # noqa: N802
        class _ScrollSafePlainTextEdit(QPlainTextEdit):
            def wheelEvent(self, event):  # noqa: N802
                super().wheelEvent(event)
                event.accept()

        editor = _ScrollSafePlainTextEdit(parent)
        editor.setReadOnly(self._read_only)
        editor.setFrameStyle(QPlainTextEdit.StyledPanel | QPlainTextEdit.Sunken)
        editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return editor

    def setEditorData(self, editor, index):  # noqa: N802
        if isinstance(editor, QPlainTextEdit):
            editor.setPlainText(str(index.data(Qt.EditRole) or ""))
            editor.moveCursor(QTextCursor.Start)
            width = editor.viewport().width() or editor.width() or 1
            editor.document().setTextWidth(width)
            editor.document().adjustSize()
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):  # noqa: N802
        if isinstance(editor, QPlainTextEdit):
            if not self._read_only:
                model.setData(index, editor.toPlainText(), Qt.EditRole)
            return
        super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, _index):  # noqa: N802
        rect = option.rect
        view = editor.parent()
        if hasattr(view, "viewport"):
            viewport = view.viewport()
            available = max(80, viewport.height() - rect.y() - 8)
            # Allow expansion up to the table bottom.
            max_height = available
        else:
            max_height = 240
        if isinstance(editor, QPlainTextEdit):
            metrics = editor.fontMetrics()
            min_height = metrics.lineSpacing() * 2 + 12
            text = ""
            # Prefer index data when available to avoid timing issues.
            if _index and _index.isValid():
                text = str(_index.data(Qt.EditRole) or "")
            doc = QTextDocument()
            doc.setDefaultFont(editor.font())
            doc.setTextWidth(rect.width())
            doc.setPlainText(text)
            desired = int(doc.size().height()) + 12
            height = min(max(desired, min_height), max_height)
            rect.setHeight(height)
        editor.setGeometry(rect)
