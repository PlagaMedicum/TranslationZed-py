from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from translationzed_py import __version__
from translationzed_py.core.project_scanner import LocaleMeta


class LocaleChooserDialog(QDialog):
    """Checkbox chooser for target locales."""

    def __init__(
        self,
        locales: Iterable[LocaleMeta],
        parent=None,
        *,
        preselected: Iterable[str] | None = None,
    ) -> None:
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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def selected_codes(self) -> list[str]:
        return [code for code, box in self._boxes.items() if box.isChecked()]

    def _rebuild_order(self) -> None:
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
        super().__init__(parent)
        self.setWindowTitle("Write original files")
        self.setModal(True)
        self._choice = "cancel"
        self._list = QListWidget(self)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(
            QLabel("Choose files to write to originals (checked = will be written):")
        )

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
        self._choice = choice
        self.accept()

    def choice(self) -> str:
        return self._choice

    def selected_files(self) -> list[str]:
        selected: list[str] = []
        for idx in range(self._list.count()):
            item = self._list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def _select_all(self) -> None:
        self._set_all_checks(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        self._set_all_checks(Qt.CheckState.Unchecked)

    def _set_all_checks(self, state: Qt.CheckState) -> None:
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
        return self._source_combo.currentText().strip()

    def target_locale(self) -> str:
        return self._target_combo.currentText().strip()

    def skip_all_requested(self) -> bool:
        return self._skip_all

    def _skip_all_now(self) -> None:
        self._skip_all = True
        self.reject()


class ReplaceFilesDialog(QDialog):
    """Confirm replace-all across multiple files."""

    def __init__(
        self,
        files: Iterable[str] | Iterable[tuple[str, int]],
        scope_label: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Replace in multiple files")
        self.setModal(True)
        self._confirmed = False

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(f"Replace matches in {scope_label} files:"))

        list_widget = QListWidget(self)
        list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        for item in files:
            if isinstance(item, tuple) and len(item) == 2:
                path, count = item
                list_widget.addItem(f"{path} ({count})")
            else:
                list_widget.addItem(str(item))
        list_widget.setMaximumHeight(240)
        main_layout.addWidget(list_widget)

        buttons = QDialogButtonBox(self)
        btn_replace = buttons.addButton("Replace", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_replace.clicked.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _confirm(self) -> None:
        self._confirmed = True
        self.accept()

    def confirmed(self) -> bool:
        return self._confirmed


class ConflictChoiceDialog(QDialog):
    """Prompt when cached drafts conflict with current file values."""

    def __init__(self, file_label: str, count: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Translation conflict")
        self.setModal(True)
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
        self._choice = choice
        self.accept()

    def choice(self) -> str | None:
        return self._choice

    def reject(self) -> None:  # noqa: N802
        if self._choice is None:
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._choice is None:
            event.ignore()
            return
        super().closeEvent(event)


class AboutDialog(QDialog):
    """About dialog with GPL notice and license text."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About TranslationZed-Py")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
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
        self._license_text.setVisible(False)
        layout.addWidget(self._license_text)

        def _toggle_license(checked: bool) -> None:
            self._license_text.setVisible(checked)
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

        toggle.toggled.connect(_toggle_license)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _read_license(self) -> str:
        try:
            root = Path(__file__).resolve().parents[2]
            return (root / "LICENSE").read_text(encoding="utf-8")
        except Exception:
            return "License text not available."
