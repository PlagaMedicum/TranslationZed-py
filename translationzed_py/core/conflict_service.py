from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .model import Entry, EntrySequence, Status


@dataclass(frozen=True, slots=True)
class ConflictMergeRow:
    key: str
    source_value: str
    original_value: str
    cache_value: str


@dataclass(frozen=True, slots=True)
class ConflictCachePlan:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]


@dataclass(frozen=True, slots=True)
class ConflictMergePlan:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]
    value_updates: dict[str, str]
    status_updates: dict[str, Status]


def build_merge_rows(
    entries: Sequence[Entry],
    conflict_originals: Mapping[str, str],
    sources: Mapping[str, str],
) -> tuple[list[ConflictMergeRow], dict[str, str]]:
    cache_values = {
        entry.key: entry.value for entry in entries if entry.key in conflict_originals
    }
    rows = [
        ConflictMergeRow(
            key=key,
            source_value=sources.get(key, ""),
            original_value=conflict_originals.get(key, ""),
            cache_value=cache_values.get(key, ""),
        )
        for key in sorted(conflict_originals)
    ]
    return rows, cache_values


def drop_cache_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_keys: Iterable[str],
) -> ConflictCachePlan:
    remaining_changed = set(changed_keys) - set(conflict_keys)
    return ConflictCachePlan(
        changed_keys=frozenset(remaining_changed),
        original_values=dict(baseline_values),
        force_original=frozenset(),
    )


def drop_original_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_originals: Mapping[str, str],
) -> ConflictCachePlan:
    originals = dict(baseline_values)
    originals.update(conflict_originals)
    return ConflictCachePlan(
        changed_keys=frozenset(changed_keys),
        original_values=originals,
        force_original=frozenset(conflict_originals),
    )


def merge_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_originals: Mapping[str, str],
    cache_values: Mapping[str, str],
    resolutions: Mapping[str, tuple[str, Literal["original", "cache"]]],
) -> ConflictMergePlan:
    merged_changed = set(changed_keys)
    originals = dict(baseline_values)
    keep_conflict: set[str] = set()
    value_updates: dict[str, str] = {}
    status_updates: dict[str, Status] = {}
    for key, (chosen_value, choice) in resolutions.items():
        if key not in conflict_originals:
            continue
        original_value = conflict_originals.get(key, "")
        if chosen_value == original_value:
            merged_changed.discard(key)
        else:
            merged_changed.add(key)
            originals[key] = original_value
            keep_conflict.add(key)
        if chosen_value != cache_values.get(key, ""):
            value_updates[key] = chosen_value
        if choice == "original":
            status_updates[key] = Status.FOR_REVIEW
    return ConflictMergePlan(
        changed_keys=frozenset(merged_changed),
        original_values=originals,
        force_original=frozenset(keep_conflict),
        value_updates=value_updates,
        status_updates=status_updates,
    )


def apply_entry_updates(
    entries: EntrySequence,
    *,
    value_updates: Mapping[str, str],
    status_updates: Mapping[str, Status],
) -> bool:
    if not value_updates and not status_updates:
        return False
    updated = False
    for idx, entry in enumerate(entries):
        if entry.key not in value_updates and entry.key not in status_updates:
            continue
        new_value = value_updates.get(entry.key, entry.value)
        new_status = status_updates.get(entry.key, entry.status)
        if new_value == entry.value and new_status == entry.status:
            continue
        entries[idx] = type(entry)(
            entry.key,
            new_value,
            new_status,
            entry.span,
            entry.segments,
            entry.gaps,
            entry.raw,
            getattr(entry, "key_hash", None),
        )
        updated = True
    return updated
