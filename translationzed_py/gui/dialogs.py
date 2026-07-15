"""Dialogs module."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from translationzed_py import __version__
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.search_replace_service import ReplaceAllImpactPreview


class LocaleChooserDialog(QDialog):
    """Checkbox chooser for target locales."""

    def __init__(
        self,
        locales: Iterable[LocaleMeta],
        parent=None,
        *,
        preselected: Iterable[str] | None = None,
        on_add_locale: Callable[[], LocaleMeta | None] | None = None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle("Select locales")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(520)
        preselected_set = set(preselected or [])

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Choose locales to edit:"))

        list_widget = QWidget(self)
        self._list_layout = QVBoxLayout(list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)

        self._boxes: dict[str, QCheckBox] = {}
        self._items: list[tuple[str, QCheckBox]] = []
        for meta in sorted(locales, key=lambda m: m.code):
            label = f"{meta.code} — {meta.display_name}"
            box = QCheckBox(label, self)
            box.setChecked(meta.code in preselected_set)
            box.stateChanged.connect(self._rebuild_order)
            self._boxes[meta.code] = box
            self._items.append((meta.code, box))
        self._rebuild_order()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(list_widget)
        main_layout.addWidget(scroll)

        if on_add_locale is not None:
            add_locale = QPushButton("Add localization…", self)
            add_locale.setObjectName("addLocalizationButton")

            def _add() -> None:
                meta = on_add_locale()
                if meta is None or meta.code in self._boxes:
                    return
                label = f"{meta.code} — {meta.display_name}"
                box = QCheckBox(label, self)
                box.setChecked(True)
                box.stateChanged.connect(self._rebuild_order)
                self._boxes[meta.code] = box
                self._items.append((meta.code, box))
                self._rebuild_order()

            add_locale.clicked.connect(_add)
            main_layout.addWidget(add_locale)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def selected_codes(self) -> list[str]:
        """Execute selected codes."""
        return [code for code, box in self._boxes.items() if box.isChecked()]

    def _rebuild_order(self) -> None:
        """Execute rebuild order."""
        checked = {code for code, box in self._items if box.isChecked()}
        ordered = sorted(
            self._items,
            key=lambda pair: (0 if pair[0] in checked else 1, pair[0]),
        )
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        for _, box in ordered:
            self._list_layout.addWidget(box)
        self._list_layout.addStretch(1)


class SaveFilesDialog(QDialog):
    """Prompt listing files that will be written to originals."""

    def __init__(self, files: Iterable[str], parent=None) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle("Write original files")
        self.setModal(True)
        self._choice = "cancel"
        self._list = QListWidget(self)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(
            QLabel("Choose files to write to originals (checked = will be written):")
        )
        cache_notice = QLabel(
            "Draft edits are auto-saved to cache by default while you work.\n"
            "Choose Write only when you want to update original files now."
        )
        cache_notice.setObjectName("saveCacheNoticeLabel")
        cache_notice.setWordWrap(True)
        main_layout.addWidget(cache_notice)

        self._list.setSelectionMode(QAbstractItemView.NoSelection)
        for item in files:
            row = QListWidgetItem(item)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked)
            self._list.addItem(row)
        self._list.setMaximumHeight(260)
        main_layout.addWidget(self._list)

        toggles_layout = QHBoxLayout()
        select_all = QToolButton(self)
        select_all.setText("All")
        select_all.clicked.connect(self._select_all)
        select_none = QToolButton(self)
        select_none.setText("None")
        select_none.clicked.connect(self._select_none)
        toggles_layout.addWidget(select_all)
        toggles_layout.addWidget(select_none)
        toggles_layout.addStretch(1)
        main_layout.addLayout(toggles_layout)

        buttons = QDialogButtonBox(self)
        btn_write = buttons.addButton("Write", QDialogButtonBox.AcceptRole)
        btn_cache = buttons.addButton("Cache only", QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_write.clicked.connect(lambda: self._set_choice("write"))
        btn_cache.clicked.connect(lambda: self._set_choice("cache"))
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _set_choice(self, choice: str) -> None:
        """Set choice."""
        self._choice = choice
        self.accept()

    def choice(self) -> str:
        """Execute choice."""
        return self._choice

    def selected_files(self) -> list[str]:
        """Execute selected files."""
        selected: list[str] = []
        for idx in range(self._list.count()):
            item = self._list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def _select_all(self) -> None:
        """Execute select all."""
        self._set_all_checks(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        """Execute select none."""
        self._set_all_checks(Qt.CheckState.Unchecked)

    def _set_all_checks(self, state: Qt.CheckState) -> None:
        """Set all checks."""
        for idx in range(self._list.count()):
            self._list.item(idx).setCheckState(state)


class TmLanguageDialog(QDialog):
    """Pick source/target locale pair for TM import/export."""

    def __init__(
        self,
        languages: Iterable[str],
        parent=None,
        *,
        default_source: str | None = None,
        default_target: str | None = None,
        title: str = "TM language pair",
        allow_skip_all: bool = False,
    ) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._skip_all = False
        langs = sorted({lang for lang in languages if lang})
        if not langs:
            langs = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select source/target languages:"))

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox(self)
        self._source_combo.setEditable(True)
        self._source_combo.addItems(langs)
        source_row.addWidget(self._source_combo)
        layout.addLayout(source_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target:"))
        self._target_combo = QComboBox(self)
        self._target_combo.setEditable(True)
        self._target_combo.addItems(langs)
        target_row.addWidget(self._target_combo)
        layout.addLayout(target_row)

        if default_source:
            self._source_combo.setCurrentText(default_source)
        if default_target:
            self._target_combo.setCurrentText(default_target)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        if allow_skip_all:
            skip_btn = buttons.addButton(
                "Skip all for now", QDialogButtonBox.ActionRole
            )
            skip_btn.clicked.connect(self._skip_all_now)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def source_locale(self) -> str:
        """Execute source locale."""
        return self._source_combo.currentText().strip()

    def target_locale(self) -> str:
        """Execute target locale."""
        return self._target_combo.currentText().strip()

    def skip_all_requested(self) -> bool:
        """Execute skip all requested."""
        return self._skip_all

    def _skip_all_now(self) -> None:
        """Execute skip all now."""
        self._skip_all = True
        self.reject()


class ReplaceFilesDialog(QDialog):
    """Confirm replace-all across multiple files."""

    def __init__(
        self,
        files: Iterable[object],
        scope_label: str,
        *,
        total_matches: int,
        affected_files: int,
        impact_preview: ReplaceAllImpactPreview | None = None,
        scope_options: Sequence[tuple[str, str]] = (),
        selected_scope: str | None = None,
        on_scope_changed: Callable[[str], object | None] | None = None,
        parent=None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle("Confirm Replace All")
        self.setModal(True)
        self._confirmed = False
        self._selected_scope = str(selected_scope or "").upper()
        self._on_scope_changed = on_scope_changed
        self._has_replacements = int(total_matches) > 0
        self.setMinimumSize(980, 620)

        main_layout = QVBoxLayout(self)
        if scope_options:
            scope_layout = QHBoxLayout()
            scope_layout.addWidget(QLabel("Replace scope", self))
            self._scope_combo = QComboBox(self)
            for label, value in scope_options:
                self._scope_combo.addItem(str(label), str(value).upper())
            if self._selected_scope:
                for idx in range(self._scope_combo.count()):
                    if self._scope_combo.itemData(idx) == self._selected_scope:
                        self._scope_combo.setCurrentIndex(idx)
                        break
            else:
                self._selected_scope = str(
                    self._scope_combo.currentData() or ""
                ).upper()
            self._scope_combo.currentIndexChanged.connect(self._scope_selection_changed)
            scope_layout.addWidget(self._scope_combo, 1)
            main_layout.addLayout(scope_layout)
        else:
            self._scope_combo = None

        self._summary = QLabel(self)
        self._summary.setWordWrap(True)
        main_layout.addWidget(self._summary)

        main_layout.addWidget(QLabel("Per-file replacement counts:", self))
        self._file_counts_list = QListWidget(self)
        self._file_counts_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._file_counts_list.setMaximumHeight(240)
        main_layout.addWidget(self._file_counts_list)

        main_layout.addWidget(
            QLabel("Impact preview (file, row, before, after):", self)
        )
        self._preview_table = QTableWidget(0, 4, self)
        self._preview_table.setHorizontalHeaderLabels(
            ("File", "Row", "Before", "After")
        )
        self._preview_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview_table.verticalHeader().setVisible(False)
        header = self._preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._preview_table.setMinimumHeight(260)
        self._preview_table.setMaximumHeight(420)
        main_layout.addWidget(self._preview_table)

        self._confirm_checkbox = QCheckBox(
            "I reviewed the replacement list and impact preview.", self
        )
        self._confirm_checkbox.stateChanged.connect(
            lambda _state: self._sync_replace_enabled()
        )
        main_layout.addWidget(self._confirm_checkbox)
        self._truncation_label = QLabel(self)
        self._truncation_label.setWordWrap(True)
        self._truncation_label.setVisible(False)
        main_layout.addWidget(self._truncation_label)

        buttons = QDialogButtonBox(self)
        self._replace_button = buttons.addButton("Replace", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._replace_button.setEnabled(False)
        self._replace_button.clicked.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)
        self._set_replace_payload(
            files=tuple(files),
            scope_label=scope_label,
            total_matches=total_matches,
            affected_files=affected_files,
            impact_preview=impact_preview,
        )

    def _set_replace_payload(
        self,
        *,
        files: Sequence[object],
        scope_label: str,
        total_matches: int,
        affected_files: int,
        impact_preview: ReplaceAllImpactPreview | None,
    ) -> None:
        self._has_replacements = int(total_matches) > 0
        self._summary.setText(
            f"Scope: {scope_label}\n"
            f"Total replacements: {max(0, int(total_matches))}\n"
            f"Affected files: {max(0, int(affected_files))}"
        )
        self._file_counts_list.clear()
        for item in files:
            if isinstance(item, tuple) and len(item) == 2:
                path, count = item
                self._file_counts_list.addItem(f"{path} ({count})")
            else:
                self._file_counts_list.addItem(str(item))
        preview_rows = () if impact_preview is None else impact_preview.rows
        self._preview_table.setRowCount(len(preview_rows))
        for idx, row in enumerate(preview_rows):
            self._preview_table.setItem(idx, 0, QTableWidgetItem(str(row.file)))
            self._preview_table.setItem(
                idx, 1, QTableWidgetItem(str(max(1, int(row.row))))
            )
            self._preview_table.setItem(
                idx, 2, QTableWidgetItem(_clip_preview_text(str(row.before), limit=140))
            )
            self._preview_table.setItem(
                idx, 3, QTableWidgetItem(_clip_preview_text(str(row.after), limit=140))
            )
        if impact_preview is not None and impact_preview.truncated:
            self._truncation_label.setText(
                "Preview truncated: "
                f"{impact_preview.rendered_rows} shown, {impact_preview.omitted_rows} omitted."
            )
            self._truncation_label.setVisible(True)
        else:
            self._truncation_label.setText("")
            self._truncation_label.setVisible(False)
        self._sync_replace_enabled()

    def _scope_selection_changed(self) -> None:
        if self._scope_combo is None:
            return
        scope = str(self._scope_combo.currentData() or "").upper()
        if not scope or scope == self._selected_scope:
            return
        self._selected_scope = scope
        self._confirmed = False
        self._confirm_checkbox.setChecked(False)
        if self._on_scope_changed is None:
            self._sync_replace_enabled()
            return
        payload = self._on_scope_changed(scope)
        if not isinstance(payload, dict):
            self._has_replacements = False
            self._sync_replace_enabled()
            return
        self._set_replace_payload(
            files=payload.get("files", ()),
            scope_label=str(payload.get("scope_label", scope)),
            total_matches=int(payload.get("total_matches", 0)),
            affected_files=int(payload.get("affected_files", 0)),
            impact_preview=payload.get("impact_preview"),
        )

    def _sync_replace_enabled(self) -> None:
        """Enable Replace only after explicit checklist acknowledgement."""
        self._replace_button.setEnabled(
            self._confirm_checkbox.isChecked() and self._has_replacements
        )

    def _confirm(self) -> None:
        """Execute confirm."""
        if not self._confirm_checkbox.isChecked():
            return
        self._confirmed = True
        self.accept()

    def confirmed(self) -> bool:
        """Execute confirmed."""
        return self._confirmed

    def selected_scope(self) -> str:
        """Return the transient dialog-selected replace scope."""
        return self._selected_scope


def _clip_preview_text(text: str, *, limit: int = 80) -> str:
    """Clip preview text for compact dialog rendering."""
    if limit <= 0:
        return ""
    raw = str(text)
    if len(raw) <= limit:
        return raw
    if limit <= 3:
        return raw[:limit]
    return raw[: limit - 3] + "..."


class ConflictChoiceDialog(QDialog):
    """Prompt when cached drafts conflict with current file values."""

    def __init__(self, file_label: str, count: int, parent=None) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle("Translation conflict")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self._choice: str | None = None

        layout = QVBoxLayout(self)
        label = QLabel(
            "Cached drafts conflict with the current file values:\n"
            f"{file_label}\n"
            f"Conflicts: {count}",
            self,
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        buttons = QDialogButtonBox(self)
        btn_drop_cache = buttons.addButton("Drop cache", QDialogButtonBox.ActionRole)
        btn_drop_orig = buttons.addButton("Drop original", QDialogButtonBox.ActionRole)
        btn_merge = buttons.addButton("Merge…", QDialogButtonBox.AcceptRole)
        btn_drop_cache.clicked.connect(lambda: self._set_choice("drop_cache"))
        btn_drop_orig.clicked.connect(lambda: self._set_choice("drop_original"))
        btn_merge.clicked.connect(lambda: self._set_choice("merge"))
        layout.addWidget(buttons)

    def _set_choice(self, choice: str) -> None:
        """Set choice."""
        self._choice = choice
        self.accept()

    def choice(self) -> str | None:
        """Execute choice."""
        return self._choice

    def reject(self) -> None:  # noqa: N802
        """Execute reject."""
        if self._choice is None:
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Execute closeEvent."""
        if self._choice is None:
            event.ignore()
            return
        super().closeEvent(event)


class AboutDialog(QDialog):
    """About dialog with GPL notice and license text."""

    def __init__(self, parent=None) -> None:
        """Initialize the instance."""
        super().__init__(parent)
        self.setWindowTitle("About TranslationZed-Py")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(280)
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(QLabel(f"<b>TranslationZed-Py</b> v{__version__}", self))
        desc = QLabel(
            "CAT tool for Project Zomboid translators, by translators. Created with Python.",
            self,
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        link = QLabel(
            '<a href="https://github.com/PlagaMedicum/TranslationZed-py">'
            "GitHub: TranslationZed-py"
            "</a>",
            self,
        )
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        layout.addWidget(
            QLabel(
                "Licensed under GNU GPLv3. This program comes with ABSOLUTELY NO WARRANTY.",
                self,
            )
        )
        toggle = QToolButton(self)
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.RightArrow)
        toggle.setText("View License")
        layout.addWidget(toggle)

        self._license_text = QPlainTextEdit(self)
        self._license_text.setReadOnly(True)
        self._license_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._license_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._license_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._license_text.setPlainText(self._read_license())
        self._license_text.setMaximumHeight(250)
        self._license_text.setVisible(False)
        layout.addWidget(self._license_text)

        def _toggle_license(checked: bool) -> None:
            """Execute toggle license."""
            self._license_text.setVisible(checked)
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

        toggle.toggled.connect(_toggle_license)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def _read_license(self) -> str:
        """Read license."""
        try:
            root = Path(__file__).resolve().parents[2]
            return (root / "LICENSE").read_text(encoding="utf-8")
        except Exception:
            return "License text not available."
