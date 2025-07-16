from __future__ import annotations
from typing import Sequence
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from translationzed_py.core import Entry, Status

_HEADERS = ("Key", "Value", "Status")

class TranslationModel(QAbstractTableModel):
    def __init__(self, entries: Sequence[Entry]):
        super().__init__()
        self._entries = list(entries)

    # Qt mandatory overrides ----------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:      # noqa: N802
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()) -> int:   # noqa: N802
        return 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.ToolTipRole):
            return None
        e = self._entries[index.row()]
        match index.column():
            case 0:
                return e.key
            case 1:
                return e.value
            case 2:
                return e.status.name.title()
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _HEADERS[section]
        return super().headerData(section, orientation, role)

