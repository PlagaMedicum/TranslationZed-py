from __future__ import annotations

from .app import get_app
from .main_window import MainWindow


def launch(project_root: str | None = None) -> None:
    app = get_app()
    win = MainWindow(project_root)
    if getattr(win, "_startup_aborted", False):
        return
    win.show()
    app.exec()
