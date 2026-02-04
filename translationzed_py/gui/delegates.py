from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QPlainTextEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

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


_TAG_RE = re.compile(r"<[^>\r\n]+>")
_ESCAPE_RE = re.compile(r"\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|[nrt\"\\\\])")
_WS_RE = re.compile(r"[ \t]{2,}")

_TAG_FORMAT = QTextCharFormat()
_TAG_FORMAT.setForeground(QColor("#2a6f97"))
_ESCAPE_FORMAT = QTextCharFormat()
_ESCAPE_FORMAT.setForeground(QColor("#6a4c93"))
_WS_FORMAT = QTextCharFormat()
_WS_FORMAT.setForeground(QColor("#888888"))
_WS_FORMAT.setBackground(QColor("#f0f0f0"))


def _apply_whitespace_option(doc: QTextDocument, enabled: bool) -> None:
    option = doc.defaultTextOption()
    flags = option.flags()
    if enabled:
        flags |= (
            QTextOption.ShowTabsAndSpaces | QTextOption.ShowLineAndParagraphSeparators
        )
    else:
        flags &= ~(
            QTextOption.ShowTabsAndSpaces | QTextOption.ShowLineAndParagraphSeparators
        )
    option.setFlags(flags)
    doc.setDefaultTextOption(option)


def _apply_visual_formats(doc: QTextDocument, text: str, *, highlight: bool) -> None:
    if not highlight or not text:
        return
    cursor = QTextCursor(doc)
    for match in _TAG_RE.finditer(text):
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(_TAG_FORMAT)
    for match in _ESCAPE_RE.finditer(text):
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(_ESCAPE_FORMAT)
    for match in _WS_RE.finditer(text):
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(_WS_FORMAT)


class TextVisualHighlighter(QSyntaxHighlighter):
    def __init__(
        self, doc: QTextDocument, options_provider: Callable[[], tuple[bool, bool]]
    ):
        super().__init__(doc)
        self._options_provider = options_provider

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        _show_ws, highlight = self._options_provider()
        if not highlight:
            return
        for match in _TAG_RE.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), _TAG_FORMAT)
        for match in _ESCAPE_RE.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), _ESCAPE_FORMAT)
        for match in _WS_RE.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), _WS_FORMAT)


class VisualTextDelegate(MultiLineEditDelegate):
    """Delegate with optional glyphs and tag/escape highlighting."""

    def __init__(
        self,
        parent=None,
        *,
        read_only: bool = False,
        options_provider: Callable[[], tuple[bool, bool]] | None = None,
    ) -> None:
        super().__init__(parent, read_only=read_only)
        self._options_provider = options_provider or (lambda: (False, False))
        self._doc = QTextDocument()

    def createEditor(self, parent, _option, _index):  # noqa: N802
        editor = super().createEditor(parent, _option, _index)
        if isinstance(editor, QPlainTextEdit):
            show_ws, _highlight = self._options_provider()
            _apply_whitespace_option(editor.document(), show_ws)
            editor._text_visual_highlighter = TextVisualHighlighter(  # type: ignore[attr-defined]
                editor.document(), self._options_provider
            )
        return editor

    def paint(self, painter, option, index):  # noqa: N802
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        doc = self._doc
        doc.setDefaultFont(opt.font)
        doc.setPlainText(text)
        show_ws, highlight = self._options_provider()
        _apply_whitespace_option(doc, show_ws)
        text_rect = opt.rect.adjusted(4, 0, -4, 0)
        doc.setTextWidth(max(0, text_rect.width()))
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.Document)
        base_format = QTextCharFormat()
        if opt.state & QStyle.State_Selected:
            base_format.setForeground(opt.palette.highlightedText())
        else:
            base_format.setForeground(opt.palette.text())
        cursor.mergeCharFormat(base_format)
        _apply_visual_formats(doc, text, highlight=highlight)

        painter.save()
        painter.translate(text_rect.topLeft())
        doc.drawContents(painter)
        painter.restore()
