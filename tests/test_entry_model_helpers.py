"""Test module for additional entry model helper branches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from translationzed_py.core.model import Entry, ParsedFile, Status
from translationzed_py.gui.entry_model import TranslationModel


def _entry(
    key: str,
    value: str,
    *,
    status: Status = Status.UNTOUCHED,
) -> Entry:
    """Create a minimal immutable entry for model tests."""
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=None,
    )


def _parsed(entries) -> ParsedFile:  # type: ignore[no-untyped-def]
    """Create ParsedFile with test entries."""
    return ParsedFile(Path("/tmp/project/BE/ui.txt"), entries, b"")


def test_init_prefetch_replace_and_changed_row_helpers() -> None:
    """Verify prefetch entries, replace behavior, and changed-row tracking helpers."""

    class _Entries(list):
        """List-like entries with prefetch support."""

        def __init__(self, values) -> None:  # type: ignore[no-untyped-def]
            super().__init__(values)
            self.prefetch_calls: list[tuple[int, int]] = []

        def prefetch(self, start: int, end: int) -> None:
            """Capture prefetch range."""
            self.prefetch_calls.append((start, end))

    entries = _Entries([_entry("HELLO", "old"), _entry("", "")])
    model = TranslationModel(
        _parsed(entries),
        baseline_by_row={0: "old", 99: "x"},
        source_values={"HELLO": "src-hello"},
    )

    assert model._entries is entries
    model.prefetch_rows(3, 9)
    assert entries.prefetch_calls == [(3, 9)]

    replacement = _entry("HELLO", "old")
    model._replace_entry(0, replacement, value_changed=True)
    assert model._dirty is True
    assert model._pf.dirty is True
    assert model.changed_values() == {}
    assert model.changed_keys() == set()
    assert model.baseline_values() == {}

    status_entry = _entry("HELLO", "old", status=Status.PROOFREAD)
    model._replace_entry(0, status_entry, value_changed=False)
    rows = model.changed_rows_with_source()
    assert rows == [("HELLO", "src-hello", "old", int(Status.PROOFREAD))]
    assert model.status_for_row(200) is None

    missing_key_bg = model._cell_background(1, 0, entries[1])
    missing_source_bg = model._cell_background(0, 1, _entry("MISS", "ok"))
    missing_value_bg = model._cell_background(1, 2, entries[1])
    assert missing_key_bg is not None
    assert missing_source_bg is not None
    assert missing_value_bg is not None

    assert isinstance(model._dark_palette_active(), bool)


def test_dark_palette_active_without_qapp_and_source_lookup_empty_entries(monkeypatch) -> None:
    """Verify dark palette returns false without app and source lookup handles empties."""
    monkeypatch.setattr("translationzed_py.gui.entry_model.QApplication.instance", lambda: None)
    model = TranslationModel(_parsed([]))
    assert model._dark_palette_active() is False
    model.set_source_lookup(source_values={"A": "B"}, source_by_row=["B"])


def test_length_preview_and_tooltip_paths_cover_exception_and_fallback_branches() -> None:
    """Verify text-length, preview, and tooltip helpers handle exceptional inputs."""

    class _SourceRows:
        """Source rows stub with length/preview helpers that may fail."""

        def __init__(self, values: list[str], *, fail_length: bool, fail_preview: bool) -> None:
            self._values = values
            self._fail_length = fail_length
            self._fail_preview = fail_preview

        def __len__(self) -> int:
            return len(self._values)

        def __getitem__(self, index: int) -> str:
            return self._values[index]

        def length_at(self, index: int) -> int:
            if self._fail_length:
                raise RuntimeError("length error")
            return len(self._values[index])

        def preview_at(self, index: int, limit: int) -> str:
            if self._fail_preview:
                raise RuntimeError("preview error")
            return (self._values[index] + "ZZZ")[:limit]

    class _Entries(list):
        """Entries stub with optional meta/preview/max-length helpers."""

        def __init__(
            self,
            values,
            *,
            fail_meta: bool = False,
            fail_preview: bool = False,
            max_error: bool = False,
        ) -> None:  # type: ignore[no-untyped-def]
            super().__init__(values)
            self._fail_meta = fail_meta
            self._fail_preview = fail_preview
            self._max_error = max_error

        def meta_at(self, index: int):  # type: ignore[no-untyped-def]
            if self._fail_meta:
                raise RuntimeError("meta error")
            return SimpleNamespace(segments=(len(self[index].value),))

        def preview_at(self, index: int, limit: int) -> str:
            if self._fail_preview:
                raise RuntimeError("preview error")
            return (self[index].value + "YYY")[:limit]

        def max_value_length(self) -> int:
            if self._max_error:
                raise RuntimeError("max error")
            return 123

        def prefetch(self, _start: int, _end: int) -> None:
            """Expose prefetch so TranslationModel keeps this instance as-is."""

    src_rows = _SourceRows(["alpha", "beta"], fail_length=True, fail_preview=True)
    entries = _Entries([_entry("A", "value")], fail_meta=True, fail_preview=True)
    model = TranslationModel(_parsed(entries), source_by_row=src_rows)

    assert model.text_lengths(-1) == (0, 0)
    assert model.text_lengths(0) == (0, 0)
    assert model._source_length_at(0) == len("alpha")
    assert model._value_length_at(0) == len("value")
    assert model._preview_source_raw(0, 4) == ("", len("alpha"))
    assert model._preview_source(0, 4) == "…"
    assert model._preview_value_raw(0, 4) == ("", len("value"))
    assert model._preview_value(0, 4) == "…"

    assert model._truncate_preview("abc", 0, None) == ""
    assert model._truncate_preview("abc", 3, None) == "abc"
    assert model._truncate_preview("abcdef", 3, 3) == "abcdef"
    assert model._truncate_preview("abcdef", 3, 9).endswith("…")

    assert model._tooltip_limit_for_length(0) is None
    assert model._tooltip_limit_for_length(9000) == 200
    assert model._tooltip_limit_for_length(900) == 800
    assert model._tooltip_limit_for_length(20) is None

    assert model._tooltip_apply_limit("", 10, 5) == ""
    assert model._tooltip_apply_limit("ok", 2, None) == "ok"
    assert model._tooltip_apply_limit("ok", 2, 3) == "ok"
    assert model._tooltip_apply_limit("abcdef", 6, 3) == "abc\n...(truncated)"

    model._source_by_row = None
    model._source_values = {"A": "source-text"}
    assert model._full_source_text(0) == "source-text"
    assert model._full_value_text(0) == "value"
    assert model._source_length_at(0) == len("source-text")
    assert model._preview_source_raw(0, 6) == ("source", len("source-text"))
    assert model._tooltip_source(0) == "source-text"
    assert model._tooltip_value(0) == "value"

    entries_with_meta = _Entries([_entry("B", "longer-text")], fail_meta=False)
    model_with_meta = TranslationModel(_parsed(entries_with_meta))
    assert model_with_meta.max_value_length() == 123
    assert model_with_meta.max_value_length() == 123

    failing_max_entries = _Entries([_entry("C", "x")], max_error=True)
    model_failing_max = TranslationModel(_parsed(failing_max_entries))
    assert model_failing_max.max_value_length() == 0

    class _MetaOnly(list):
        """Entries stub exposing only meta_at for max-length computation."""

        def meta_at(self, index: int):  # type: ignore[no-untyped-def]
            if index == 0:
                return SimpleNamespace(segments=(2, 3))
            raise RuntimeError("skip")

        def prefetch(self, _start: int, _end: int) -> None:
            """Expose prefetch so TranslationModel keeps this instance as-is."""

    meta_only = _MetaOnly([_entry("D", "abcde"), _entry("E", "")])
    model_meta_only = TranslationModel(_parsed(meta_only))
    assert model_meta_only.max_value_length() == 5


def test_data_header_and_setdata_branches(qapp) -> None:
    """Verify data accessors, header writes, and setData branch behavior."""
    _ = qapp
    model = TranslationModel(_parsed([_entry("K1", "value1", status=Status.TRANSLATED)]))
    model._source_values = {"K1": "source1"}

    assert model.data(QModelIndex()) is None

    key_index = model.index(0, 0)
    src_index = model.index(0, 1)
    val_index = model.index(0, 2)
    status_index = model.index(0, 3)

    assert model.data(key_index, role=Qt.ToolTipRole) == "K1"
    assert model.data(src_index, role=Qt.ToolTipRole) == "source1"
    assert model.data(val_index, role=Qt.ToolTipRole) == "value1"
    assert model.data(status_index, role=Qt.ToolTipRole) == "Translated"

    model.set_preview_limit(4)
    assert model.data(src_index, role=Qt.DisplayRole).endswith("…")

    model._source_by_row = None
    assert model.data(src_index, role=Qt.EditRole) == "source1"

    assert model.setHeaderData(0, Qt.Horizontal, "Key", role=Qt.DisplayRole) is True
    assert model.setHeaderData(0, Qt.Vertical, "ignored", role=Qt.DisplayRole) is False

    assert model.setData(val_index, "ignored", role=Qt.DisplayRole) is False
    assert model.setData(val_index, "value1", role=Qt.EditRole) is False
    assert model.setData(val_index, "value2", role=Qt.EditRole) is True
    assert model._baseline_by_row[0] == "value1"

    assert model.setData(status_index, "not-a-status", role=Qt.EditRole) is False
    assert model.setData(status_index, Status.TRANSLATED, role=Qt.EditRole) is False
    assert model.setData(status_index, Status.PROOFREAD, role=Qt.EditRole) is True

    parent = model.index(0, 0)
    assert model.rowCount(parent) == 0
    assert model.columnCount(parent) == 0


def test_tooltip_paths_with_large_content_use_limiting_logic(qapp) -> None:
    """Verify tooltip helpers limit very large source/value text lengths."""
    _ = qapp
    long_source = "s" * 1200
    long_value = "v" * 6000
    model = TranslationModel(_parsed([_entry("L", long_value)]), source_values={"L": long_source})

    source_tip = model._tooltip_source(0)
    value_tip = model._tooltip_value(0)

    assert source_tip.endswith("...(truncated)")
    assert value_tip.endswith("...(truncated)")

    app = QApplication.instance()
    assert app is not None
    palette = app.palette()
    assert isinstance(palette, QPalette)


def test_remaining_entry_model_source_and_preview_success_paths() -> None:
    """Verify remaining source/value length and preview success branches."""

    class _SourceRows:
        """Source rows with both preview_at and direct-index access."""

        def __init__(self, values: list[str]) -> None:
            self._values = values

        def __len__(self) -> int:
            return len(self._values)

        def __getitem__(self, index: int) -> str:
            return self._values[index]

        def preview_at(self, index: int, limit: int) -> str:
            return self._values[index][:limit]

    class _Entries(list):
        """Entries exposing meta_at/preview_at success paths."""

        def meta_at(self, index: int):  # type: ignore[no-untyped-def]
            return SimpleNamespace(segments=(2, 3) if index == 0 else ())

        def preview_at(self, index: int, limit: int) -> str:
            return (self[index].value or "")[:limit]

        def prefetch(self, _start: int, _end: int) -> None:
            """Keep entry collection attached in model initialization."""

    source_rows = _SourceRows(["source-a", "source-b"])
    entries = _Entries([_entry("A", "value-a"), _entry("B", "value-b")])
    model = TranslationModel(_parsed(entries), source_by_row=source_rows)

    model._source_values = {"A": "fallback-source"}
    model._source_by_row = None
    assert model.text_lengths(0) == (len("fallback-source"), 5)
    assert model.iter_search_rows().__next__().source == "fallback-source"

    model._source_by_row = source_rows
    assert model._full_source_text(0) == "source-a"
    assert model._source_length_at(1) == len("source-b")
    assert model._value_length_at(0) == 5
    assert model._preview_source_raw(0, 4) == ("sour", len("source-a"))
    assert model._preview_source_raw(1, 4) == ("sour", len("source-b"))
    assert model._preview_value_raw(0, 4) == ("valu", 5)

    entries_with_no_value = _Entries([_entry("C", "")])
    model_empty = TranslationModel(_parsed(entries_with_no_value), source_values={"C": ""})
    assert model_empty._tooltip_source(0) == ""
    assert model_empty._tooltip_value(0) == ""

    model_dark = TranslationModel(_parsed([_entry("D", "")]))
    model_dark._dark_palette_active = lambda: True  # type: ignore[method-assign]
    assert model_dark._missing_background_color() is not None
