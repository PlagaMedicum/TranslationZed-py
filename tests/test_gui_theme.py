"""Test module for gui theme."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from translationzed_py.gui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    _apply_dark,
    _apply_light_or_system,
    _ensure_base_style,
    _style_key,
    apply_theme,
    connect_system_theme_sync,
    detect_system_theme_mode,
    disconnect_system_theme_sync,
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


def test_system_theme_from_qt_scheme_without_colorscheme_returns_none(
    monkeypatch,
) -> None:
    """Verify scheme mapper returns None when Qt lacks ColorScheme enum."""

    class _QtNoScheme:
        """Qt stub that omits ColorScheme."""

    monkeypatch.setattr("translationzed_py.gui.theme.Qt", _QtNoScheme())
    assert system_theme_from_qt_scheme(object()) is None


def test_detect_system_theme_mode_handles_missing_hints_and_non_callable_scheme(
    qapp,
) -> None:
    """Verify system theme detection returns None for unsupported hints."""
    assert detect_system_theme_mode(qapp, style_hints=None) in {
        None,
        THEME_LIGHT,
        THEME_DARK,
    }
    assert detect_system_theme_mode(qapp, style_hints=object()) is None


def test_connect_disconnect_theme_sync_guard_clauses_and_failures(monkeypatch) -> None:
    """Verify system theme sync connect/disconnect handles unavailable signals."""

    def callback(*_args, **_kwargs) -> None:
        """No-op callback for signal connect/disconnect tests."""
        return None

    monkeypatch.setattr(
        "translationzed_py.gui.theme.QApplication.instance", lambda: None
    )
    assert connect_system_theme_sync(callback) is False
    assert disconnect_system_theme_sync(callback) is False

    class _SignalNoHooks:
        """Signal stub without connect/disconnect methods."""

    class _SignalRaises:
        """Signal stub that raises during connect/disconnect."""

        def connect(self, _callback) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("connect failed")

        def disconnect(self, _callback) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("disconnect failed")

    class _AppStub:
        """Application stub exposing configurable style hints."""

        def __init__(self, signal) -> None:  # type: ignore[no-untyped-def]
            self._signal = signal

        def styleHints(self):  # type: ignore[no-untyped-def]
            return type("_Hints", (), {"colorSchemeChanged": self._signal})()

        def processEvents(self) -> None:
            """No-op Qt event pump for pytest-qt teardown hooks."""

    monkeypatch.setattr(
        "translationzed_py.gui.theme.QApplication.instance",
        lambda: _AppStub(_SignalNoHooks()),
    )
    assert connect_system_theme_sync(callback) is False
    assert disconnect_system_theme_sync(callback) is False

    monkeypatch.setattr(
        "translationzed_py.gui.theme.QApplication.instance",
        lambda: _AppStub(_SignalRaises()),
    )
    assert connect_system_theme_sync(callback) is False
    assert disconnect_system_theme_sync(callback) is False


def test_style_key_and_base_style_fallback_paths(monkeypatch) -> None:
    """Verify style-key resolution and base-style fallback behaviors."""
    monkeypatch.setattr(
        "translationzed_py.gui.theme.QStyleFactory.keys",
        lambda: ["Fusion", "Windows"],
    )
    assert _style_key("") is None
    assert _style_key("Unknown") is None
    assert _style_key("windows") == "Windows"

    class _Style:
        """Style stub used for objectName/standardPalette methods."""

        def objectName(self) -> str:
            return "Windows"

        def standardPalette(self):  # type: ignore[no-untyped-def]
            return object()

    class _App:
        """App stub exposing the minimal style/palette interface."""

        def __init__(self, base_value: object) -> None:
            self._props = {"_tzp_base_style": base_value}

        def property(self, name: str) -> object:
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def style(self) -> _Style:
            return _Style()

    app = _App("invalid")
    assert _ensure_base_style(app) == "Windows"
    assert app.property("_tzp_base_style") == "Windows"

    monkeypatch.setattr("translationzed_py.gui.theme.QStyleFactory.keys", lambda: [])
    app_no_styles = _App("invalid")
    assert _ensure_base_style(app_no_styles) == ""


def test_light_and_dark_apply_paths_handle_missing_style_keys(
    qapp, monkeypatch
) -> None:
    """Verify light/dark apply helpers tolerate missing style-key lookup."""
    monkeypatch.setattr("translationzed_py.gui.theme._style_key", lambda _name: None)
    _apply_light_or_system(qapp)
    _apply_dark(qapp)
