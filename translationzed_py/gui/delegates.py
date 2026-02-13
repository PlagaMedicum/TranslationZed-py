from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QColor,
    QPalette,
    QStaticText,
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

from .perf_trace import PERF_TRACE


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


_TAG_RE = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>\r\n]+)?>")
_BRACKET_TAG_RE = re.compile(r"\[[Ii][Mm][Gg]=[^\]\r\n]+\]")
_PLACEHOLDER_RE = re.compile(r"%(?:\d+\$[A-Za-z]|\d+|[A-Za-z])")
_ESCAPE_RE = re.compile(r"\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|[nrt\"\\\\])")
_WS_RE = re.compile(r"[ \t]{2,}")
_WS_GLYPH_RE = re.compile(r"[ \t]")

_MAX_RENDER_CHARS = 4000
_MAX_RENDER_LINES = 12
MAX_VISUAL_CHARS = 100_000
_DOC_CACHE_MAX = 256

_TAG_LIGHT = QColor("#2a6f97")
_TAG_DARK = QColor("#8bcfff")
_TAG_SELECTED = QColor("#ffe58f")
_ESCAPE_LIGHT = QColor("#6a4c93")
_ESCAPE_DARK = QColor("#d7bbff")
_ESCAPE_SELECTED = QColor("#ffd0ff")
_WS_GLYPH_LIGHT = QColor("#5a5a5a")
_WS_GLYPH_DARK = QColor("#aab3bf")
_WS_GLYPH_SELECTED = QColor("#ffd48f")
_WS_REPEAT_BG_LIGHT = QColor("#f0f0f0")
_WS_REPEAT_BG_DARK = QColor("#ffffff")
_WS_REPEAT_BG_SELECTED = QColor("#ffffff")


@dataclass(frozen=True, slots=True)
class _VisualFormats:
    tag: QTextCharFormat
    escape: QTextCharFormat
    ws_glyph: QTextCharFormat
    ws_repeat: QTextCharFormat


@dataclass(frozen=True, slots=True)
class _DocCacheEntry:
    text: str
    width: int
    height: int
    doc: QTextDocument


def _is_dark_palette(palette: QPalette) -> bool:
    base = palette.color(QPalette.Base)
    text = palette.color(QPalette.Text)
    return text.lightness() > base.lightness()


def _alpha(color: QColor, value: int) -> QColor:
    out = QColor(color)
    out.setAlpha(value)
    return out


def _palette_cache_key(palette: QPalette) -> int | tuple[int, int, int, int]:
    key_attr = getattr(palette, "cacheKey", None)
    if callable(key_attr):
        try:
            return int(key_attr())
        except Exception:
            pass
    return (
        palette.color(QPalette.Base).rgba(),
        palette.color(QPalette.Text).rgba(),
        palette.color(QPalette.Highlight).rgba(),
        palette.color(QPalette.HighlightedText).rgba(),
    )


def _build_visual_formats(
    palette: QPalette,
    *,
    selected: bool,
) -> _VisualFormats:
    dark = _is_dark_palette(palette)
    tag_color = _TAG_DARK if dark else _TAG_LIGHT
    escape_color = _ESCAPE_DARK if dark else _ESCAPE_LIGHT
    ws_color = _WS_GLYPH_DARK if dark else _WS_GLYPH_LIGHT
    ws_repeat_bg = _WS_REPEAT_BG_DARK if dark else _WS_REPEAT_BG_LIGHT
    if selected:
        tag_color = _TAG_SELECTED
        escape_color = _ESCAPE_SELECTED
        ws_color = _WS_GLYPH_SELECTED
        ws_repeat_bg = _WS_REPEAT_BG_SELECTED

    tag_fmt = QTextCharFormat()
    tag_fmt.setForeground(tag_color)

    escape_fmt = QTextCharFormat()
    escape_fmt.setForeground(escape_color)

    ws_glyph_fmt = QTextCharFormat()
    ws_glyph_fmt.setForeground(_alpha(ws_color, 240))

    ws_repeat_fmt = QTextCharFormat()
    ws_repeat_fmt.setForeground(_alpha(ws_color, 235))
    ws_repeat_fmt.setBackground(_alpha(ws_repeat_bg, 70 if selected else 120))

    return _VisualFormats(
        tag=tag_fmt,
        escape=escape_fmt,
        ws_glyph=ws_glyph_fmt,
        ws_repeat=ws_repeat_fmt,
    )


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


def _apply_visual_formats(
    doc: QTextDocument,
    text: str,
    *,
    highlight: bool,
    show_ws: bool,
    palette: QPalette,
    selected: bool,
) -> None:
    if not text:
        return
    formats = _build_visual_formats(palette, selected=selected)
    if show_ws:
        cursor = QTextCursor(doc)
        for match in _WS_GLYPH_RE.finditer(text):
            cursor.setPosition(match.start())
            cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(formats.ws_glyph)
    if not highlight:
        return
    cursor = QTextCursor(doc)
    for regex in (_TAG_RE, _BRACKET_TAG_RE, _PLACEHOLDER_RE):
        for match in regex.finditer(text):
            cursor.setPosition(match.start())
            cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(formats.tag)
    for match in _ESCAPE_RE.finditer(text):
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(formats.escape)
    for match in _WS_RE.finditer(text):
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(formats.ws_repeat)


class TextVisualHighlighter(QSyntaxHighlighter):
    def __init__(
        self,
        doc: QTextDocument,
        options_provider: Callable[[], tuple[bool, bool, bool]],
        palette_provider: Callable[[], QPalette] | None = None,
    ):
        super().__init__(doc)
        self._options_provider = options_provider
        self._palette_provider = palette_provider or QApplication.palette

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        show_ws, highlight, optimize = self._options_provider()
        if optimize and self.document().characterCount() >= MAX_VISUAL_CHARS:
            show_ws = False
            highlight = False
        palette = self._palette_provider()
        formats = _build_visual_formats(palette, selected=False)
        if show_ws:
            for match in _WS_GLYPH_RE.finditer(text):
                self.setFormat(
                    match.start(), match.end() - match.start(), formats.ws_glyph
                )
        if not highlight:
            return
        for regex in (_TAG_RE, _BRACKET_TAG_RE, _PLACEHOLDER_RE):
            for match in regex.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), formats.tag)
        for match in _ESCAPE_RE.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), formats.escape
            )
        for match in _WS_RE.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), formats.ws_repeat
            )


class VisualTextDelegate(MultiLineEditDelegate):
    """Delegate with optional glyphs and tag/escape highlighting."""

    def __init__(
        self,
        parent=None,
        *,
        read_only: bool = False,
        options_provider: Callable[[], tuple[bool, bool, bool]] | None = None,
    ) -> None:
        super().__init__(parent, read_only=read_only)
        self._options_provider = options_provider or (lambda: (False, False, False))
        self._doc = QTextDocument()
        self._doc_cache: OrderedDict[tuple, _DocCacheEntry] = OrderedDict()

    def clear_visual_cache(self) -> None:
        self._doc_cache.clear()

    def _get_cached_doc(
        self,
        text: str,
        width: int,
        *,
        font,
        palette,
        show_ws: bool,
        highlight: bool,
        selected: bool,
    ) -> _DocCacheEntry:
        cache_key = (
            text,
            width,
            font.key(),
            _palette_cache_key(palette),
            show_ws,
            highlight,
            selected,
        )
        entry = self._doc_cache.get(cache_key)
        if entry is not None:
            self._doc_cache.move_to_end(cache_key)
            return entry
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setPlainText(text)
        _apply_whitespace_option(doc, show_ws)
        doc.setTextWidth(width)
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.Document)
        base_format = QTextCharFormat()
        if selected:
            base_format.setForeground(palette.highlightedText())
        else:
            base_format.setForeground(palette.text())
        cursor.mergeCharFormat(base_format)
        _apply_visual_formats(
            doc,
            text,
            highlight=highlight,
            show_ws=show_ws,
            palette=palette,
            selected=selected,
        )
        entry = _DocCacheEntry(
            text=text, width=width, height=int(doc.size().height()), doc=doc
        )
        self._doc_cache[cache_key] = entry
        if len(self._doc_cache) > _DOC_CACHE_MAX:
            self._doc_cache.popitem(last=False)
        return entry

    def createEditor(self, parent, _option, _index):  # noqa: N802
        editor = super().createEditor(parent, _option, _index)
        if isinstance(editor, QPlainTextEdit):
            show_ws, _highlight, _optimize = self._options_provider()
            _apply_whitespace_option(editor.document(), show_ws)
            editor._text_visual_highlighter = TextVisualHighlighter(  # type: ignore[attr-defined]
                editor.document(),
                self._options_provider,
                palette_provider=editor.palette,
            )
        return editor

    def setEditorData(self, editor, index):  # noqa: N802
        super().setEditorData(editor, index)
        if not isinstance(editor, QPlainTextEdit):
            return
        show_ws, _highlight, optimize = self._options_provider()
        text = str(index.data(Qt.EditRole) or "")
        if optimize and len(text) >= MAX_VISUAL_CHARS:
            show_ws = False
        _apply_whitespace_option(editor.document(), show_ws)

    def sizeHint(self, option, index):  # noqa: N802
        text = index.data(Qt.DisplayRole)
        if isinstance(text, str) and len(text) > _MAX_RENDER_CHARS:
            line_height = option.fontMetrics.lineSpacing()
            height = line_height * _MAX_RENDER_LINES + 8
            return QSize(0, height)
        if not isinstance(text, str) or not text:
            return super().sizeHint(option, index)
        show_ws, highlight, optimize = self._options_provider()
        if optimize and len(text) >= MAX_VISUAL_CHARS:
            show_ws = False
            highlight = False
        width = max(0, option.rect.width() - 8)
        entry = self._get_cached_doc(
            text,
            width,
            font=option.font,
            palette=option.palette,
            show_ws=show_ws,
            highlight=highlight,
            selected=False,
        )
        height = max(0, entry.height) + 8
        return QSize(0, height)

    def paint(self, painter, option, index):  # noqa: N802
        perf_trace = PERF_TRACE
        start = perf_trace.start("paint")
        try:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            text = opt.text
            opt.text = ""
            style = opt.widget.style() if opt.widget else QApplication.style()
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

            if len(text) > _MAX_RENDER_CHARS:
                text_rect = opt.rect.adjusted(4, 0, -4, 0)
                painter.save()
                painter.setClipRect(text_rect)
                if opt.state & QStyle.State_Selected:
                    painter.setPen(opt.palette.highlightedText().color())
                else:
                    painter.setPen(opt.palette.text().color())
                elided = opt.fontMetrics.elidedText(
                    text, Qt.ElideRight, text_rect.width()
                )
                painter.drawText(
                    text_rect,
                    Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
                    elided,
                )
                painter.restore()
                return

            show_ws, highlight, _optimize = self._options_provider()
            wrap = False
            if opt.widget is not None and hasattr(opt.widget, "wordWrap"):
                try:
                    wrap = bool(opt.widget.wordWrap())
                except Exception:
                    wrap = False
            if not highlight and not show_ws:
                text_rect = opt.rect.adjusted(4, 0, -4, 0)
                painter.save()
                painter.setClipRect(text_rect)
                painter.setFont(opt.font)
                if opt.state & QStyle.State_Selected:
                    painter.setPen(opt.palette.highlightedText().color())
                else:
                    painter.setPen(opt.palette.text().color())
                if not wrap:
                    # No-wrap rows: avoid QTextDocument layout; draw a single elided line.
                    elided = opt.fontMetrics.elidedText(
                        text, Qt.ElideRight, text_rect.width()
                    )
                    painter.drawText(
                        text_rect,
                        Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
                        elided,
                    )
                else:
                    static_text = QStaticText(text)
                    static_text.setTextFormat(Qt.PlainText)
                    text_option = QTextOption()
                    text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
                    static_text.setTextOption(text_option)
                    static_text.setTextWidth(max(0, text_rect.width()))
                    painter.drawStaticText(text_rect.topLeft(), static_text)
                painter.restore()
                return

            show_ws, highlight, optimize = self._options_provider()
            if optimize and len(text) >= MAX_VISUAL_CHARS:
                show_ws = False
                highlight = False
            text_rect = opt.rect.adjusted(4, 0, -4, 0)
            width = max(0, text_rect.width())
            entry = self._get_cached_doc(
                text,
                width,
                font=opt.font,
                palette=opt.palette,
                show_ws=show_ws,
                highlight=highlight,
                selected=bool(opt.state & QStyle.State_Selected),
            )

            painter.save()
            painter.setClipRect(text_rect)
            painter.translate(text_rect.topLeft())
            entry.doc.drawContents(painter)
            painter.restore()
        finally:
            perf_trace.stop("paint", start, items=1, unit="cells")
