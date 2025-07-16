from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QUndoStack

from translationzed_py.core import Entry, Status
from translationzed_py.core.commands import ChangeStatusCommand, EditValueCommand
from translationzed_py.core.model import ParsedFile

_HEADERS = ("Key", "Value", "Status")
_COLOR = {
    Status.UNTOUCHED: QColor("#2d2d2d"),  # dark grey text
    Status.TRANSLATED: QColor("#006400"),  # green
    Status.PROOFREAD: QColor("#004c99"),  # blue
}


class TranslationModel(QAbstractTableModel):
    """Qt model that backs the translation table, with undo/redo support."""

    def __init__(self, pf: ParsedFile):
        super().__init__()
        self._pf = pf
        self._entries = list(pf.entries)
        self._dirty = False

        # attach a QUndoStack lazily to the ParsedFile object
        if not hasattr(self._pf, "undo_stack"):
            self._pf.undo_stack = QUndoStack()  # type: ignore[attr-defined]

    # ---------------------------------------------------------------- helpers
    def _replace_entry(self, row: int, entry: Entry) -> None:
        """Called by EditValueCommand to swap immutable Entry objects."""
        self._entries[row] = entry
        idx = self.index(row, 1)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole])
        self._dirty = True

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
        if index.column() in (1, 2):  # Value & Status columns
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):  # noqa: N802
        if role != Qt.EditRole:
            return False

        col = index.column()
        row = index.row()
        e = self._entries[row]

        # ---- value edit ----------------------------------------------------
        if col == 1:
            e = self._entries[index.row()]
            if value != e.value:
                new_entry = Entry(e.key, str(value), Status.TRANSLATED, e.span)
                cmd = EditValueCommand(
                    self._pf,
                    index.row(),
                    e,
                    new_entry,
                    self,
                )
                self._pf.undo_stack.push(cmd)
                return True

        # ---- status edit ---------------------------------------------------
        if col == 2:
            try:
                st = Status[str(value).upper()]
            except KeyError:
                return False
            if st != e.status:
                cmd = ChangeStatusCommand(self._pf, row, st, self)
                self._pf.undo_stack.push(cmd)
                return True

        return False
