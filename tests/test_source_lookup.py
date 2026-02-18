"""Test module for source lookup helpers."""

from __future__ import annotations

from translationzed_py.core.model import Entry, Status
from translationzed_py.gui.source_lookup import LazySourceRows, SourceLookup


def _entry(key: str, value: str) -> Entry:
    return Entry(
        key=key, value=value, status=Status.UNTOUCHED, span=(0, 0), segments=(), gaps=()
    )


def test_source_lookup_builds_map_from_rows_and_keys() -> None:
    """Verify row-backed lookup builds by-key map with shared-length guard."""
    lookup = SourceLookup(by_row=["One", "Two"], keys=["K1"], by_key=None)

    assert lookup.by_row == ["One", "Two"]
    assert lookup.get("K1") == "One"
    assert lookup["missing"] == ""
    assert list(iter(lookup)) == ["K1"]
    assert len(lookup) == 1


def test_source_lookup_handles_empty_backing_and_explicit_map() -> None:
    """Verify lookup handles no backing rows and explicit by-key dictionaries."""
    empty_lookup = SourceLookup()
    assert len(empty_lookup) == 0
    assert empty_lookup.get("K", "default") == "default"

    explicit_lookup = SourceLookup(by_key={"A": "Alpha"})
    assert explicit_lookup.get("A") == "Alpha"
    assert list(explicit_lookup) == ["A"]


class _Meta:
    """Simple test metadata holder."""

    def __init__(self, segments: tuple[int, ...]) -> None:
        self.segments = segments


class _EntriesWithMeta(list[Entry]):
    """Entry list exposing ``meta_at`` for lazy-length branches."""

    def __init__(self, entries: list[Entry], segments: tuple[int, ...]) -> None:
        super().__init__(entries)
        self._segments = segments

    def meta_at(self, idx: int) -> _Meta:
        """Return fake metadata."""
        _ = idx
        return _Meta(self._segments)


class _EntriesMetaError(list[Entry]):
    """Entry list whose ``meta_at`` raises to test defensive fallback."""

    def meta_at(self, idx: int) -> _Meta:
        """Raise metadata read failure."""
        _ = idx
        raise RuntimeError("meta failure")


class _EntriesWithPreview(list[Entry]):
    """Entry list exposing ``preview_at`` for lazy-preview branches."""

    def preview_at(self, idx: int, limit: int) -> str:
        """Return precomputed preview."""
        _ = idx, limit
        return "preview"


class _EntriesPreviewError(list[Entry]):
    """Entry list whose ``preview_at`` raises to test fallback path."""

    def preview_at(self, idx: int, limit: int) -> str:
        """Raise preview failure."""
        _ = idx, limit
        raise RuntimeError("preview failure")


def test_lazy_source_rows_indexing_and_plain_fallback_paths() -> None:
    """Verify lazy rows handle index/slice and plain entry fallback behavior."""
    rows = LazySourceRows([_entry("A", "Alpha"), _entry("B", "")])

    assert len(rows) == 2
    assert rows[0] == "Alpha"
    assert rows[:2] == ["Alpha", ""]
    assert rows.length_at(0) == 5
    assert rows.length_at(1) == 0
    assert rows.preview_at(0, 2) == "Al"
    assert rows.preview_at(0, 0) == ""
    assert rows.preview_at(1, 2) == ""


def test_lazy_source_rows_meta_and_preview_extension_paths() -> None:
    """Verify lazy rows consume optional meta/preview APIs when available."""
    with_meta = LazySourceRows(_EntriesWithMeta([_entry("A", "Alpha")], (2, 3)))
    assert with_meta.length_at(0) == 5

    with_empty_meta = LazySourceRows(_EntriesWithMeta([_entry("A", "Alpha")], ()))
    assert with_empty_meta.length_at(0) == 0

    with_meta_error = LazySourceRows(_EntriesMetaError([_entry("A", "Alpha")]))
    assert with_meta_error.length_at(0) == 0

    with_preview = LazySourceRows(_EntriesWithPreview([_entry("A", "Alpha")]))
    assert with_preview.preview_at(0, 3) == "preview"

    with_preview_error = LazySourceRows(_EntriesPreviewError([_entry("A", "Alpha")]))
    assert with_preview_error.preview_at(0, 3) == ""
