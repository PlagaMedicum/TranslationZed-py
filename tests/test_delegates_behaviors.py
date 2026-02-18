"""Test module for delegate editors, visual helpers, and rendering branches."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPalette,
    QStandardItem,
    QStandardItemModel,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import (
    QComboBox,
    QStyle,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from translationzed_py.core.model import Status
from translationzed_py.gui.delegates import (
    MAX_VISUAL_CHARS,
    MultiLineEditDelegate,
    StatusDelegate,
    TextVisualHighlighter,
    VisualTextDelegate,
    _apply_visual_formats,
    _apply_whitespace_option,
    _palette_cache_key,
)


def _make_option(view: QTableView) -> QStyleOptionViewItem:
    """Build a reusable style option for delegate paint/size tests."""
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, 40)
    option.state = QStyle.State_Enabled | QStyle.State_Active
    option.widget = view
    option.font = view.font()
    option.palette = view.palette()
    return option


def test_status_delegate_editor_data_and_model_roundtrip(qtbot) -> None:
    """Verify status delegate maps edit data between model and combo editor."""
    parent = QWidget()
    qtbot.addWidget(parent)
    delegate = StatusDelegate(parent)

    model = QStandardItemModel(1, 1, parent)
    index = model.index(0, 0)

    combo = delegate.createEditor(parent, None, index)
    assert isinstance(combo, QComboBox)
    assert combo.count() == len(tuple(Status))

    model.setData(index, Status.PROOFREAD, Qt.EditRole)
    delegate.setEditorData(combo, index)
    assert combo.currentData() == Status.PROOFREAD

    model.setData(index, "for review", Qt.EditRole)
    delegate.setEditorData(combo, index)
    assert combo.currentData() == Status.FOR_REVIEW

    model.setData(index, "invalid-value", Qt.EditRole)
    delegate.setEditorData(combo, index)
    assert combo.currentIndex() == -1

    combo.setCurrentIndex(combo.findData(Status.TRANSLATED))
    delegate.setModelData(combo, model, index)
    assert model.data(index, Qt.EditRole) == Status.TRANSLATED

    combo.setEditable(True)
    combo.setCurrentIndex(-1)
    combo.setEditText("bad status")
    delegate.setModelData(combo, model, index)
    assert model.data(index, Qt.EditRole) == Status.TRANSLATED

    bare_combo = QComboBox(parent)
    model.setData(index, Status.PROOFREAD, Qt.EditRole)
    delegate.setEditorData(bare_combo, index)
    assert bare_combo.currentIndex() == -1

    delegate.setEditorData(QWidget(parent), index)
    delegate.setModelData(QWidget(parent), model, index)


def test_multiline_delegate_editor_update_and_geometry_paths(qtbot) -> None:
    """Verify multiline delegate editor config, model sync, and geometry updates."""
    table = QTableView()
    qtbot.addWidget(table)
    model = QStandardItemModel(1, 1, table)
    model.setData(model.index(0, 0), "line one\nline two", Qt.EditRole)
    table.setModel(model)
    index = model.index(0, 0)
    option = _make_option(table)

    delegate = MultiLineEditDelegate(table, read_only=False)
    editor = delegate.createEditor(table, option, index)
    assert editor.isReadOnly() is False
    delegate.setEditorData(editor, index)
    assert editor.toPlainText() == "line one\nline two"

    delegate.updateEditorGeometry(editor, option, index)
    assert editor.geometry().height() >= 1

    delegate.setModelData(editor, model, index)
    assert model.data(index, Qt.EditRole) == "line one\nline two"

    read_only_delegate = MultiLineEditDelegate(table, read_only=True)
    read_only_editor = read_only_delegate.createEditor(table, option, index)
    read_only_editor.setPlainText("changed text")
    read_only_delegate.setModelData(read_only_editor, model, index)
    assert model.data(index, Qt.EditRole) == "line one\nline two"

    standalone_parent = QWidget()
    qtbot.addWidget(standalone_parent)
    standalone_editor = delegate.createEditor(standalone_parent, option, index)
    delegate.updateEditorGeometry(standalone_editor, option, index)
    assert standalone_editor.geometry().height() >= 1

    delegate.setEditorData(QComboBox(table), index)
    delegate.setModelData(QComboBox(table), model, index)

    invalid_option = _make_option(table)
    invalid_option.rect = QRect(0, 0, 200, 20)
    non_plain = QWidget(table)
    delegate.updateEditorGeometry(non_plain, invalid_option, None)
    assert non_plain.geometry().height() == 20


def test_palette_cache_key_and_visual_helpers_cover_fallback_branches(
    monkeypatch,
) -> None:
    """Verify visual helper functions cover whitespace and palette-key fallback paths."""

    class _BrokenPalette:
        """Palette stub that raises from cacheKey to trigger fallback tuple key."""

        def cacheKey(self) -> int:
            raise RuntimeError("cache key unavailable")

        def color(self, role):  # type: ignore[no-untyped-def]
            _ = role
            return QColor("#112233")

    fallback_key = _palette_cache_key(_BrokenPalette())  # type: ignore[arg-type]
    assert isinstance(fallback_key, tuple)
    assert len(fallback_key) == 4

    doc = QTextDocument()
    _apply_whitespace_option(doc, True)
    flags = doc.defaultTextOption().flags()
    assert bool(flags & QTextOption.ShowTabsAndSpaces)

    _apply_whitespace_option(doc, False)
    flags = doc.defaultTextOption().flags()
    assert not bool(flags & QTextOption.ShowTabsAndSpaces)

    palette = QPalette()
    doc.setPlainText(r"A <b> {TOKEN}  \n B")
    _apply_visual_formats(
        doc,
        doc.toPlainText(),
        highlight=True,
        show_ws=True,
        palette=palette,
        selected=False,
    )
    _apply_visual_formats(
        doc,
        "",
        highlight=True,
        show_ws=True,
        palette=palette,
        selected=True,
    )

    monkeypatch.setattr("translationzed_py.gui.delegates.MAX_VISUAL_CHARS", 8)
    doc.setPlainText("abcdefghijk")
    highlighter = TextVisualHighlighter(
        doc,
        options_provider=lambda: (True, True, True),
    )
    highlighter.rehighlight()


def test_visual_delegate_cache_editor_sizehint_and_paint_paths(
    qtbot, monkeypatch
) -> None:
    """Verify visual delegate cache, editor setup, size hints, and paint branches."""
    view = QTableView()
    qtbot.addWidget(view)
    view.setWordWrap(False)
    model = QStandardItemModel(1, 1, view)
    item = QStandardItem("short text {tag} \\n")
    model.setItem(0, 0, item)
    view.setModel(model)
    index = model.index(0, 0)

    delegate = VisualTextDelegate(
        view,
        options_provider=lambda: (False, False, False),
    )
    option = _make_option(view)

    entry_a = delegate._get_cached_doc(
        "abc",
        120,
        font=option.font,
        palette=option.palette,
        show_ws=False,
        highlight=False,
        selected=False,
    )
    entry_b = delegate._get_cached_doc(
        "abc",
        120,
        font=option.font,
        palette=option.palette,
        show_ws=False,
        highlight=False,
        selected=False,
    )
    assert entry_a.doc is entry_b.doc

    monkeypatch.setattr("translationzed_py.gui.delegates._DOC_CACHE_MAX", 1)
    delegate._get_cached_doc(
        "def",
        120,
        font=option.font,
        palette=option.palette,
        show_ws=False,
        highlight=False,
        selected=False,
    )
    assert len(delegate._doc_cache) == 1
    delegate.clear_visual_cache()
    assert delegate._doc_cache == {}

    editor = delegate.createEditor(view, option, index)
    assert hasattr(editor, "_text_visual_highlighter")
    model.setData(index, "x" * (MAX_VISUAL_CHARS + 1), Qt.EditRole)
    delegate.setEditorData(editor, index)

    model.setData(index, "x" * 5001, Qt.DisplayRole)
    hint = delegate.sizeHint(option, index)
    assert hint.height() > 0

    model.setData(index, None, Qt.DisplayRole)
    fallback_hint = delegate.sizeHint(option, index)
    assert fallback_hint.height() >= 0

    model.setData(index, "wrapped text value", Qt.DisplayRole)
    hint_regular = delegate.sizeHint(option, index)
    assert hint_regular.height() > 0

    image = QImage(260, 60, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        model.setData(index, "x" * 5001, Qt.DisplayRole)
        selected_long = QStyleOptionViewItem(option)
        selected_long.state |= QStyle.State_Selected
        delegate.paint(painter, selected_long, index)

        model.setData(index, "plain single line", Qt.DisplayRole)
        delegate.paint(painter, option, index)

        view.setWordWrap(True)
        delegate.paint(painter, option, index)

        selected_option = QStyleOptionViewItem(option)
        selected_option.state |= QStyle.State_Selected
        highlight_delegate = VisualTextDelegate(
            view,
            options_provider=lambda: (True, True, True),
        )
        highlight_delegate.paint(painter, selected_option, index)
    finally:
        painter.end()

    monkeypatch.setattr("translationzed_py.gui.delegates.MAX_VISUAL_CHARS", 8)
    model.setData(index, "0123456789", Qt.DisplayRole)
    optimize_delegate = VisualTextDelegate(
        view,
        options_provider=lambda: (True, True, True),
    )
    optimize_delegate.sizeHint(option, index)

    image2 = QImage(260, 60, QImage.Format_ARGB32)
    image2.fill(0)
    painter2 = QPainter(image2)
    try:
        optimize_delegate.paint(painter2, option, index)
    finally:
        painter2.end()

    class _DummyDelegate(VisualTextDelegate):
        """Visual delegate subclass with non-plain editor fallback path."""

        def createEditor(self, parent, _option, _index):  # noqa: N802
            return QWidget(parent)

    dummy = _DummyDelegate(view, options_provider=lambda: (False, False, False))
    widget_editor = dummy.createEditor(view, option, index)
    assert isinstance(widget_editor, QWidget)


def test_visual_delegate_set_editor_data_non_plain_and_optimize_branch(
    qtbot, monkeypatch
) -> None:
    """Verify visual delegate setEditorData handles non-plain and optimize branches."""
    view = QTableView()
    qtbot.addWidget(view)
    model = QStandardItemModel(1, 1, view)
    model.setData(model.index(0, 0), "x" * 100, Qt.EditRole)
    view.setModel(model)
    index = model.index(0, 0)

    monkeypatch.setattr("translationzed_py.gui.delegates.MAX_VISUAL_CHARS", 8)
    delegate = VisualTextDelegate(
        view,
        options_provider=lambda: (True, True, True),
    )
    option = _make_option(view)
    editor = delegate.createEditor(view, option, index)
    delegate.setEditorData(editor, index)
    delegate.setEditorData(QWidget(view), index)
