from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from translationzed_py.core.project_scanner import LocaleMeta


class LocaleChooserDialog(QDialog):
    """Checkbox chooser for target locales."""

    def __init__(self, locales: Iterable[LocaleMeta], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select locales")
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Choose locales to edit:"))

        list_widget = QWidget(self)
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self._boxes: dict[str, QCheckBox] = {}
        for meta in sorted(locales, key=lambda m: m.code):
            label = f"{meta.code} — {meta.display_name}"
            box = QCheckBox(label, self)
            box.setChecked(False)
            self._boxes[meta.code] = box
            list_layout.addWidget(box)

        list_layout.addStretch(1)
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
