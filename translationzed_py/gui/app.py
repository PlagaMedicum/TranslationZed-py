from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication

_APP: QApplication | None = None

def get_app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication(sys.argv)
    return _APP
