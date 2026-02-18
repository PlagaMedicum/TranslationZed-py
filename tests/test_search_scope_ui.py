"""Test module for search scope UI icon helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from translationzed_py.gui.search_scope_ui import scope_icon_for


def test_scope_icon_for_supports_file_locale_and_project_scopes(qtbot) -> None:
    """Verify icon helper returns an icon for each supported scope."""
    host = QWidget()
    qtbot.addWidget(host)

    file_icon = scope_icon_for(host, "FILE")
    locale_icon = scope_icon_for(host, "LOCALE")
    project_icon = scope_icon_for(host, "PROJECT")

    assert isinstance(file_icon, QIcon)
    assert isinstance(locale_icon, QIcon)
    assert isinstance(project_icon, QIcon)
