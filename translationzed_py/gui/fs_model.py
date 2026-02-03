from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from translationzed_py.core.project_scanner import LocaleMeta, list_translatable_files


class FsModel(QStandardItemModel):
    """Tiny tree showing translatable files under <root>/<LOCALE>/."""

    def __init__(self, root: Path, locales: list[LocaleMeta]) -> None:
        super().__init__()
        self._root = root  # keep for helpers
        self._path_items: dict[str, QStandardItem] = {}
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
                abs_path = str(txt)
                file_item.setData(abs_path, int(Qt.ItemDataRole.UserRole))
                file_item.setData(rel, int(Qt.ItemDataRole.UserRole) + 1)
                loc_item.appendRow(file_item)
                self._path_items[abs_path] = file_item
            self.appendRow(loc_item)

    def set_dirty(self, path: Path, dirty: bool) -> None:
        item = self._path_items.get(str(path))
        if item is None:
            return
        base = item.data(int(Qt.ItemDataRole.UserRole) + 1) or item.text()
        label = f"● {base}" if dirty else str(base)
        item.setText(label)

    # ------------------------------------------------------------------ helper
    def index_for_path(self, path: Path) -> QModelIndex:
        """Return QModelIndex of *path* inside the tree."""
        item = self._path_items.get(str(path))
        return item.index() if item is not None else QModelIndex()
