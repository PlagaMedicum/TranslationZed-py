"""Theme detection and palette application helpers for the Qt GUI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

THEME_SYSTEM = "SYSTEM"
THEME_LIGHT = "LIGHT"
THEME_DARK = "DARK"
THEME_MODES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

_BASE_STYLE_PROP = "_tzp_base_style"
_DARK_TOOLTIP_QSS = (
    "QToolTip {"
    "color: #f0f0f0;"
    "background-color: #2b2b2b;"
    "border: 1px solid #808080;"
    "}"
)


def normalize_theme_mode(value: object, *, default: str = THEME_SYSTEM) -> str:
    """Normalize arbitrary theme input to a supported mode constant."""
    raw = str(value).strip().upper()
    if raw in THEME_MODES:
        return raw
    return default


def system_theme_from_qt_scheme(scheme: object) -> str | None:
    """Map Qt color-scheme value to TZP theme mode.

    This helper is intentionally side-effect free and is used as a preparation
    hook for future "System follows OS dark mode" behavior.
    """
    color_scheme = getattr(Qt, "ColorScheme", None)
    if color_scheme is None:
        return None
    if scheme == color_scheme.Dark:
        return THEME_DARK
    if scheme == color_scheme.Light:
        return THEME_LIGHT
    return None


def detect_system_theme_mode(
    app: QApplication, *, style_hints: object | None = None
) -> str | None:
    """Best-effort system theme detection from Qt style hints."""
    hints = style_hints if style_hints is not None else app.styleHints()
    if hints is None:
        return None
    color_scheme = getattr(hints, "colorScheme", None)
    if not callable(color_scheme):
        return None
    try:
        return system_theme_from_qt_scheme(color_scheme())
    except Exception:
        return None


def connect_system_theme_sync(callback: Callable[..., object]) -> bool:
    """Connect callback to Qt system-theme change notifications when available."""
    app = QApplication.instance()
    if app is None:
        return False
    signal = getattr(app.styleHints(), "colorSchemeChanged", None)
    if signal is None or not hasattr(signal, "connect"):
        return False
    try:
        signal.connect(callback)
    except Exception:
        return False
    return True


def disconnect_system_theme_sync(callback: Callable[..., object]) -> bool:
    """Disconnect a previously connected system-theme change callback."""
    app = QApplication.instance()
    if app is None:
        return False
    signal = getattr(app.styleHints(), "colorSchemeChanged", None)
    if signal is None or not hasattr(signal, "disconnect"):
        return False
    try:
        signal.disconnect(callback)
    except Exception:
        return False
    return True


def _style_key(name: str) -> str | None:
    raw = name.strip()
    if not raw:
        return None
    available = QStyleFactory.keys()
    for key in available:
        if key.lower() == raw.lower():
            return key
    return None


def _ensure_base_style(app: QApplication) -> str:
    base = app.property(_BASE_STYLE_PROP)
    if isinstance(base, str):
        key = _style_key(base)
        if key:
            return key
    current = _style_key(app.style().objectName())
    if current:
        app.setProperty(_BASE_STYLE_PROP, current)
        return current
    fallback = _style_key("Fusion")
    if fallback:
        app.setProperty(_BASE_STYLE_PROP, fallback)
        return fallback
    return ""


def _apply_light_or_system(app: QApplication) -> None:
    base_style = _ensure_base_style(app)
    style_key = _style_key(base_style)
    if style_key:
        app.setStyle(style_key)
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet("")


def _apply_dark(app: QApplication) -> None:
    fusion = _style_key("Fusion")
    if fusion:
        app.setStyle(fusion)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(42, 42, 42))
    palette.setColor(QPalette.ToolTipBase, QColor(43, 43, 43))
    palette.setColor(QPalette.ToolTipText, QColor(240, 240, 240))
    palette.setColor(QPalette.Text, QColor(240, 240, 240))
    palette.setColor(QPalette.PlaceholderText, QColor(155, 155, 155))
    palette.setColor(QPalette.Button, QColor(52, 52, 52))
    palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    palette.setColor(QPalette.BrightText, QColor(255, 85, 85))
    palette.setColor(QPalette.Link, QColor(91, 157, 255))
    palette.setColor(QPalette.Highlight, QColor(63, 111, 180))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(135, 135, 135))
    palette.setColor(QPalette.Disabled, QPalette.PlaceholderText, QColor(95, 95, 95))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(135, 135, 135))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(135, 135, 135))
    app.setPalette(palette)
    app.setStyleSheet(_DARK_TOOLTIP_QSS)


def apply_theme(
    app: QApplication,
    mode: object,
    *,
    style_hints: object | None = None,
) -> str:
    """Apply requested theme mode to the QApplication and return normalized mode."""
    normalized = normalize_theme_mode(mode)
    if normalized == THEME_SYSTEM:
        system_mode = detect_system_theme_mode(app, style_hints=style_hints)
        if system_mode == THEME_DARK:
            _apply_dark(app)
        else:
            _apply_light_or_system(app)
        return normalized
    if normalized == THEME_DARK:
        _apply_dark(app)
    else:
        _apply_light_or_system(app)
    return normalized
