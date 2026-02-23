"""Entry model module."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QPalette, QUndoStack
from PySide6.QtWidgets import QApplication

from translationzed_py.core import Entry, Status
from translationzed_py.core.model import STATUS_ORDER, ParsedFile
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
_ROW_KIND_BASE = "base"
_ROW_KIND_VIRTUAL = "virtual"
_STATUS_PRIORITY = {status: idx for idx, status in enumerate(STATUS_ORDER)}
DIFF_MARKER_ROLE = int(Qt.UserRole) + 41
_DIFF_MARKER_TOOLTIP = {
    "NEW": "NEW in EN (missing in locale)",
    "REMOVED": "Present in locale (missing in EN)",
    "MODIFIED": "EN source changed since snapshot baseline",
}


@dataclass(frozen=True, slots=True)
class VirtualNewRow:
    """Represent one EN-only virtual row exposed in the table."""

    key: str
    source: str
    value: str = ""


@dataclass(frozen=True, slots=True)
class _RowRef:
    """Represent one displayed row reference."""

    kind: Literal["base", "virtual"]
    index: int | None = None
    key: str = ""


class TranslationModel(QAbstractTableModel):
    """Qt model that backs the translation table, with undo/redo support."""

    def __init__(
        self,
        pf: ParsedFile,
        *,
        baseline_by_row: dict[int, str] | None = None,
        source_values: Mapping[str, str] | None = None,
        source_by_row: Sequence[str] | None = None,
        diff_marker_by_key: Mapping[str, str] | None = None,
        virtual_new_rows: Sequence[VirtualNewRow] | None = None,
        virtual_new_edited_keys: Iterable[str] | None = None,
        en_order_keys: Sequence[str] | None = None,
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
        self._diff_marker_by_key: dict[str, str] = {}
        self._virtual_new_rows_by_key: dict[str, VirtualNewRow] = {}
        self._virtual_new_order: list[str] = []
        self._virtual_new_edited_keys: set[str] = set()
        self._en_order_keys = tuple(
            key for key in (str(raw).strip() for raw in (en_order_keys or ())) if key
        )
        self._status_filter: set[Status] | None = None
        self._status_sort_enabled = False
        self._row_refs: list[_RowRef] = []
        self._set_diff_markers(diff_marker_by_key or {})
        self._set_virtual_new_rows(
            virtual_new_rows or (),
            edited_keys=virtual_new_edited_keys,
        )
        self._rebuild_row_refs()
        self._preview_limit: int | None = None
        self._max_value_len: int | None = None
        self._headers = list(_HEADERS)

        self.undo_stack = QUndoStack()

    def _set_diff_markers(self, marker_by_key: Mapping[str, str]) -> None:
        self._diff_marker_by_key = {}
        for raw_key, raw_marker in marker_by_key.items():
            key = str(raw_key).strip()
            marker = str(raw_marker).strip().upper()
            if not key or not marker:
                continue
            self._diff_marker_by_key[key] = marker

    def _set_virtual_new_rows(
        self,
        rows: Sequence[VirtualNewRow],
        *,
        edited_keys: Iterable[str] | None = None,
    ) -> None:
        self._virtual_new_rows_by_key = {}
        self._virtual_new_order = []
        for raw in rows:
            key = str(raw.key).strip()
            if not key or key in self._virtual_new_rows_by_key:
                continue
            row = VirtualNewRow(
                key=key,
                source=str(raw.source or ""),
                value=str(raw.value or ""),
            )
            self._virtual_new_rows_by_key[key] = row
            self._virtual_new_order.append(key)
            if row.value:
                self._virtual_new_edited_keys.add(key)
        if edited_keys is not None:
            known = set(self._virtual_new_rows_by_key)
            self._virtual_new_edited_keys = {
                key for key in (str(raw).strip() for raw in edited_keys) if key in known
            }
        else:
            self._virtual_new_edited_keys.intersection_update(
                self._virtual_new_rows_by_key
            )
        for key in self._virtual_new_order:
            self._diff_marker_by_key.setdefault(key, "NEW")
        self._recompute_dirty_state()

    def apply_diff_state(
        self,
        *,
        marker_by_key: Mapping[str, str],
        virtual_new_rows: Sequence[VirtualNewRow],
        en_order_keys: Sequence[str] | None = None,
        edited_virtual_new_keys: Iterable[str] | None = None,
    ) -> None:
        """Apply EN-diff marker/virtual-row state and rebuild row mapping."""
        self.beginResetModel()
        self._set_diff_markers(marker_by_key)
        if en_order_keys is not None:
            self._en_order_keys = tuple(
                key for key in (str(raw).strip() for raw in en_order_keys) if key
            )
        self._set_virtual_new_rows(
            virtual_new_rows,
            edited_keys=edited_virtual_new_keys,
        )
        self._rebuild_row_refs()
        self.endResetModel()

    # ---------------------------------------------------------------- helpers
    def _recompute_dirty_state(self) -> None:
        self._dirty = bool(self._baseline_by_row or self._virtual_new_edited_keys)
        self._pf.dirty = self._dirty

    def _status_for_ref(self, ref: _RowRef) -> Status:
        if ref.kind == _ROW_KIND_BASE and ref.index is not None:
            return self._entries[ref.index].status
        return Status.UNTOUCHED

    def _row_ref(self, row: int) -> _RowRef | None:
        if 0 <= row < len(self._row_refs):
            return self._row_refs[row]
        return None

    def _base_index_for_row(self, row: int) -> int | None:
        ref = self._row_ref(row)
        if ref is None or ref.kind != _ROW_KIND_BASE:
            return None
        return ref.index

    def _virtual_row_for_row(self, row: int) -> VirtualNewRow | None:
        ref = self._row_ref(row)
        if ref is None or ref.kind != _ROW_KIND_VIRTUAL:
            return None
        return self._virtual_new_rows_by_key.get(ref.key)

    def _rebuild_row_refs(self) -> None:
        refs: list[_RowRef] = []
        base_index_by_key: dict[str, int] = {}
        for idx, entry in enumerate(self._entries):
            base_index_by_key.setdefault(entry.key, idx)
        used_base: set[int] = set()
        used_virtual: set[str] = set()

        if self._en_order_keys:
            for key in self._en_order_keys:
                base_idx = base_index_by_key.get(key)
                if base_idx is not None and base_idx not in used_base:
                    refs.append(_RowRef(kind=_ROW_KIND_BASE, index=base_idx))
                    used_base.add(base_idx)
                    continue
                if key in self._virtual_new_rows_by_key and key not in used_virtual:
                    refs.append(_RowRef(kind=_ROW_KIND_VIRTUAL, key=key))
                    used_virtual.add(key)

        for idx in range(len(self._entries)):
            if idx in used_base:
                continue
            refs.append(_RowRef(kind=_ROW_KIND_BASE, index=idx))

        for key in self._virtual_new_order:
            if key in used_virtual:
                continue
            refs.append(_RowRef(kind=_ROW_KIND_VIRTUAL, key=key))

        if self._status_filter is not None:
            refs = [
                ref for ref in refs if self._status_for_ref(ref) in self._status_filter
            ]

        if self._status_sort_enabled:
            indexed = list(enumerate(refs))
            indexed.sort(
                key=lambda pair: (
                    _STATUS_PRIORITY.get(self._status_for_ref(pair[1]), 99),
                    pair[0],
                )
            )
            refs = [ref for _idx, ref in indexed]

        self._row_refs = refs

    def set_status_filter(self, statuses: Iterable[Status] | None) -> None:
        """Set optional row visibility filter by status values."""
        normalized: set[Status] | None
        if statuses is None:
            normalized = None
        else:
            candidate = {status for status in statuses if isinstance(status, Status)}
            normalized = candidate or None
        if normalized == self._status_filter:
            return
        self.beginResetModel()
        self._status_filter = normalized
        self._rebuild_row_refs()
        self.endResetModel()

    def status_filter(self) -> set[Status] | None:
        """Return active status filter."""
        if self._status_filter is None:
            return None
        return set(self._status_filter)

    def set_status_sort_enabled(self, enabled: bool) -> None:
        """Enable/disable status-priority sort order."""
        next_enabled = bool(enabled)
        if next_enabled == self._status_sort_enabled:
            return
        self.beginResetModel()
        self._status_sort_enabled = next_enabled
        self._rebuild_row_refs()
        self.endResetModel()

    def status_sort_enabled(self) -> bool:
        """Return whether status-priority sorting is active."""
        return self._status_sort_enabled

    def has_pending_virtual_new_values(self) -> bool:
        """Return true when edited virtual NEW rows have unsaved draft values."""
        return bool(self._virtual_new_edited_keys)

    def edited_virtual_new_values(self) -> dict[str, str]:
        """Return edited virtual NEW rows for insertion/save-time preview."""
        return {
            key: self._virtual_new_rows_by_key[key].value
            for key in self._virtual_new_order
            if key in self._virtual_new_edited_keys
            and key in self._virtual_new_rows_by_key
        }

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

    def _row_background_color(self, row: int, column: int) -> QColor | None:
        base_index = self._base_index_for_row(row)
        if base_index is not None:
            return self._cell_background(base_index, column, self._entries[base_index])
        virtual = self._virtual_row_for_row(row)
        if virtual is None:
            return None
        if column == 1 and not (virtual.source or ""):
            return self._missing_background_color()
        if column == 2 and not (virtual.value or ""):
            return self._missing_background_color()
        return self._status_background_color(Status.UNTOUCHED)

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
        prev_entry = self._entries[row]
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
        status_changed = prev_entry.status != entry.status
        if status_changed and (
            self._status_sort_enabled or self._status_filter is not None
        ):
            self.beginResetModel()
            self._rebuild_row_refs()
            self.endResetModel()
        else:
            for view_row, ref in enumerate(self._row_refs):
                if ref.kind != _ROW_KIND_BASE or ref.index != row:
                    continue
                left = self.index(view_row, 0)
                right = self.index(view_row, self.columnCount() - 1)
                self.dataChanged.emit(
                    left,
                    right,
                    [Qt.DisplayRole, Qt.EditRole, Qt.ForegroundRole, Qt.BackgroundRole],
                )
        if value_changed:
            self._recompute_dirty_state()

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
        ref = self._row_ref(row)
        if ref is None:
            return None
        if ref.kind == _ROW_KIND_BASE and ref.index is not None:
            return self._entries[ref.index].status
        if ref.kind == _ROW_KIND_VIRTUAL:
            return Status.UNTOUCHED
        return None

    def clear_changed_values(self, *, clear_virtual: bool = False) -> None:
        """Execute clear changed values."""
        self._baseline_by_row.clear()
        self._changed_rows.clear()
        self._status_touched_rows.clear()
        if clear_virtual:
            self._virtual_new_edited_keys.clear()
        self._recompute_dirty_state()

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
        if not self._row_refs:
            return
        top = self.index(0, 1)
        bottom = self.index(self.rowCount() - 1, 1)
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
        base_index = self._base_index_for_row(row)
        if base_index is not None:
            if self._source_by_row is not None and base_index < len(
                self._source_by_row
            ):
                return self._source_by_row[base_index] or ""
            return self._source_values.get(self._entries[base_index].key, "") or ""
        virtual = self._virtual_row_for_row(row)
        if virtual is None:
            return ""
        return virtual.source or ""

    def _full_value_text(self, row: int) -> str:
        """Execute full value text."""
        base_index = self._base_index_for_row(row)
        if base_index is not None:
            return self._entries[base_index].value or ""
        virtual = self._virtual_row_for_row(row)
        if virtual is None:
            return ""
        return virtual.value or ""

    def _source_length_at(self, row: int) -> int:
        """Execute source length at."""
        base_index = self._base_index_for_row(row)
        if base_index is None:
            text = self._full_source_text(row)
            return len(text) if text else 0
        if self._source_by_row is not None and base_index < len(self._source_by_row):
            source_row = self._source_by_row
            if hasattr(source_row, "length_at"):
                try:
                    return int(source_row.length_at(base_index))
                except Exception:
                    text = source_row[base_index]
                    return len(text) if text else 0
            text = source_row[base_index]
            return len(text) if text else 0
        text = self._source_values.get(self._entries[base_index].key, "")
        return len(text) if text else 0

    def _value_length_at(self, row: int) -> int:
        """Execute value length at."""
        base_index = self._base_index_for_row(row)
        if base_index is None:
            text = self._full_value_text(row)
            return len(text) if text else 0
        entries = self._entries
        if hasattr(entries, "meta_at"):
            try:
                meta = entries.meta_at(base_index)
                if meta.segments:
                    return sum(meta.segments)
            except Exception:
                text = entries[base_index].value
                return len(text) if text else 0
        text = entries[base_index].value
        return len(text) if text else 0

    def _preview_source_raw(self, row: int, limit: int) -> tuple[str, int]:
        """Execute preview source raw."""
        actual_len = self._source_length_at(row)
        base_index = self._base_index_for_row(row)
        if base_index is None:
            preview = self._full_source_text(row)
            return preview[:limit], actual_len
        if self._source_by_row is not None and base_index < len(self._source_by_row):
            source_row = self._source_by_row
            if hasattr(source_row, "preview_at"):
                try:
                    preview = source_row.preview_at(base_index, limit)
                    return preview[:limit], actual_len
                except Exception:
                    preview = ""
                    return preview, actual_len
            preview = source_row[base_index] or ""
            return preview[:limit], actual_len
        preview = self._source_values.get(self._entries[base_index].key, "") or ""
        return preview[:limit], actual_len

    def _preview_source(self, row: int, limit: int) -> str:
        """Execute preview source."""
        preview, actual_len = self._preview_source_raw(row, limit)
        return self._truncate_preview(preview, limit, actual_len)

    def _preview_value_raw(self, row: int, limit: int) -> tuple[str, int]:
        """Execute preview value raw."""
        base_index = self._base_index_for_row(row)
        if base_index is None:
            preview = self._full_value_text(row)
            return preview[:limit], len(preview)
        entries = self._entries
        actual_len = self._value_length_at(row)
        if hasattr(entries, "preview_at"):
            try:
                preview = entries.preview_at(base_index, limit)
                return preview[:limit], actual_len
            except Exception:
                preview = ""
                return preview, actual_len
        preview = entries[base_index].value or ""
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

    def reset_baseline(self, *, clear_virtual: bool = False) -> None:
        """After writing to disk, treat current values as the new baseline."""
        self.clear_changed_values(clear_virtual=clear_virtual)

    def iter_search_rows(
        self, *, include_source: bool = True, include_value: bool = True
    ):
        """Yield search rows without going through QModelIndex lookups."""
        for idx, ref in enumerate(self._row_refs):
            if ref.kind == _ROW_KIND_BASE and ref.index is not None:
                entry = self._entries[ref.index]
                key = entry.key
                if include_source:
                    if self._source_by_row is not None and ref.index < len(
                        self._source_by_row
                    ):
                        source = self._source_by_row[ref.index]
                    else:
                        source = self._source_values.get(entry.key, "")
                else:
                    source = ""
                value = entry.value if include_value else ""
            else:
                virtual = self._virtual_new_rows_by_key.get(ref.key)
                if virtual is None:
                    continue
                key = virtual.key
                source = virtual.source if include_source else ""
                value = virtual.value if include_value else ""
            yield SearchRow(
                file=self._pf.path,
                row=idx,
                key=key,
                source=source,
                value=value,
            )

    def prefetch_rows(self, start: int, end: int) -> None:
        """Execute prefetch rows."""
        if hasattr(self._entries, "prefetch"):
            if not self._row_refs:
                self._entries.prefetch(start, end)
                return
            base_rows = [
                ref.index
                for ref in self._row_refs[max(0, start) : max(0, end) + 1]
                if ref.kind == _ROW_KIND_BASE and ref.index is not None
            ]
            if not base_rows:
                self._entries.prefetch(start, end)
                return
            self._entries.prefetch(min(base_rows), max(base_rows))

    # Qt mandatory overrides ----------------------------------------------------
    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        """Execute rowCount."""
        if parent and parent.isValid():
            return 0
        return len(self._row_refs)

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

        ref = self._row_ref(index.row())
        if ref is None:
            return None
        base_index = self._base_index_for_row(index.row())
        virtual = self._virtual_row_for_row(index.row())
        entry = self._entries[base_index] if base_index is not None else None
        key_text = entry.key if entry is not None else (virtual.key if virtual else "")
        status = entry.status if entry is not None else Status.UNTOUCHED
        marker = self._diff_marker_by_key.get(key_text)
        key_display = key_text

        if role == DIFF_MARKER_ROLE and index.column() == 0:
            return marker or None
        if role == Qt.TextAlignmentRole and index.column() == 0:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.ToolTipRole:
            match index.column():
                case 0:
                    if not key_text:
                        return ""
                    if marker:
                        label = _DIFF_MARKER_TOOLTIP.get(marker, marker)
                        return f"{label}\n{key_text}"
                    return key_text
                case 1:
                    return self._tooltip_source(index.row())
                case 2:
                    return self._tooltip_value(index.row())
                case 3:
                    return status.label()

        # --- display text ----------------------------------------------------
        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return key_display
                case 1:
                    if self._preview_limit:
                        return self._preview_source(index.row(), self._preview_limit)
                    if (
                        base_index is not None
                        and self._source_by_row is not None
                        and base_index < len(self._source_by_row)
                    ):
                        return self._source_by_row[base_index]
                    if base_index is not None and entry is not None:
                        return self._source_values.get(entry.key, "")
                    return virtual.source if virtual is not None else ""
                case 2:
                    if self._preview_limit:
                        return self._preview_value(index.row(), self._preview_limit)
                    if entry is not None:
                        return entry.value
                    return virtual.value if virtual is not None else ""
                case 3:
                    return status.label()

        if role == Qt.EditRole:
            match index.column():
                case 0:
                    return key_text
                case 1:
                    if (
                        base_index is not None
                        and self._source_by_row is not None
                        and base_index < len(self._source_by_row)
                    ):
                        return self._source_by_row[base_index]
                    if base_index is not None and entry is not None:
                        return self._source_values.get(entry.key, "")
                    return virtual.source if virtual is not None else ""
                case 2:
                    if entry is not None:
                        return entry.value
                    return virtual.value if virtual is not None else ""
                case 3:
                    return status

        # --- background highlights -------------------------------------------
        if role == Qt.BackgroundRole:
            return self._row_background_color(index.row(), index.column())

        if role == Qt.ForegroundRole:
            background = self._row_background_color(index.row(), index.column())
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
        ref = self._row_ref(index.row())
        if ref is None:
            return base
        if ref.kind == _ROW_KIND_VIRTUAL:
            if index.column() == 2:
                return base | Qt.ItemIsEditable
            return base
        if index.column() in (2, 3):  # Translation & Status columns
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):  # noqa: N802
        """Execute setData."""
        if role != Qt.EditRole:
            return False

        col = index.column()
        row = index.row()
        ref = self._row_ref(row)
        if ref is None:
            return False
        if ref.kind == _ROW_KIND_VIRTUAL:
            if col != 2:
                return False
            key = ref.key
            current_row = self._virtual_new_rows_by_key.get(key)
            if current_row is None:
                return False
            next_value = str(value)
            if next_value == current_row.value:
                return False
            self._virtual_new_rows_by_key[key] = VirtualNewRow(
                key=current_row.key,
                source=current_row.source,
                value=next_value,
            )
            self._virtual_new_edited_keys.add(key)
            self._recompute_dirty_state()
            left = self.index(row, 2)
            right = self.index(row, 3)
            self.dataChanged.emit(
                left,
                right,
                [Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole, Qt.ForegroundRole],
            )
            return True

        assert ref.index is not None
        base_row = ref.index
        e = self._entries[base_row]

        # ---- value edit ----------------------------------------------------
        if col == 2:
            e = self._entries[base_row]
            if value != e.value:
                if base_row not in self._baseline_by_row:
                    self._baseline_by_row[base_row] = e.value
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
                    base_row,
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
                cmd = ChangeStatusCommand(self._pf, base_row, st, self)
                self.undo_stack.push(cmd)
                return True

        return False
