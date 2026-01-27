from __future__ import annotations

from pathlib import Path

import xxhash
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QTreeView,
)

from translationzed_py.core import LocaleMeta, parse, scan_root
from translationzed_py.core.model import Status
from translationzed_py.core.saver import save
from translationzed_py.core.status_cache import read as _read_status_cache
from translationzed_py.core.status_cache import write as _write_status_cache

from .entry_model import TranslationModel
from .fs_model import FsModel
from .commands import ChangeStatusCommand
from .dialogs import LocaleChooserDialog


class MainWindow(QMainWindow):
    """Main window: left file-tree, right translation table."""

    def __init__(
        self, project_root: str | None = None, *, selected_locales: list[str] | None = None
    ) -> None:
        super().__init__()
        self._root = Path(project_root or ".").resolve()
        self.setWindowTitle(f"TranslationZed – {self._root}")
        self._locales: dict[str, LocaleMeta] = {}
        self._selected_locales: list[str] = []
        self._current_encoding = "utf-8"

        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # ── left pane: project tree ──────────────────────────────────────────
        self.tree = QTreeView()
        self._init_locales(selected_locales)
        self.fs_model = FsModel(self._root, [self._locales[c] for c in self._selected_locales])
        self.tree.setModel(self.fs_model)
        # prevent in-place renaming on double-click; we use double-click to open
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.expandAll()
        self.tree.activated.connect(self._file_chosen)  # Enter / platform activation
        self.tree.doubleClicked.connect(self._file_chosen)
        splitter.addWidget(self.tree)

        # ── proofread toggle ────────────────────────────────────────────────
        act_proof = QAction("&Mark Proofread", self)
        act_proof.setShortcut("Ctrl+P")
        act_proof.triggered.connect(self._mark_proofread)
        self.addAction(act_proof)
        self.act_proof = act_proof

        # ── right pane: entry table ─────────────────────────────────────────
        self.table = QTableView()
        splitter.addWidget(self.table)

        splitter.setSizes([220, 600])

        # ── undo/redo actions ───────────────────────────────────────────────
        self.act_undo: QAction | None = None
        self.act_redo: QAction | None = None

        # ── save action ─────────────────────────────────────────────────────
        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save_current)
        self.addAction(act_save)

        self._current_pf = None  # type: translationzed_py.core.model.ParsedFile | None
        self._current_model: TranslationModel | None = None

        # ── status-cache ───────────────────────────────────────────────
        self._status_map: dict[int, Status] = {}

    def _init_locales(self, selected_locales: list[str] | None) -> None:
        self._locales = scan_root(self._root)
        selectable = {k: v for k, v in self._locales.items() if k != "EN"}

        if selected_locales is None:
            dialog = LocaleChooserDialog(selectable.values(), self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                self._selected_locales = []
                return
            selected_locales = dialog.selected_codes()

        self._selected_locales = [c for c in selected_locales if c in selectable]

    def _locale_for_path(self, path: Path) -> str | None:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return None
        if not rel.parts:
            return None
        return rel.parts[0]

    # ----------------------------------------------------------------- slots
    def _file_chosen(self, index) -> None:
        """Populate table when user activates a .txt file."""
        raw_path = index.data(Qt.UserRole)  # FsModel stores absolute path string
        path = Path(raw_path) if raw_path else None
        if not (path and path.suffix == ".txt"):
            return
        locale = self._locale_for_path(path)
        encoding = self._locales.get(locale, LocaleMeta("", Path(), "", "utf-8")).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            QMessageBox.warning(self, "Parse error", f"{path}\n\n{exc}")
            return

        self._current_encoding = encoding

        self._status_map = _read_status_cache(self._root, path)

        for e in pf.entries:
            h = xxhash.xxh64(e.key.encode("utf-8")).intdigest() & 0xFFFF
            if h in self._status_map:
                # Entry is frozen → use object.__setattr__
                object.__setattr__(e, "status", self._status_map[h])
        self._current_pf = pf
        self._current_model = TranslationModel(pf)
        self.table.setModel(self._current_model)

        # (re)create undo/redo actions bound to this file’s stack
        for old in (self.act_undo, self.act_redo):
            if old:
                self.removeAction(old)
        stack = self._current_model.undo_stack
        self.act_undo = stack.createUndoAction(self, "&Undo")
        self.act_redo = stack.createRedoAction(self, "&Redo")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        for a in (self.act_undo, self.act_redo):
            self.addAction(a)


    def _save_current(self) -> None:
        """Patch file on disk if there are unsaved edits in the table model."""
        if not (self._current_pf and self._current_model):
            return
        if not getattr(self._current_model, "_dirty", False):
            return

        changed = self._current_model.changed_values()
        try:
            if changed:
                save(self._current_pf, changed, encoding=self._current_encoding)

            # update in-memory cache with *new* statuses from the file we saved
            for e in self._current_pf.entries:
                h = xxhash.xxh64(e.key.encode("utf-8")).intdigest() & 0xFFFF
                self._status_map[h] = e.status

            # persist statuses for this file only (edited files only)
            _write_status_cache(self._root, self._current_pf.path, self._current_pf.entries)

            self._current_model._dirty = False
            self._current_model.clear_changed_values()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _mark_proofread(self) -> None:
        if not (self._current_pf and self._current_model):
            return
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        cmd = ChangeStatusCommand(
            self._current_pf, row, Status.PROOFREAD, self._current_model
        )
        self._current_model.undo_stack.push(cmd)
