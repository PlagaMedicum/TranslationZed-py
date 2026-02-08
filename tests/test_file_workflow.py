from __future__ import annotations

from dataclasses import dataclass

from translationzed_py.core.file_workflow import (
    FileWorkflowService,
    apply_cache_for_write,
    apply_cache_overlay,
)
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.status_cache import CacheEntry, CacheMap


@dataclass(frozen=True, slots=True)
class _Meta:
    key: str
    status: Status
    span: tuple[int, int]
    segments: tuple[int, ...]
    gaps: tuple[bytes, ...]
    raw: bool
    key_hash: int


class _IndexedEntries:
    def __init__(
        self,
        entries: list[Entry],
        metas: list[_Meta],
        by_hash16: dict[int, list[int]],
    ) -> None:
        self._entries = entries
        self._metas = metas
        self._by_hash16 = by_hash16

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> Entry:
        return self._entries[index]

    def __setitem__(self, index: int, entry: Entry) -> None:
        self._entries[index] = entry

    def __iter__(self):
        return iter(self._entries)

    def meta_at(self, index: int) -> _Meta:
        return self._metas[index]

    def index_by_hash(self, *, bits: int = 64) -> dict[int, list[int]]:
        if bits == 16:
            return self._by_hash16
        return {}


def _entry(key: str, value: str, status: Status, key_hash: int = 1) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=key_hash,
    )


def test_apply_cache_overlay_fallback_tracks_drafts_and_conflicts() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=11),
        _entry("B", "file-b", Status.UNTOUCHED, key_hash=22),
    ]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")
    cache[2] = CacheEntry(Status.PROOFREAD, None, None)

    result = apply_cache_overlay(
        entries,
        cache,
        hash_for_entry=lambda entry: 1 if entry.key == "A" else 2,
    )

    assert result.changed_keys == {"A"}
    assert result.baseline_by_row == {0: "file-a"}
    assert result.conflict_originals == {"A": "file-a"}
    assert result.original_values == {"A": "orig-a"}
    assert entries[0].value == "draft-a"
    assert entries[0].status == Status.TRANSLATED
    assert entries[0].key_hash == 11
    assert entries[1].status == Status.PROOFREAD


def test_apply_cache_overlay_uses_indexed_lookup_for_hash_bits() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=111),
        _entry("B", "file-b", Status.UNTOUCHED, key_hash=222),
    ]
    metas = [
        _Meta("A", Status.UNTOUCHED, (0, 0), (), (), False, 111),
        _Meta("B", Status.UNTOUCHED, (0, 0), (), (), False, 222),
    ]
    indexed_entries = _IndexedEntries(entries, metas, by_hash16={5: [1]})
    cache = CacheMap(hash_bits=16)
    cache[5] = CacheEntry(Status.TRANSLATED, "draft-b", "orig-b")

    result = apply_cache_overlay(
        indexed_entries,
        cache,
        hash_for_entry=lambda _entry: 0,
    )

    assert result.changed_keys == {"B"}
    assert result.baseline_by_row == {1: "file-b"}
    assert result.conflict_originals == {"B": "file-b"}
    assert indexed_entries[1].value == "draft-b"
    assert indexed_entries[1].status == Status.TRANSLATED
    assert indexed_entries[1].key_hash == 222


def test_apply_cache_for_write_returns_changed_values_and_statuses() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=31),
        _entry("B", "file-b", Status.PROOFREAD, key_hash=32),
    ]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.FOR_REVIEW, "draft-a", "orig-a")
    cache[2] = CacheEntry(Status.TRANSLATED, None, None)

    result = apply_cache_for_write(
        entries,
        cache,
        hash_for_entry=lambda entry: 1 if entry.key == "A" else 2,
    )

    assert result.changed_values == {"A": "draft-a"}
    assert result.entries[0].status == Status.FOR_REVIEW
    assert result.entries[0].value == "file-a"
    assert result.entries[1].status == Status.TRANSLATED
    assert result.entries[1].value == "file-b"
    assert result.entries[0].key_hash == 31


def test_file_workflow_service_wraps_overlay_helpers() -> None:
    service = FileWorkflowService()
    entries = [_entry("A", "file-a", Status.UNTOUCHED, key_hash=11)]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")

    overlay = service.apply_cache_overlay(
        entries,
        cache,
        hash_for_entry=lambda _entry: 1,
    )
    write_overlay = service.apply_cache_for_write(
        entries,
        cache,
        hash_for_entry=lambda _entry: 1,
    )

    assert overlay.changed_keys == {"A"}
    assert write_overlay.changed_values == {"A": "draft-a"}
