from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel


class FsModel(QStandardItemModel):
    """Tiny tree showing  <root>/<LOCALE>/**/*.txt  files only."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root  # keep for helpers
        self.setHorizontalHeaderLabels(["Project files"])

        for loc_dir in sorted(root.iterdir()):
            if not (loc_dir.is_dir() and len(loc_dir.name) == 2):
                continue
            loc_item = QStandardItem(loc_dir.name)
            loc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for txt in sorted(loc_dir.rglob("*.txt")):
                rel = str(txt.relative_to(root))
                file_item = QStandardItem(rel)
                file_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                # store absolute Path in UserRole
                file_item.setData(txt, int(Qt.ItemDataRole.UserRole))
                loc_item.appendRow(file_item)
            self.appendRow(loc_item)

    # ------------------------------------------------------------------ helper
    def index_for_path(self, path: Path) -> QModelIndex:
        """Return QModelIndex of *path* inside the tree."""
        rel = str(path.relative_to(self._root))
        matches = self.match(
            self.index(0, 0),
            Qt.DisplayRole,
            rel,
            hits=1,
            flags=Qt.MatchRecursive | Qt.MatchExactly,
        )
        return matches[0] if matches else QModelIndex()
