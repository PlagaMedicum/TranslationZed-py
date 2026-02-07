from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_SCOPES = [
    ("File", "FILE"),
    ("Locale", "LOCALE"),
    ("Locale Pool", "POOL"),
]


class PreferencesDialog(QDialog):
    def __init__(self, prefs: dict, *, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self._prefs = dict(prefs)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_search_tab(), "Search & Replace")
        tabs.addTab(self._build_view_tab(), "View")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "default_root": self._default_root_edit.text().strip(),
            "tm_import_dir": self._tm_import_dir_edit.text().strip(),
            "prompt_write_on_exit": self._prompt_exit_check.isChecked(),
            "wrap_text": self._wrap_text_check.isChecked(),
            "large_text_optimizations": self._large_text_opt_check.isChecked(),
            "visual_highlight": self._visual_highlight_check.isChecked(),
            "visual_whitespace": self._visual_whitespace_check.isChecked(),
            "search_scope": self._search_scope_combo.currentData(),
            "replace_scope": self._replace_scope_combo.currentData(),
        }

    def _build_general_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QFormLayout(widget)

        self._default_root_edit = QLineEdit(self._prefs.get("default_root", ""))
        browse_btn = QPushButton("Browse…", self)
        browse_btn.clicked.connect(self._browse_root)
        root_row = QWidget(self)
        root_layout = QHBoxLayout(root_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)
        root_layout.addWidget(self._default_root_edit)
        root_layout.addWidget(browse_btn)

        self._tm_import_dir_edit = QLineEdit(self._prefs.get("tm_import_dir", ""))
        browse_tm_btn = QPushButton("Browse…", self)
        browse_tm_btn.clicked.connect(self._browse_tm_import_dir)
        tm_row = QWidget(self)
        tm_layout = QHBoxLayout(tm_row)
        tm_layout.setContentsMargins(0, 0, 0, 0)
        tm_layout.setSpacing(6)
        tm_layout.addWidget(self._tm_import_dir_edit)
        tm_layout.addWidget(browse_tm_btn)

        self._prompt_exit_check = QCheckBox("Prompt before writing on exit", self)
        self._prompt_exit_check.setChecked(
            bool(self._prefs.get("prompt_write_on_exit", True))
        )

        layout.addRow(QLabel("Default root path"), root_row)
        layout.addRow(QLabel("TM import folder"), tm_row)
        layout.addRow(self._prompt_exit_check)
        return widget

    def _build_search_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QFormLayout(widget)

        self._search_scope_combo = QComboBox(self)
        self._replace_scope_combo = QComboBox(self)
        for label, value in _SCOPES:
            self._search_scope_combo.addItem(label, value)
            self._replace_scope_combo.addItem(label, value)

        search_scope = str(self._prefs.get("search_scope", "FILE")).upper()
        replace_scope = str(self._prefs.get("replace_scope", "FILE")).upper()
        self._set_combo_value(self._search_scope_combo, search_scope)
        self._set_combo_value(self._replace_scope_combo, replace_scope)

        layout.addRow(QLabel("Search scope"), self._search_scope_combo)
        layout.addRow(QLabel("Replace scope"), self._replace_scope_combo)
        return widget

    def _build_view_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QFormLayout(widget)

        self._wrap_text_check = QCheckBox("Wrap long strings in table", self)
        self._wrap_text_check.setChecked(bool(self._prefs.get("wrap_text", False)))
        self._large_text_opt_check = QCheckBox(
            "Enable large-text performance optimizations", self
        )
        self._large_text_opt_check.setChecked(
            bool(self._prefs.get("large_text_optimizations", True))
        )
        self._visual_highlight_check = QCheckBox(
            "Highlight tags and escape sequences", self
        )
        self._visual_highlight_check.setChecked(
            bool(self._prefs.get("visual_highlight", False))
        )
        self._visual_whitespace_check = QCheckBox(
            "Show whitespace glyphs (spaces/newlines)", self
        )
        self._visual_whitespace_check.setChecked(
            bool(self._prefs.get("visual_whitespace", False))
        )

        layout.addRow(self._wrap_text_check)
        layout.addRow(self._large_text_opt_check)
        layout.addRow(self._visual_highlight_check)
        layout.addRow(self._visual_whitespace_check)
        return widget

    def _browse_root(self) -> None:
        start_dir = self._default_root_edit.text().strip()
        picked = QFileDialog.getExistingDirectory(
            self, "Select Project Root", start_dir
        )
        if picked:
            self._default_root_edit.setText(str(Path(picked)))

    def _browse_tm_import_dir(self) -> None:
        start_dir = self._tm_import_dir_edit.text().strip()
        picked = QFileDialog.getExistingDirectory(
            self, "Select TM Import Folder", start_dir
        )
        if picked:
            self._tm_import_dir_edit.setText(str(Path(picked)))

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
