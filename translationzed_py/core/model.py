from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path

try:  # GUI runtime only; fall back for headless tests
    from PySide6.QtGui import QUndoStack  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in headless envs

    class QUndoStack:  # noqa: D101 - minimal fallback for non-GUI contexts
        def __init__(self) -> None:
            self._stack: list[object] = []
            self._index = 0

        def push(self, cmd: object) -> None:
            if self._index < len(self._stack):
                del self._stack[self._index :]
            self._stack.append(cmd)
            self._index += 1
            redo = getattr(cmd, "redo", None)
            if callable(redo):
                redo()

        def undo(self) -> None:
            if self._index == 0:
                return
            self._index -= 1
            cmd = self._stack[self._index]
            undo = getattr(cmd, "undo", None)
            if callable(undo):
                undo()

        def redo(self) -> None:
            if self._index >= len(self._stack):
                return
            cmd = self._stack[self._index]
            self._index += 1
            redo = getattr(cmd, "redo", None)
            if callable(redo):
                redo()

        def createUndoAction(self, *args, **kwargs):  # noqa: ANN001, D401
            raise RuntimeError("QUndoStack actions require PySide6.")


class Status(enum.IntEnum):
    UNTOUCHED = 0
    TRANSLATED = 1
    PROOFREAD = 2  # spec §5.3 :contentReference[oaicite:1]{index=1}


@dataclass(frozen=True, slots=True)
class Entry:
    key: str
    value: str
    status: Status
    span: tuple[int, int]  # byte offsets in raw file


class ParsedFile:
    def __init__(self, path: Path, entries: list[Entry], raw: bytes) -> None:
        self.path = path
        self.entries = entries
        self._raw = bytearray(raw)
        self.dirty = False
        self.undo_stack = QUndoStack()

    # read-only helpers
    def get_entry(self, key: str) -> Entry | None:
        return next((e for e in self.entries if e.key == key), None)

    def raw_bytes(self) -> bytes:  # round-trip tests will use this
        return bytes(self._raw)
