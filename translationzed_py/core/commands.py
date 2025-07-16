from __future__ import annotations

from typing import Any

from PySide6.QtGui import QUndoCommand

from .model import Entry, ParsedFile, Status


class EditValueCommand(QUndoCommand):
    """Undo-able value edit in the translation table."""

    def __init__(
        self,
        pf: ParsedFile,
        row: int,
        old_entry: Entry,
        new_entry: Entry,
        model: Any,  # TranslationModel
    ) -> None:
        super().__init__(f"Edit “{old_entry.key}”")
        self._pf, self._row = pf, row
        # keep immutable snapshots so undo truly restores the previous state
        self._old = Entry(
            old_entry.key,
            old_entry.value,
            old_entry.status,
            old_entry.span,
        )
        self._old, self._new = old_entry, new_entry
        self._model = model

    # ---- QUndoCommand -------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        self._apply(self._old)

    def redo(self) -> None:  # noqa: D401
        self._apply(self._new)

    # ---- helpers ------------------------------------------------------
    def _apply(self, entry: Entry) -> None:
        # Replace frozen Entry wholesale (no mutation)
        self._pf.entries[self._row] = entry
        self._model._replace_entry(self._row, entry)


class ChangeStatusCommand(QUndoCommand):
    """Undo-able status toggle."""

    def __init__(
        self,
        pf: ParsedFile,
        row: int,
        new_status: Status,
        model: Any,
    ) -> None:
        super().__init__("Change status")
        self._pf, self._row = pf, row
        self._prev = pf.entries[row].status
        self._new = new_status
        self._model = model

    # -------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        self._apply(self._prev)

    def redo(self) -> None:  # noqa: D401
        self._apply(self._new)

    def _apply(self, st: Status) -> None:
        e = self._pf.entries[self._row]
        self._pf.entries[self._row] = Entry(e.key, e.value, st, e.span)
        self._model._replace_entry(self._row, self._pf.entries[self._row])
