from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QFileSystemModel

class LocaleFsModel(QFileSystemModel):
    """Hide files not under 2-letter locale sub-dirs (EN, BE, RU …)."""

    def __init__(self, root: Path):
        super().__init__()
        self.setRootPath(str(root))

    def filterAcceptsRow(self, source_row, source_parent):
        ix = self.index(source_row, 0, source_parent)
        return super().isDir(ix) or self.fileName(ix).endswith(".txt")
