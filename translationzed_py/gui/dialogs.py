from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
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
