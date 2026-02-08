from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .model import Entry, EntrySequence
from .status_cache import CacheEntry


@dataclass(frozen=True, slots=True)
class CacheOverlayResult:
    changed_keys: set[str]
    baseline_by_row: dict[int, str]
    conflict_originals: dict[str, str]
    original_values: dict[str, str]


@dataclass(frozen=True, slots=True)
class CacheWriteOverlay:
    entries: list[Entry]
    changed_values: dict[str, str]


@dataclass(frozen=True, slots=True)
class FileWorkflowService:
    def apply_cache_overlay(
        self,
        entries: EntrySequence,
        cache_map: Mapping[int, CacheEntry],
        *,
        hash_for_entry: Callable[[Entry], int],
    ) -> CacheOverlayResult:
        return apply_cache_overlay(
            entries,
            cache_map,
            hash_for_entry=hash_for_entry,
        )

    def apply_cache_for_write(
        self,
        entries: Iterable[Entry],
        cache_map: Mapping[int, CacheEntry],
        *,
        hash_for_entry: Callable[[Entry], int],
    ) -> CacheWriteOverlay:
        return apply_cache_for_write(
            entries,
            cache_map,
            hash_for_entry=hash_for_entry,
        )


def apply_cache_overlay(
    entries: EntrySequence,
    cache_map: Mapping[int, CacheEntry],
    *,
    hash_for_entry: Callable[[Entry], int],
) -> CacheOverlayResult:
    changed_keys: set[str] = set()
    baseline_by_row: dict[int, str] = {}
    conflict_originals: dict[str, str] = {}
    original_values: dict[str, str] = {}
    if not cache_map:
        return CacheOverlayResult(
            changed_keys=changed_keys,
            baseline_by_row=baseline_by_row,
            conflict_originals=conflict_originals,
            original_values=original_values,
        )

    if hasattr(entries, "index_by_hash") and hasattr(entries, "meta_at"):
        hash_bits = getattr(cache_map, "hash_bits", 64)
        index_by_hash = entries.index_by_hash(bits=hash_bits)
        for key_hash, rec in cache_map.items():
            indices = index_by_hash.get(key_hash)
            if not indices:
                continue
            for idx in indices:
                meta = entries.meta_at(idx)
                file_value = entries[idx].value
                if (
                    rec.value is not None
                    and rec.original is not None
                    and rec.original != file_value
                ):
                    conflict_originals[meta.key] = file_value
                new_value = rec.value if rec.value is not None else file_value
                if rec.value is not None and rec.value != file_value:
                    changed_keys.add(meta.key)
                    baseline_by_row[idx] = file_value
                    original_values[meta.key] = (
                        rec.original if rec.original is not None else file_value
                    )
                if new_value != file_value or rec.status != meta.status:
                    entries[idx] = Entry(
                        meta.key,
                        new_value,
                        rec.status,
                        meta.span,
                        meta.segments,
                        meta.gaps,
                        meta.raw,
                        meta.key_hash,
                    )
        return CacheOverlayResult(
            changed_keys=changed_keys,
            baseline_by_row=baseline_by_row,
            conflict_originals=conflict_originals,
            original_values=original_values,
        )

    for idx, entry in enumerate(entries):
        key_hash = hash_for_entry(entry)
        rec_opt = cache_map.get(key_hash)
        if rec_opt is None:
            continue
        rec = rec_opt
        if (
            rec.value is not None
            and rec.original is not None
            and rec.original != entry.value
        ):
            conflict_originals[entry.key] = entry.value
        new_value = rec.value if rec.value is not None else entry.value
        if rec.value is not None and rec.value != entry.value:
            changed_keys.add(entry.key)
            baseline_by_row[idx] = entry.value
            original_values[entry.key] = (
                rec.original if rec.original is not None else entry.value
            )
        if new_value != entry.value or rec.status != entry.status:
            entries[idx] = type(entry)(
                entry.key,
                new_value,
                rec.status,
                entry.span,
                entry.segments,
                entry.gaps,
                entry.raw,
                getattr(entry, "key_hash", None),
            )
    return CacheOverlayResult(
        changed_keys=changed_keys,
        baseline_by_row=baseline_by_row,
        conflict_originals=conflict_originals,
        original_values=original_values,
    )


def apply_cache_for_write(
    entries: Iterable[Entry],
    cache_map: Mapping[int, CacheEntry],
    *,
    hash_for_entry: Callable[[Entry], int],
) -> CacheWriteOverlay:
    changed_values: dict[str, str] = {}
    new_entries: list[Entry] = []
    for entry in entries:
        key_hash = hash_for_entry(entry)
        rec_opt = cache_map.get(key_hash)
        if rec_opt is None:
            new_entries.append(entry)
            continue
        rec = rec_opt
        next_entry = entry
        if rec.status != entry.status:
            next_entry = type(entry)(
                entry.key,
                entry.value,
                rec.status,
                entry.span,
                entry.segments,
                entry.gaps,
                entry.raw,
                getattr(entry, "key_hash", None),
            )
        if rec.value is not None:
            changed_values[next_entry.key] = rec.value
        new_entries.append(next_entry)
    return CacheWriteOverlay(entries=new_entries, changed_values=changed_values)
