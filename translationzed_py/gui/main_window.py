from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QSplitter, QTreeView, QTableView
from translationzed_py.core import parse, scan_root
from .fs_model import LocaleFsModel
from .entry_model import TranslationModel

class MainWindow(QMainWindow):
    def __init__(self, project_root: str | None = None):
        super().__init__()
        root = Path(project_root or ".").resolve()
        self.setWindowTitle(f"TranslationZed – {root}")
        splitter = QSplitter()
        # left: file tree
        self.fs_model = LocaleFsModel(root)
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(str(root)))
        self.tree.clicked.connect(self._on_file_selected)
        splitter.addWidget(self.tree)
        # right: entry table
        self.table = QTableView()
        splitter.addWidget(self.table)
        self.setCentralWidget(splitter)

    # slot ---------------------------------------------------------------------
    def _on_file_selected(self, index):
        path = Path(self.fs_model.filePath(index))
        if path.suffix == ".txt":
            pf = parse(path)
            model = TranslationModel(pf.entries)
            self.table.setModel(model)

