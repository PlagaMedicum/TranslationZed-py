import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui.theme import (
    THEME_DARK,
    THEME_SYSTEM,
    apply_theme,
    normalize_theme_mode,
)


def test_normalize_theme_mode_accepts_supported_values() -> None:
    assert normalize_theme_mode("dark") == THEME_DARK
    assert normalize_theme_mode("LIGHT") == "LIGHT"
    assert normalize_theme_mode("system") == THEME_SYSTEM
    assert normalize_theme_mode("unknown", default=THEME_DARK) == THEME_DARK


def test_apply_theme_dark_then_system_updates_stylesheet(qapp) -> None:
    assert apply_theme(qapp, "dark") == THEME_DARK
    assert "QToolTip" in qapp.styleSheet()
    assert apply_theme(qapp, "system") == THEME_SYSTEM
    assert qapp.styleSheet() == ""
