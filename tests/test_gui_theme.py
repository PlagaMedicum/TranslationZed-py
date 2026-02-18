"""Test module for gui theme."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from translationzed_py.gui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    apply_theme,
    detect_system_theme_mode,
    normalize_theme_mode,
    system_theme_from_qt_scheme,
)


def test_normalize_theme_mode_accepts_supported_values() -> None:
    """Verify normalize theme mode accepts supported values."""
    assert normalize_theme_mode("dark") == THEME_DARK
    assert normalize_theme_mode("LIGHT") == "LIGHT"
    assert normalize_theme_mode("system") == THEME_SYSTEM
    assert normalize_theme_mode("unknown", default=THEME_DARK) == THEME_DARK


def test_apply_theme_dark_then_system_updates_stylesheet(qapp) -> None:
    """Verify apply theme dark then system updates stylesheet."""
    color_scheme = getattr(Qt, "ColorScheme", None)
    assert apply_theme(qapp, "dark") == THEME_DARK
    assert "QToolTip" in qapp.styleSheet()
    if color_scheme is None:
        assert apply_theme(qapp, "system", style_hints=object()) == THEME_SYSTEM
        assert qapp.styleSheet() == ""
        return

    class _Hints:
        def __init__(self, scheme):
            self._scheme = scheme

        def colorScheme(self):
            return self._scheme

    assert (
        apply_theme(qapp, "system", style_hints=_Hints(color_scheme.Dark))
        == THEME_SYSTEM
    )
    assert "QToolTip" in qapp.styleSheet()
    assert (
        apply_theme(qapp, "system", style_hints=_Hints(color_scheme.Light))
        == THEME_SYSTEM
    )
    assert qapp.styleSheet() == ""


def test_apply_theme_dark_sets_readable_text_roles(qapp) -> None:
    """Verify apply theme dark sets readable text roles."""
    assert apply_theme(qapp, "dark") == THEME_DARK
    palette = qapp.palette()
    base = palette.color(QPalette.Base)
    text = palette.color(QPalette.Text)
    placeholder = palette.color(QPalette.PlaceholderText)
    assert text.lightness() > base.lightness()
    assert placeholder.lightness() > base.lightness()


def test_system_theme_from_qt_scheme_maps_dark_light() -> None:
    """Verify system theme from qt scheme maps dark light."""
    color_scheme = getattr(Qt, "ColorScheme", None)
    if color_scheme is None:
        assert system_theme_from_qt_scheme(object()) is None
        return
    assert system_theme_from_qt_scheme(color_scheme.Dark) == THEME_DARK
    assert system_theme_from_qt_scheme(color_scheme.Light) == THEME_LIGHT
    assert system_theme_from_qt_scheme(object()) is None


def test_detect_system_theme_mode_uses_style_hints(qapp) -> None:
    """Verify detect system theme mode uses style hints."""
    color_scheme = getattr(Qt, "ColorScheme", None)
    if color_scheme is None:
        assert detect_system_theme_mode(qapp, style_hints=object()) is None
        return

    class _Hints:
        def __init__(self, scheme):
            self._scheme = scheme

        def colorScheme(self):
            return self._scheme

    assert (
        detect_system_theme_mode(qapp, style_hints=_Hints(color_scheme.Dark))
        == THEME_DARK
    )
    assert (
        detect_system_theme_mode(qapp, style_hints=_Hints(color_scheme.Light))
        == THEME_LIGHT
    )

    class _BrokenHints:
        def colorScheme(self):  # pragma: no cover - exercised by call
            raise RuntimeError("boom")

    assert detect_system_theme_mode(qapp, style_hints=_BrokenHints()) is None
