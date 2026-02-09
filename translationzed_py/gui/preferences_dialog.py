from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
_THEME_MODES = [
    ("System", "SYSTEM"),
    ("Light", "LIGHT"),
    ("Dark", "DARK"),
]
_TM_PATH_ROLE = Qt.UserRole + 1
_TM_IS_PENDING_ROLE = Qt.UserRole + 2
_TM_STATUS_ROLE = Qt.UserRole + 3


class PreferencesDialog(QDialog):
    def __init__(
        self,
        prefs: dict,
        *,
        tm_files: list[dict[str, object]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self._prefs = dict(prefs)
        self._tm_files = list(tm_files or [])
        self._tm_enabled: dict[str, bool] = {}
        self._tm_initial_enabled: dict[str, bool] = {}
        self._tm_remove_paths: set[str] = set()
        self._tm_import_paths: list[str] = []
        self._tm_resolve_pending = False
        self._tm_export_tmx = False
        self._tm_rebuild = False
        self._tm_show_diagnostics = False
        self._tm_resolve_btn: QPushButton | None = None

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_search_tab(), "Search / Replace")
        tabs.addTab(self._build_tm_tab(), "TM")
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
        changed_tm_enabled = {
            tm_path: enabled
            for tm_path, enabled in self._tm_enabled.items()
            if self._tm_initial_enabled.get(tm_path) != enabled
        }
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
            "theme_mode": self._theme_mode_combo.currentData(),
            "tm_enabled": changed_tm_enabled,
            "tm_remove_paths": sorted(self._tm_remove_paths),
            "tm_import_paths": list(self._tm_import_paths),
            "tm_resolve_pending": self._tm_resolve_pending,
            "tm_export_tmx": self._tm_export_tmx,
            "tm_rebuild": self._tm_rebuild,
            "tm_show_diagnostics": self._tm_show_diagnostics,
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

        self._theme_mode_combo = QComboBox(self)
        for label, value in _THEME_MODES:
            self._theme_mode_combo.addItem(label, value)
        theme_mode = str(self._prefs.get("theme_mode", "SYSTEM")).upper()
        self._set_combo_value(self._theme_mode_combo, theme_mode)
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

        layout.addRow(QLabel("Theme"), self._theme_mode_combo)
        layout.addRow(self._wrap_text_check)
        layout.addRow(self._large_text_opt_check)
        layout.addRow(self._visual_highlight_check)
        layout.addRow(self._visual_whitespace_check)
        return widget

    def _build_tm_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(
            "Imported TM files (unchecked = disabled for suggestions).", widget
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self._tm_formats_label = QLabel(
            "Supported now:\n"
            "- Import: TMX (.tmx, TMX 1.4)\n"
            "- Export: TMX (.tmx, TMX 1.4)\n"
            "- Runtime store: .tzp/config/tm.sqlite\n"
            "- Managed imported folder: .tzp/tms\n"
            "\n"
            "Planned later:\n"
            "- Additional exchange formats (deferred).",
            widget,
        )
        self._tm_formats_label.setWordWrap(True)
        layout.addWidget(self._tm_formats_label)
        self._tm_list = QListWidget(widget)
        self._tm_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tm_list.itemChanged.connect(self._on_tm_item_changed)
        layout.addWidget(self._tm_list)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        import_btn = QPushButton("Import TMX…", widget)
        import_btn.setToolTip("Queue TMX files for import into the managed TM folder")
        import_btn.clicked.connect(self._queue_tm_imports)
        remove_btn = QPushButton("Remove selected", widget)
        remove_btn.setToolTip(
            "Remove selected imported TM files (with confirmation before delete)"
        )
        remove_btn.clicked.connect(self._remove_selected_tm_items)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        ops_row = QHBoxLayout()
        ops_row.setContentsMargins(0, 0, 0, 0)
        ops_row.setSpacing(6)
        self._tm_resolve_btn = QPushButton("Resolve Pending", widget)
        self._tm_resolve_btn.setToolTip(
            "Resolve pending/unmapped/error imported TM files"
        )
        self._tm_resolve_btn.clicked.connect(self._request_tm_resolve_pending)
        export_btn = QPushButton("Export TMX…", widget)
        export_btn.setToolTip("Export current TM entries to a TMX file")
        export_btn.clicked.connect(self._request_tm_export)
        rebuild_btn = QPushButton("Rebuild TM", widget)
        rebuild_btn.setToolTip("Rebuild project TM from selected locale files")
        rebuild_btn.clicked.connect(self._request_tm_rebuild)
        diagnostics_btn = QPushButton("Diagnostics", widget)
        diagnostics_btn.setToolTip("Show TM diagnostics for current filters and row")
        diagnostics_btn.clicked.connect(self._request_tm_diagnostics)
        ops_row.addWidget(self._tm_resolve_btn)
        ops_row.addWidget(export_btn)
        ops_row.addWidget(rebuild_btn)
        ops_row.addWidget(diagnostics_btn)
        ops_row.addStretch(1)
        layout.addLayout(ops_row)

        for row in self._tm_files:
            self._add_tm_file_item(row)
        self._update_tm_action_state()
        return widget

    def _add_tm_file_item(self, row: dict[str, object]) -> None:
        tm_path = str(row.get("tm_path", "")).strip()
        if not tm_path:
            return
        tm_name = str(row.get("tm_name", "")).strip() or tm_path
        source_locale = str(row.get("source_locale", "")).strip().upper()
        target_locale = str(row.get("target_locale", "")).strip().upper()
        source_locale_raw = str(row.get("source_locale_raw", "")).strip()
        target_locale_raw = str(row.get("target_locale_raw", "")).strip()
        try:
            segment_count = max(0, int(row.get("segment_count", 0) or 0))
        except (TypeError, ValueError):
            segment_count = 0
        status = str(row.get("status", "")).strip() or "ready"
        enabled = bool(row.get("enabled", True))
        if source_locale and target_locale:
            locale_pair = f"{source_locale}->{target_locale}"
        else:
            locale_pair = "unmapped"
        raw_pair = ""
        if source_locale_raw and target_locale_raw:
            normalized_raw = (
                source_locale_raw.upper().replace("_", "-"),
                target_locale_raw.upper().replace("_", "-"),
            )
            normalized_pair = (
                source_locale.upper().replace("_", "-"),
                target_locale.upper().replace("_", "-"),
            )
            if normalized_raw != normalized_pair:
                raw_pair = f" {{{source_locale_raw}->{target_locale_raw}}}"
        text = f"{tm_name} [{locale_pair}{raw_pair}] ({status}, {segment_count} seg)"
        if segment_count == 0:
            text += " [WARNING: 0 segments]"
        item = QListWidgetItem(text, self._tm_list)
        item.setToolTip(tm_path)
        item.setData(_TM_PATH_ROLE, tm_path)
        item.setData(_TM_IS_PENDING_ROLE, False)
        item.setData(_TM_STATUS_ROLE, status)
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if status == "ready":
            flags |= Qt.ItemIsUserCheckable
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            self._tm_enabled[tm_path] = enabled
            self._tm_initial_enabled[tm_path] = enabled
        item.setFlags(flags)

    def _queue_tm_imports(self) -> None:
        start_dir = self._tm_import_dir_edit.text().strip() or str(Path.cwd())
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import TMX files",
            start_dir,
            "TMX files (*.tmx);;All files (*)",
        )
        for raw_path in paths:
            tm_path = str(Path(raw_path))
            if tm_path in self._tm_import_paths:
                continue
            self._tm_import_paths.append(tm_path)
            item = QListWidgetItem(
                f"{Path(tm_path).name} [queued import]", self._tm_list
            )
            item.setToolTip(tm_path)
            item.setData(_TM_PATH_ROLE, tm_path)
            item.setData(_TM_IS_PENDING_ROLE, True)
            item.setData(_TM_STATUS_ROLE, "queued")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self._update_tm_action_state()

    def _remove_selected_tm_items(self) -> None:
        items = list(self._tm_list.selectedItems())
        for item in items:
            tm_path = str(item.data(_TM_PATH_ROLE) or "").strip()
            pending = bool(item.data(_TM_IS_PENDING_ROLE))
            if tm_path:
                if pending:
                    self._tm_import_paths = [
                        p for p in self._tm_import_paths if p != tm_path
                    ]
                else:
                    self._tm_remove_paths.add(tm_path)
                    self._tm_enabled.pop(tm_path, None)
                    self._tm_initial_enabled.pop(tm_path, None)
            row = self._tm_list.row(item)
            self._tm_list.takeItem(row)
        self._update_tm_action_state()

    def _on_tm_item_changed(self, item: QListWidgetItem) -> None:
        tm_path = str(item.data(_TM_PATH_ROLE) or "").strip()
        if not tm_path or bool(item.data(_TM_IS_PENDING_ROLE)):
            return
        if not (item.flags() & Qt.ItemIsUserCheckable):
            return
        self._tm_enabled[tm_path] = item.checkState() == Qt.Checked

    def _update_tm_action_state(self) -> None:
        if self._tm_resolve_btn is None:
            return
        has_pending = False
        for idx in range(self._tm_list.count()):
            item = self._tm_list.item(idx)
            if item is None:
                continue
            if bool(item.data(_TM_IS_PENDING_ROLE)):
                has_pending = True
                break
            status = str(item.data(_TM_STATUS_ROLE) or "").strip().lower()
            if status and status != "ready":
                has_pending = True
                break
        self._tm_resolve_btn.setEnabled(has_pending)

    def _request_tm_resolve_pending(self) -> None:
        self._tm_resolve_pending = True
        self.accept()

    def _request_tm_export(self) -> None:
        self._tm_export_tmx = True
        self.accept()

    def _request_tm_rebuild(self) -> None:
        self._tm_rebuild = True
        self.accept()

    def _request_tm_diagnostics(self) -> None:
        self._tm_show_diagnostics = True
        self.accept()

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
