"""Entry model module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QPalette, QUndoStack
from PySide6.QtWidgets import QApplication

from translationzed_py.core import Entry, Status
from translationzed_py.core.model import ParsedFile
from translationzed_py.core.search import SearchRow
from translationzed_py.gui.commands import ChangeStatusCommand, EditValueCommand

_HEADERS = ("Key", "Source", "Translation", "Status")
_BG_STATUS_LIGHT = {
    Status.TRANSLATED: QColor("#ccffcc"),
    Status.PROOFREAD: QColor("#cce5ff"),
    Status.FOR_REVIEW: QColor("#ffd8a8"),
}
_BG_STATUS_DARK = {
    Status.TRANSLATED: QColor("#1f4629"),
    Status.PROOFREAD: QColor("#203a57"),
    Status.FOR_REVIEW: QColor("#543717"),
}
_BG_MISSING_LIGHT = QColor("#ffcccc")
_BG_MISSING_DARK = QColor("#7a2f2f")
_FG_LIGHT_BG = QColor("#111111")
_FG_DARK_BG = QColor("#f1f1f1")
_TOOLTIP_LIMIT = 800
_TOOLTIP_LIMIT_LARGE = 200
_TOOLTIP_LARGE_THRESHOLD = 5000


class TranslationModel(QAbstractTableModel):
    """Qt model that backs the translation table, with undo/redo support."""

    def __init__(
        self,
        pf: ParsedFile,
        *,
        baseline_by_row: dict[int, str] | None = None,
        source_values: Mapping[str, str] | None = None,
        source_by_row: Sequence[str] | None = None,
    ):
        """Initialize the instance."""
        super().__init__()
        self._pf = pf
        if hasattr(pf.entries, "prefetch"):
            self._entries = pf.entries
        else:
            self._entries = list(pf.entries)
        self._source_values = source_values or {}
        self._source_by_row = source_by_row
        self._baseline_by_row = dict(baseline_by_row or {})
        self._changed_rows: set[int] = set(self._baseline_by_row)
        self._status_touched_rows: set[int] = set()
        self._dirty = bool(self._baseline_by_row)
        self._pf.dirty = self._dirty
        self._preview_limit: int | None = None
        self._max_value_len: int | None = None
        self._headers = list(_HEADERS)

        self.undo_stack = QUndoStack()

    # ---------------------------------------------------------------- helpers
    def _dark_palette_active(self) -> bool:
        """Execute dark palette active."""
        app = QApplication.instance()
        if app is None:
            return False
        palette = app.palette()
        base = palette.color(QPalette.Base)
        text = palette.color(QPalette.Text)
        return text.lightness() > base.lightness()

    def _status_background_color(self, status: Status) -> QColor | None:
        """Execute status background color."""
        if self._dark_palette_active():
            return _BG_STATUS_DARK.get(status)
        return _BG_STATUS_LIGHT.get(status)

    def _missing_background_color(self) -> QColor:
        """Execute missing background color."""
        if self._dark_palette_active():
            return _BG_MISSING_DARK
        return _BG_MISSING_LIGHT

    def _foreground_for_background(self, background: QColor) -> QColor:
        # Keep readable text regardless of status color brightness.
        """Execute foreground for background."""
        return _FG_LIGHT_BG if background.lightness() >= 145 else _FG_DARK_BG

    def _cell_background(self, row: int, column: int, entry: Entry) -> QColor | None:
        """Execute cell background."""
        if column == 0 and not (entry.key or ""):
            return self._missing_background_color()
        if column == 1:
            if self._source_by_row is not None and row < len(self._source_by_row):
                source_text = self._source_by_row[row]
            else:
                source_text = self._source_values.get(entry.key, "")
            if not (source_text or ""):
                return self._missing_background_color()
        if column == 2 and not (entry.value or ""):
            return self._missing_background_color()
        return self._status_background_color(entry.status)

    def _replace_entry(self, row: int, entry: Entry, *, value_changed: bool) -> None:
        """Swap immutable Entry objects during value/status updates."""
        self._entries[row] = entry
        if value_changed:
            baseline = self._baseline_by_row.get(row)
            if baseline is not None and entry.value == baseline:
                self._baseline_by_row.pop(row, None)
                self._changed_rows.discard(row)
            else:
                if baseline is not None:
                    self._changed_rows.add(row)
        else:
            # Status-only edits should propagate to TM metadata updates.
            self._status_touched_rows.add(row)
        left = self.index(row, 0)
        right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(
            left,
            right,
            [Qt.DisplayRole, Qt.EditRole, Qt.ForegroundRole, Qt.BackgroundRole],
        )
        if value_changed:
            self._dirty = bool(self._baseline_by_row)
            self._pf.dirty = self._dirty

    def changed_values(self) -> dict[str, str]:
        """Return only values that were edited (no status-only changes)."""
        out = {}
        for row in self._baseline_by_row:
            if 0 <= row < len(self._entries):
                e = self._entries[row]
                out[e.key] = e.value
        return out

    def changed_rows_with_source(self) -> list[tuple[str, str, str, int]]:
        """Return (key, source, value, status) for value/status touched rows."""
        out: list[tuple[str, str, str, int]] = []
        touched_rows = set(self._baseline_by_row)
        touched_rows.update(self._status_touched_rows)
        for row in touched_rows:
            if 0 <= row < len(self._entries):
                e = self._entries[row]
                source_text = ""
                if self._source_by_row is not None and row < len(self._source_by_row):
                    source_text = self._source_by_row[row]
                else:
                    source_text = self._source_values.get(e.key, "")
                value_text = "" if e.value is None else str(e.value)
                out.append((e.key, source_text, value_text, int(e.status)))
        return out

    def changed_keys(self) -> set[str]:
        """Execute changed keys."""
        keys: set[str] = set()
        for row in self._baseline_by_row:
            if 0 <= row < len(self._entries):
                keys.add(self._entries[row].key)
        return keys

    def text_lengths(self, row: int) -> tuple[int, int]:
        """Return (source_len, value_len) without forcing lazy decode when possible."""
        if not (0 <= row < len(self._entries)):
            return 0, 0
        source_len = 0
        if self._source_by_row is not None and row < len(self._source_by_row):
            source_row = self._source_by_row
            if hasattr(source_row, "length_at"):
                try:
                    source_len = int(source_row.length_at(row))
                except Exception:
                    source_len = 0
            else:
                source_text = source_row[row]
                source_len = len(source_text) if source_text else 0
        else:
            source_text = self._source_values.get(self._entries[row].key, "")
            source_len = len(source_text) if source_text else 0

        value_len = 0
        entries = self._entries
        if hasattr(entries, "meta_at"):
            try:
                meta = entries.meta_at(row)
                if meta.segments:
                    value_len = sum(meta.segments)
            except Exception:
                value_len = 0
        else:
            value_text = self._entries[row].value
            value_len = len(value_text) if value_text else 0
        return source_len, value_len

    def baseline_values(self) -> dict[str, str]:
        """Return original values for rows that currently track edits."""
        out: dict[str, str] = {}
        for row, baseline in self._baseline_by_row.items():
            if 0 <= row < len(self._entries):
                out[self._entries[row].key] = baseline
        return out

    def status_for_row(self, row: int) -> Status | None:
        """Execute status for row."""
        if 0 <= row < len(self._entries):
            return self._entries[row].status
        return None

    def clear_changed_values(self) -> None:
        """Execute clear changed values."""
        self._baseline_by_row.clear()
        self._changed_rows.clear()
        self._status_touched_rows.clear()
        self._dirty = False
        self._pf.dirty = False

    def set_preview_limit(self, limit: int | None) -> None:
        """Set preview limit."""
        self._preview_limit = limit

    def set_source_lookup(
        self,
        *,
        source_values: Mapping[str, str] | None = None,
        source_by_row: Sequence[str] | None = None,
    ) -> None:
        """Set source lookup."""
        self._source_values = source_values or {}
        self._source_by_row = source_by_row
        if not self._entries:
            return
        top = self.index(0, 1)
        bottom = self.index(len(self._entries) - 1, 1)
        self.dataChanged.emit(
            top,
            bottom,
            [Qt.DisplayRole, Qt.EditRole, Qt.ToolTipRole],
        )

    def max_value_length(self) -> int:
        """Execute max value length."""
        cached = self._max_value_len
        if cached is not None:
            return cached
        max_len = 0
        entries = self._entries
        if hasattr(entries, "max_value_length"):
            try:
                max_len = int(entries.max_value_length())
            except Exception:
                max_len = 0
        elif hasattr(entries, "meta_at"):
            for idx in range(len(entries)):
                try:
                    meta = entries.meta_at(idx)
                except Exception:
                    continue
                if meta.segments:
                    max_len = max(max_len, sum(meta.segments))
        else:
            for entry in entries:
                if entry.value:
                    max_len = max(max_len, len(entry.value))
        self._max_value_len = max_len
        return max_len

    def _truncate_preview(self, text: str, limit: int, actual_len: int | None) -> str:
        """Execute truncate preview."""
        if limit <= 0:
            return ""
        if actual_len is None:
            if len(text) <= limit:
                return text
        else:
            if actual_len <= limit:
                return text
        return text[: max(0, limit - 1)] + "…"

    def _tooltip_limit_for_length(self, length: int) -> int | None:
        """Execute tooltip limit for length."""
        if length <= 0:
            return None
        if length > _TOOLTIP_LARGE_THRESHOLD:
            return _TOOLTIP_LIMIT_LARGE
        if length > _TOOLTIP_LIMIT:
            return _TOOLTIP_LIMIT
        return None

    def _tooltip_apply_limit(
        self, text: str, actual_len: int, limit: int | None
    ) -> str:
        """Execute tooltip apply limit."""
        if not text:
            return ""
        if limit is None:
            return text
        truncated = text[:limit]
        if actual_len <= limit:
            return text
        return truncated + "\n...(truncated)"

    def _full_source_text(self, row: int) -> str:
        """Execute full source text."""
        if self._source_by_row is not None and row < len(self._source_by_row):
            return self._source_by_row[row] or ""
        return self._source_values.get(self._entries[row].key, "") or ""

    def _full_value_text(self, row: int) -> str:
        """Execute full value text."""
        return self._entries[row].value or ""

    def _source_length_at(self, row: int) -> int:
        """Execute source length at."""
        if self._source_by_row is not None and row < len(self._source_by_row):
            source_row = self._source_by_row
            if hasattr(source_row, "length_at"):
                try:
                    return int(source_row.length_at(row))
                except Exception:
                    text = source_row[row]
                    return len(text) if text else 0
            text = source_row[row]
            return len(text) if text else 0
        text = self._source_values.get(self._entries[row].key, "")
        return len(text) if text else 0

    def _value_length_at(self, row: int) -> int:
        """Execute value length at."""
        entries = self._entries
        if hasattr(entries, "meta_at"):
            try:
                meta = entries.meta_at(row)
                if meta.segments:
                    return sum(meta.segments)
            except Exception:
                text = entries[row].value
                return len(text) if text else 0
        text = entries[row].value
        return len(text) if text else 0

    def _preview_source_raw(self, row: int, limit: int) -> tuple[str, int]:
        """Execute preview source raw."""
        actual_len = self._source_length_at(row)
        if self._source_by_row is not None and row < len(self._source_by_row):
            source_row = self._source_by_row
            if hasattr(source_row, "preview_at"):
                try:
                    preview = source_row.preview_at(row, limit)
                    return preview[:limit], actual_len
                except Exception:
                    preview = ""
                    return preview, actual_len
            preview = source_row[row] or ""
            return preview[:limit], actual_len
        preview = self._source_values.get(self._entries[row].key, "") or ""
        return preview[:limit], actual_len

    def _preview_source(self, row: int, limit: int) -> str:
        """Execute preview source."""
        preview, actual_len = self._preview_source_raw(row, limit)
        return self._truncate_preview(preview, limit, actual_len)

    def _preview_value_raw(self, row: int, limit: int) -> tuple[str, int]:
        """Execute preview value raw."""
        entries = self._entries
        actual_len = self._value_length_at(row)
        if hasattr(entries, "preview_at"):
            try:
                preview = entries.preview_at(row, limit)
                return preview[:limit], actual_len
            except Exception:
                preview = ""
                return preview, actual_len
        preview = entries[row].value or ""
        return preview[:limit], actual_len or len(preview)

    def _preview_value(self, row: int, limit: int) -> str:
        """Execute preview value."""
        preview, actual_len = self._preview_value_raw(row, limit)
        return self._truncate_preview(preview, limit, actual_len)

    def _tooltip_source(self, row: int) -> str:
        """Execute tooltip source."""
        actual_len = self._source_length_at(row)
        if actual_len <= 0:
            return ""
        limit = self._tooltip_limit_for_length(actual_len)
        if limit is None:
            return self._full_source_text(row)
        preview, _ = self._preview_source_raw(row, limit)
        return self._tooltip_apply_limit(preview, actual_len, limit)

    def _tooltip_value(self, row: int) -> str:
        """Execute tooltip value."""
        actual_len = self._value_length_at(row)
        if actual_len <= 0:
            return ""
        limit = self._tooltip_limit_for_length(actual_len)
        if limit is None:
            return self._full_value_text(row)
        preview, _ = self._preview_value_raw(row, limit)
        return self._tooltip_apply_limit(preview, actual_len, limit)

    def reset_baseline(self) -> None:
        """After writing to disk, treat current values as the new baseline."""
        self.clear_changed_values()

    def iter_search_rows(
        self, *, include_source: bool = True, include_value: bool = True
    ):
        """Yield search rows without going through QModelIndex lookups."""
        for idx, entry in enumerate(self._entries):
            if include_source:
                if self._source_by_row is not None and idx < len(self._source_by_row):
                    source = self._source_by_row[idx]
                else:
                    source = self._source_values.get(entry.key, "")
            else:
                source = ""
            value = entry.value if include_value else ""
            yield SearchRow(
                file=self._pf.path,
                row=idx,
                key=entry.key,
                source=source,
                value=value,
            )

    def prefetch_rows(self, start: int, end: int) -> None:
        """Execute prefetch rows."""
        if hasattr(self._entries, "prefetch"):
            self._entries.prefetch(start, end)

    # Qt mandatory overrides ----------------------------------------------------
    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        """Execute rowCount."""
        if parent and parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        """Execute columnCount."""
        if parent and parent.isValid():
            return 0
        return 4

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        """Execute data."""
        if not index.isValid():
            return None

        e = self._entries[index.row()]

        if role == Qt.TextAlignmentRole and index.column() == 0:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.ToolTipRole:
            match index.column():
                case 0:
                    return e.key or ""
                case 1:
                    return self._tooltip_source(index.row())
                case 2:
                    return self._tooltip_value(index.row())
                case 3:
                    return e.status.label()

        # --- display text ----------------------------------------------------
        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    if self._preview_limit:
                        return self._preview_source(index.row(), self._preview_limit)
                    if self._source_by_row is not None and index.row() < len(
                        self._source_by_row
                    ):
                        return self._source_by_row[index.row()]
                    return self._source_values.get(e.key, "")
                case 2:
                    if self._preview_limit:
                        return self._preview_value(index.row(), self._preview_limit)
                    return e.value
                case 3:
                    return e.status.label()

        if role == Qt.EditRole:
            match index.column():
                case 0:
                    return e.key
                case 1:
                    if self._source_by_row is not None and index.row() < len(
                        self._source_by_row
                    ):
                        return self._source_by_row[index.row()]
                    return self._source_values.get(e.key, "")
                case 2:
                    return e.value
                case 3:
                    return e.status

        # --- background highlights -------------------------------------------
        if role == Qt.BackgroundRole:
            return self._cell_background(index.row(), index.column(), e)

        if role == Qt.ForegroundRole:
            background = self._cell_background(index.row(), index.column(), e)
            if background is None:
                return None
            return self._foreground_for_background(background)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int
    ):  # noqa: N802
        """Execute headerData."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def setHeaderData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        value,
        role: int = Qt.EditRole,
    ) -> bool:
        """Execute setHeaderData."""
        if (
            orientation == Qt.Horizontal
            and role == Qt.DisplayRole
            and 0 <= section < len(self._headers)
        ):
            text = str(value or "")
            if self._headers[section] == text:
                return True
            self._headers[section] = text
            self.headerDataChanged.emit(orientation, section, section)
            return True
        return super().setHeaderData(section, orientation, value, role)

    def flags(self, index: QModelIndex):  # noqa: N802
        """Execute flags."""
        base = super().flags(index)
        if index.column() in (2, 3):  # Translation & Status columns
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):  # noqa: N802
        """Execute setData."""
        if role != Qt.EditRole:
            return False

        col = index.column()
        row = index.row()
        e = self._entries[row]

        # ---- value edit ----------------------------------------------------
        if col == 2:
            e = self._entries[index.row()]
            if value != e.value:
                if row not in self._baseline_by_row:
                    self._baseline_by_row[row] = e.value
                new_entry = Entry(
                    e.key,
                    str(value),
                    Status.TRANSLATED,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                    e.key_hash,
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
                    st = Status[str(value).upper().replace(" ", "_")]
                except KeyError:
                    return False
            if st != e.status:
                cmd = ChangeStatusCommand(self._pf, row, st, self)
                self.undo_stack.push(cmd)
                return True

        return False
