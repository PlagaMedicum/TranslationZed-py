"""GUI startup helpers for TranslationZed-Py."""

from __future__ import annotations

import os

from PySide6.QtCore import QTimer

from .app import get_app
from .main_window import MainWindow


def launch(project_root: str | None = None) -> None:
    """Create and run the main window for an optional project root."""
    app = get_app()
    win = MainWindow(project_root)
    if getattr(win, "_startup_aborted", False):
        return
    win.show()
    if os.environ.get("TZP_SMOKE", "") == "1":
        timeout_ms = int(os.environ.get("TZP_SMOKE_TIMEOUT_MS", "2000"))
        QTimer.singleShot(max(timeout_ms, 250), app.quit)
    app.exec()
