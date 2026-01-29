from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QUndoStack

from translationzed_py.core import Entry, Status
from translationzed_py.gui.commands import ChangeStatusCommand, EditValueCommand
from translationzed_py.core.model import ParsedFile

_HEADERS = ("Key", "Source", "Translation", "Status")
_BG = {
    Status.PROOFREAD: QColor("#ccffcc"),
}


class TranslationModel(QAbstractTableModel):
    """Qt model that backs the translation table, with undo/redo support."""

    def __init__(
        self,
        pf: ParsedFile,
        *,
        base_values: dict[str, str] | None = None,
        changed_keys: set[str] | None = None,
        source_values: dict[str, str] | None = None,
    ):
        super().__init__()
        self._pf = pf
        self._entries = list(pf.entries)
        self._source_values = source_values or {}
        self._base_values = base_values or {e.key: e.value for e in self._entries}
        self._changed_values: set[str] = set(changed_keys or set())
        self._dirty = bool(self._changed_values)
        self._pf.dirty = self._dirty

        self.undo_stack = QUndoStack()

    # ---------------------------------------------------------------- helpers
    def _replace_entry(self, row: int, entry: Entry, *, value_changed: bool) -> None:
        """Called by EditValueCommand to swap immutable Entry objects."""
        self._entries[row] = entry
        if value_changed:
            base_value = self._base_values.get(entry.key)
            if base_value is not None and entry.value == base_value:
                self._changed_values.discard(entry.key)
            else:
                self._changed_values.add(entry.key)
        left = self.index(row, 0)
        right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(
            left,
            right,
            [Qt.DisplayRole, Qt.EditRole, Qt.ForegroundRole, Qt.BackgroundRole],
        )
        if value_changed:
            self._dirty = bool(self._changed_values)
            self._pf.dirty = self._dirty

    def changed_values(self) -> dict[str, str]:
        """Return only values that were edited (no status-only changes)."""
        out = {}
        for e in self._entries:
            if e.key in self._changed_values:
                out[e.key] = e.value
        return out

    def changed_keys(self) -> set[str]:
        return set(self._changed_values)

    def status_for_row(self, row: int) -> Status | None:
        if 0 <= row < len(self._entries):
            return self._entries[row].status
        return None

    def clear_changed_values(self) -> None:
        self._changed_values.clear()
        self._dirty = False
        self._pf.dirty = False

    def reset_baseline(self) -> None:
        """After writing to disk, treat current values as the new baseline."""
        self._base_values = {e.key: e.value for e in self._entries}
        self.clear_changed_values()

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
        return 4

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        if not index.isValid():
            return None

        e = self._entries[index.row()]

        if role == Qt.TextAlignmentRole and index.column() == 0:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.ToolTipRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    return self._source_values.get(e.key, "")
                case 2:
                    return e.value
                case 3:
                    return e.status.name.title()

        # --- display text ----------------------------------------------------
        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    return self._source_values.get(e.key, "")
                case 2:
                    return e.value
                case 3:
                    return e.status.name.title()

        if role == Qt.EditRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    return self._source_values.get(e.key, "")
                case 2:
                    return e.value
                case 3:
                    return e.status

        # --- background by status --------------------------------------------
        if role == Qt.BackgroundRole:
            return _BG.get(e.status)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int
    ):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _HEADERS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):  # noqa: N802
        base = super().flags(index)
        if index.column() in (2, 3):  # Translation & Status columns
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):  # noqa: N802
        if role != Qt.EditRole:
            return False

        col = index.column()
        row = index.row()
        e = self._entries[row]

        # ---- value edit ----------------------------------------------------
        if col == 2:
            e = self._entries[index.row()]
            if value != e.value:
                new_entry = Entry(
                    e.key,
                    str(value),
                    Status.TRANSLATED,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
                cmd = EditValueCommand(
                    self._pf,
                    index.row(),
                    e,
                    new_entry,
                    self,
                )
                self.undo_stack.push(cmd)
                return True

        # ---- status edit ---------------------------------------------------
        if col == 3:
            if isinstance(value, Status):
                st = value
            else:
                try:
                    st = Status[str(value).upper()]
                except KeyError:
                    return False
            if st != e.status:
                cmd = ChangeStatusCommand(self._pf, row, st, self)
                self.undo_stack.push(cmd)
                return True

        return False
