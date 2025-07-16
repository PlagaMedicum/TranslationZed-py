from __future__ import annotations

from .app import get_app
from .main_window import MainWindow


def launch(project_root: str | None = None) -> None:
    app = get_app()
    win = MainWindow(project_root)
    win.show()
    app.exec()
