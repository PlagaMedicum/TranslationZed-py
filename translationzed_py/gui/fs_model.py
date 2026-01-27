from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from translationzed_py.core.project_scanner import LocaleMeta, list_translatable_files


class FsModel(QStandardItemModel):
    """Tiny tree showing  <root>/<LOCALE>/**/*.txt  files only."""

    def __init__(self, root: Path, locales: list[LocaleMeta]) -> None:
        super().__init__()
        self._root = root  # keep for helpers
        self.setHorizontalHeaderLabels(["Project files"])

        for meta in locales:
            loc_item = QStandardItem(f"{meta.code} — {meta.display_name}")
            loc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for txt in list_translatable_files(meta.path):
                rel = str(txt.relative_to(meta.path))
                file_item = QStandardItem(rel)
                file_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                # store absolute path string in UserRole
                file_item.setData(str(txt), int(Qt.ItemDataRole.UserRole))
                loc_item.appendRow(file_item)
            self.appendRow(loc_item)

    # ------------------------------------------------------------------ helper
    def index_for_path(self, path: Path) -> QModelIndex:
        """Return QModelIndex of *path* inside the tree."""
        matches = self.match(
            self.index(0, 0),
            Qt.UserRole,
            str(path),
            hits=1,
            flags=Qt.MatchRecursive | Qt.MatchExactly,
        )
        return matches[0] if matches else QModelIndex()
