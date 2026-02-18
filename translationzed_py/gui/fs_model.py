"""Filesystem tree model for locale translation files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from translationzed_py.core.project_scanner import LocaleMeta, list_translatable_files

_ABS_PATH_ROLE = int(Qt.ItemDataRole.UserRole)
_REL_PATH_ROLE = _ABS_PATH_ROLE + 1
_LOCALE_CODE_ROLE = _ABS_PATH_ROLE + 2


class FsModel(QStandardItemModel):
    """Tiny tree showing translatable files under <root>/<LOCALE>/."""

    def __init__(
        self, root: Path, locales: list[LocaleMeta], *, lazy: bool = True
    ) -> None:
        """Initialize a tree model for locale files with optional lazy loading."""
        super().__init__()
        self._root = root  # keep for helpers
        self._lazy = lazy
        self._path_items: dict[str, QStandardItem] = {}
        self._pending_dirty: set[str] = set()
        self._locale_meta: dict[str, LocaleMeta] = {meta.code: meta for meta in locales}
        self._locale_items: dict[str, QStandardItem] = {}
        self._loaded_locales: set[str] = set()
        self.setHorizontalHeaderLabels(["Project files"])

        for meta in locales:
            loc_item = QStandardItem(f"{meta.code} — {meta.display_name}")
            loc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            loc_item.setData(meta.code, _LOCALE_CODE_ROLE)
            if self._lazy:
                placeholder = QStandardItem("...")
                placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
                loc_item.appendRow(placeholder)
            else:
                self._populate_locale(loc_item, meta)
                self._loaded_locales.add(meta.code)
            self.appendRow(loc_item)
            self._locale_items[meta.code] = loc_item

    def is_lazy(self) -> bool:
        """Return whether locale nodes are populated lazily."""
        return self._lazy

    def ensure_loaded_for_index(self, index: QModelIndex) -> None:
        """Ensure the locale branch for the given index is populated."""
        if not index.isValid():
            return
        item = self.itemFromIndex(index)
        if item is None:
            return
        code = item.data(_LOCALE_CODE_ROLE)
        if isinstance(code, str):
            self._ensure_locale_loaded(code)

    def _ensure_locale_loaded(self, code: str) -> None:
        if code in self._loaded_locales:
            return
        meta = self._locale_meta.get(code)
        item = self._locale_items.get(code)
        if not meta or item is None:
            return
        self._populate_locale(item, meta)
        self._loaded_locales.add(code)

    def _populate_locale(self, loc_item: QStandardItem, meta: LocaleMeta) -> None:
        loc_item.removeRows(0, loc_item.rowCount())
        for txt in list_translatable_files(meta.path):
            rel = str(txt.relative_to(meta.path))
            file_item = QStandardItem(rel)
            file_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            abs_path = str(txt)
            file_item.setData(abs_path, _ABS_PATH_ROLE)
            file_item.setData(rel, _REL_PATH_ROLE)
            loc_item.appendRow(file_item)
            self._path_items[abs_path] = file_item
            if abs_path in self._pending_dirty:
                self._apply_dirty_label(file_item, True)
                self._pending_dirty.discard(abs_path)

    def set_dirty(self, path: Path, dirty: bool) -> None:
        """Toggle dirty visual marker for a file node by absolute path."""
        abs_path = str(path)
        item = self._path_items.get(abs_path)
        if item is None:
            if dirty:
                self._pending_dirty.add(abs_path)
            else:
                self._pending_dirty.discard(abs_path)
            return
        self._apply_dirty_label(item, dirty)
        if dirty:
            self._pending_dirty.discard(abs_path)

    def _apply_dirty_label(self, item: QStandardItem, dirty: bool) -> None:
        base = item.data(_REL_PATH_ROLE) or item.text()
        label = f"● {base}" if dirty else str(base)
        item.setText(label)

    # ------------------------------------------------------------------ helper
    def index_for_path(self, path: Path) -> QModelIndex:
        """Return QModelIndex of *path* inside the tree."""
        abs_path = str(path)
        item = self._path_items.get(abs_path)
        if item is not None:
            return item.index()
        if not self._lazy:
            return QModelIndex()
        code = self._locale_code_for_path(path)
        if code:
            self._ensure_locale_loaded(code)
            item = self._path_items.get(abs_path)
            if item is not None:
                return item.index()
        return QModelIndex()

    def _locale_code_for_path(self, path: Path) -> str | None:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return None
        if not rel.parts:
            return None
        return rel.parts[0]
