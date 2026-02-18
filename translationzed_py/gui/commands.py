"""Provide undo/redo command objects for table edits."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QUndoCommand

from translationzed_py.core.model import Entry, ParsedFile, Status


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
        """Initialize command snapshots for one value edit."""
        super().__init__(f"Edit “{old_entry.key}”")
        self._pf, self._row = pf, row
        # keep immutable snapshots so undo truly restores the previous state
        self._old = Entry(
            old_entry.key,
            old_entry.value,
            old_entry.status,
            old_entry.span,
            old_entry.segments,
            old_entry.gaps,
            old_entry.raw,
            old_entry.key_hash,
        )
        self._new = Entry(
            new_entry.key,
            new_entry.value,
            new_entry.status,
            new_entry.span,
            new_entry.segments,
            new_entry.gaps,
            new_entry.raw,
            new_entry.key_hash,
        )
        self._model = model

    # ---- QUndoCommand -------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        """Undo the value edit."""
        self._apply(self._old)

    def redo(self) -> None:  # noqa: D401
        """Redo the value edit."""
        self._apply(self._new)

    # ---- helpers ------------------------------------------------------
    def _apply(self, entry: Entry) -> None:
        # Replace frozen Entry wholesale (no mutation)
        self._pf.entries[self._row] = entry
        self._model._replace_entry(self._row, entry, value_changed=True)


class ChangeStatusCommand(QUndoCommand):
    """Undo-able status toggle."""

    def __init__(
        self,
        pf: ParsedFile,
        row: int,
        new_status: Status,
        model: Any,
    ) -> None:
        """Initialize command state for one status change."""
        super().__init__("Change status")
        self._pf, self._row = pf, row
        self._prev = pf.entries[row].status
        self._new = new_status
        self._model = model

    # -------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        """Undo the status change."""
        self._apply(self._prev)

    def redo(self) -> None:  # noqa: D401
        """Redo the status change."""
        self._apply(self._new)

    def _apply(self, st: Status) -> None:
        e = self._pf.entries[self._row]
        self._pf.entries[self._row] = Entry(
            e.key,
            e.value,
            st,
            e.span,
            e.segments,
            e.gaps,
            e.raw,
            e.key_hash,
        )
        self._model._replace_entry(
            self._row, self._pf.entries[self._row], value_changed=False
        )
