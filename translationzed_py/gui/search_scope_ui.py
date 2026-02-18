"""UI helpers for search scope presentation."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QWidget


def scope_icon_for(style_host: QWidget, scope: str) -> QIcon:
    """Return an icon matching the configured search scope."""
    if scope == "FILE":
        return QIcon.fromTheme(
            "text-x-generic",
            style_host.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        )
    if scope == "LOCALE":
        return QIcon.fromTheme(
            "folder",
            style_host.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
        )
    return QIcon.fromTheme(
        "view-list-tree",
        style_host.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
    )
