from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QTreeView,
)

from translationzed_py.core import parse
from translationzed_py.core.saver import save

from .entry_model import TranslationModel
from .fs_model import FsModel


class MainWindow(QMainWindow):
    """Main window: left file-tree, right translation table."""

    def __init__(self, project_root: str | None = None) -> None:
        super().__init__()
        self._root = Path(project_root or ".").resolve()
        self.setWindowTitle(f"TranslationZed – {self._root}")

        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # ── left pane: project tree ──────────────────────────────────────────
        self.tree = QTreeView()
        self.fs_model = FsModel(self._root)
        self.tree.setModel(self.fs_model)
        self.tree.expandAll()
        self.tree.activated.connect(self._file_chosen)  # double-click / Enter
        splitter.addWidget(self.tree)

        # ── right pane: entry table ─────────────────────────────────────────
        self.table = QTableView()
        splitter.addWidget(self.table)

        splitter.setSizes([220, 600])

        # ── save action ─────────────────────────────────────────────────────
        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save_current)
        self.addAction(act_save)

        self._current_pf = None  # type: translationzed_py.core.model.ParsedFile | None
        self._current_model: TranslationModel | None = None

    # ----------------------------------------------------------------- slots
    def _file_chosen(self, index) -> None:
        """Populate table when user activates a .txt file."""
        path: Path | None = index.data(Qt.UserRole)  # FsModel stores Path here
        if not (path and path.suffix == ".txt"):
            return
        try:
            pf = parse(path)
        except Exception as exc:
            QMessageBox.warning(self, "Parse error", f"{path}\n\n{exc}")
            return

        self._current_pf = pf
        self._current_model = TranslationModel(pf.entries)
        self.table.setModel(self._current_model)

    def _save_current(self) -> None:
        """Patch file on disk if there are unsaved edits in the table model."""
        if not (self._current_pf and self._current_model):
            return
        if not getattr(self._current_model, "_dirty", False):
            return

        changed = {e.key: e.value for e in self._current_model._entries}
        try:
            save(self._current_pf, changed)
            self._current_model._dirty = False
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
