from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
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

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("The following files will be written:"))

        list_widget = QListWidget(self)
        list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        for item in files:
            list_widget.addItem(item)
        list_widget.setMaximumHeight(220)
        main_layout.addWidget(list_widget)

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


class ReplaceFilesDialog(QDialog):
    """Confirm replace-all across multiple files."""

    def __init__(self, files: Iterable[str], scope_label: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Replace in multiple files")
        self.setModal(True)
        self._confirmed = False

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(f"Replace matches in {scope_label} files:"))

        list_widget = QListWidget(self)
        list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        for item in files:
            list_widget.addItem(item)
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
