from __future__ import annotations
from .main_window import MainWindow
from .app import get_app

def launch(project_root: str | None = None) -> None:
    app = get_app()
    win = MainWindow(project_root)
    win.show()
    app.exec()
