from __future__ import annotations

import sys
from typing import cast

from PySide6.QtWidgets import QApplication

_APP: QApplication | None = None


def get_app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = cast(QApplication, QApplication.instance()) or QApplication(sys.argv)
    return _APP
