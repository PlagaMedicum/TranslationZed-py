import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPalette

from translationzed_py.gui.delegates import _build_visual_formats, _palette_cache_key


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Base, QColor(22, 22, 22))
    palette.setColor(QPalette.Text, QColor(232, 232, 232))
    palette.setColor(QPalette.Highlight, QColor(51, 102, 170))
    palette.setColor(QPalette.HighlightedText, QColor(245, 245, 245))
    return palette


def test_ws_glyph_format_is_visible_in_dark_palette() -> None:
    palette = _dark_palette()
    formats = _build_visual_formats(palette, selected=False)
    base = palette.color(QPalette.Base)
    ws = formats.ws_glyph.foreground().color()
    assert ws.lightness() > base.lightness()


def test_selected_tag_format_differs_from_plain_selected_text() -> None:
    palette = _dark_palette()
    formats = _build_visual_formats(palette, selected=True)
    tag = formats.tag.foreground().color()
    selected_text = palette.color(QPalette.HighlightedText)
    assert tag.rgba() != selected_text.rgba()


def test_palette_cache_key_changes_when_palette_changes() -> None:
    palette_a = _dark_palette()
    palette_b = _dark_palette()
    palette_b.setColor(QPalette.Highlight, QColor(110, 80, 40))
    assert _palette_cache_key(palette_a) != _palette_cache_key(palette_b)
