from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor

from translationzed_py.core import Entry, Status

_HEADERS = ("Key", "Value", "Status")
_COLOR = {
    Status.UNTOUCHED: QColor("#2d2d2d"),  # dark grey text
    Status.TRANSLATED: QColor("#006400"),  # green
    Status.PROOFREAD: QColor("#004c99"),  # blue
}


class TranslationModel(QAbstractTableModel):
    def __init__(self, entries: Sequence[Entry]):
        super().__init__()
        self._entries = list(entries)
        self._dirty = False

    # Qt mandatory overrides ----------------------------------------------------
    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        if parent and parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        if parent and parent.isValid():
            return 0
        return 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        if not index.isValid():
            return None

        e = self._entries[index.row()]

        # --- display text ----------------------------------------------------
        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    return e.value
                case 2:
                    return e.status.name.title()

        # --- colour by status ------------------------------------------------
        if role == Qt.ForegroundRole:
            return _COLOR[e.status]

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int
    ):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _HEADERS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):  # noqa: N802
        base = super().flags(index)
        if index.column() == 1:  # Value column
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):  # noqa: N802
        if role == Qt.EditRole and index.column() == 1:
            e = self._entries[index.row()]
            if value != e.value:
                # replace Entry immutably
                self._entries[index.row()] = Entry(
                    e.key, str(value), Status.TRANSLATED, e.span
                )
                self.dataChanged.emit(index, index, [Qt.DisplayRole])
                self._dirty = True
            return True
        return False
