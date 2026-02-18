"""File workflow module."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .model import Entry, EntrySequence
from .status_cache import CacheEntry

if TYPE_CHECKING:
    from .model import ParsedFile


@dataclass(frozen=True, slots=True)
class CacheOverlayResult:
    """Represent CacheOverlayResult."""

    changed_keys: set[str]
    baseline_by_row: dict[int, str]
    conflict_originals: dict[str, str]
    original_values: dict[str, str]


@dataclass(frozen=True, slots=True)
class CacheWriteOverlay:
    """Represent CacheWriteOverlay."""

    entries: list[Entry]
    changed_values: dict[str, str]


@dataclass(frozen=True, slots=True)
class OpenFileCallbacks:
    """Represent OpenFileCallbacks."""

    parse_eager: Callable[[Path, str], ParsedFile]
    parse_lazy: Callable[[Path, str], ParsedFile]
    read_cache: Callable[[Path], Mapping[int, CacheEntry]]
    touch_last_opened: Callable[[Path, int], object]
    now_ts: Callable[[], int]


@dataclass(frozen=True, slots=True)
class OpenFileResult:
    """Represent OpenFileResult."""

    parsed_file: ParsedFile
    cache_map: Mapping[int, CacheEntry]
    overlay: CacheOverlayResult


@dataclass(frozen=True, slots=True)
class SaveCurrentRunPlan:
    """Represent SaveCurrentRunPlan."""

    run_save: bool
    immediate_result: bool | None


@dataclass(frozen=True, slots=True)
class SaveCurrentCallbacks:
    """Represent SaveCurrentCallbacks."""

    save_file: Callable[[ParsedFile, Mapping[str, str], str], object]
    write_cache: Callable[[Path, Iterable[Entry], int], object]
    now_ts: Callable[[], int]


@dataclass(frozen=True, slots=True)
class SaveCurrentResult:
    """Represent SaveCurrentResult."""

    wrote_original: bool
    wrote_cache: bool


@dataclass(frozen=True, slots=True)
class SaveFromCacheCallbacks:
    """Represent SaveFromCacheCallbacks."""

    parse_file: Callable[[Path, str], ParsedFile]
    save_file: Callable[[ParsedFile, Mapping[str, str], str], object]
    write_cache: Callable[[Path, Iterable[Entry]], object]


@dataclass(frozen=True, slots=True)
class SaveFromCacheResult:
    """Represent SaveFromCacheResult."""

    had_drafts: bool
    wrote_original: bool
    changed_values: Mapping[str, str]


class SaveFromCacheParseError(Exception):
    """Represent SaveFromCacheParseError."""

    def __init__(self, *, path: Path, original: Exception) -> None:
        """Initialize the instance."""
        super().__init__(str(original))
        self.path = path
        self.original = original


@dataclass(frozen=True, slots=True)
class FileWorkflowService:
    """Represent FileWorkflowService."""

    def prepare_open_file(
        self,
        path: Path,
        encoding: str,
        *,
        use_lazy_parser: bool,
        callbacks: OpenFileCallbacks,
        hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
    ) -> OpenFileResult:
        """Prepare open file."""
        return prepare_open_file(
            path,
            encoding,
            use_lazy_parser=use_lazy_parser,
            callbacks=callbacks,
            hash_for_entry=hash_for_entry,
        )

    def apply_cache_overlay(
        self,
        entries: EntrySequence,
        cache_map: Mapping[int, CacheEntry],
        *,
        hash_for_entry: Callable[[Entry], int],
    ) -> CacheOverlayResult:
        """Apply cache overlay."""
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
        """Apply cache for write."""
        return apply_cache_for_write(
            entries,
            cache_map,
            hash_for_entry=hash_for_entry,
        )

    def build_save_current_run_plan(
        self,
        *,
        has_current_file: bool,
        has_current_model: bool,
        conflicts_resolved: bool,
        has_changed_keys: bool,
    ) -> SaveCurrentRunPlan:
        """Build save current run plan."""
        return build_save_current_run_plan(
            has_current_file=has_current_file,
            has_current_model=has_current_model,
            conflicts_resolved=conflicts_resolved,
            has_changed_keys=has_changed_keys,
        )

    def persist_current_save(
        self,
        *,
        path: Path,
        parsed_file: ParsedFile,
        changed_values: Mapping[str, str],
        encoding: str,
        callbacks: SaveCurrentCallbacks,
    ) -> SaveCurrentResult:
        """Execute persist current save."""
        return persist_current_save(
            path=path,
            parsed_file=parsed_file,
            changed_values=changed_values,
            encoding=encoding,
            callbacks=callbacks,
        )

    def write_from_cache(
        self,
        path: Path,
        encoding: str,
        *,
        cache_map: Mapping[int, CacheEntry],
        callbacks: SaveFromCacheCallbacks,
        hash_for_entry: Callable[[Entry], int],
    ) -> SaveFromCacheResult:
        """Write from cache."""
        return write_from_cache(
            path,
            encoding,
            cache_map=cache_map,
            callbacks=callbacks,
            hash_for_entry=hash_for_entry,
        )


def prepare_open_file(
    path: Path,
    encoding: str,
    *,
    use_lazy_parser: bool,
    callbacks: OpenFileCallbacks,
    hash_for_entry: Callable[[Entry, Mapping[int, CacheEntry]], int],
) -> OpenFileResult:
    """Prepare open file."""
    parsed = (
        callbacks.parse_lazy(path, encoding)
        if use_lazy_parser
        else callbacks.parse_eager(path, encoding)
    )
    cache_map = callbacks.read_cache(path)
    callbacks.touch_last_opened(path, callbacks.now_ts())
    overlay = apply_cache_overlay(
        parsed.entries,
        cache_map,
        hash_for_entry=lambda entry: hash_for_entry(entry, cache_map),
    )
    return OpenFileResult(parsed_file=parsed, cache_map=cache_map, overlay=overlay)


def apply_cache_overlay(
    entries: EntrySequence,
    cache_map: Mapping[int, CacheEntry],
    *,
    hash_for_entry: Callable[[Entry], int],
) -> CacheOverlayResult:
    """Apply cache overlay."""
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
    """Apply cache for write."""
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


def build_save_current_run_plan(
    *,
    has_current_file: bool,
    has_current_model: bool,
    conflicts_resolved: bool,
    has_changed_keys: bool,
) -> SaveCurrentRunPlan:
    """Build save current run plan."""
    if not has_current_file or not has_current_model:
        return SaveCurrentRunPlan(run_save=False, immediate_result=True)
    if not conflicts_resolved:
        return SaveCurrentRunPlan(run_save=False, immediate_result=False)
    if not has_changed_keys:
        return SaveCurrentRunPlan(run_save=False, immediate_result=True)
    return SaveCurrentRunPlan(run_save=True, immediate_result=None)


def persist_current_save(
    *,
    path: Path,
    parsed_file: ParsedFile,
    changed_values: Mapping[str, str],
    encoding: str,
    callbacks: SaveCurrentCallbacks,
) -> SaveCurrentResult:
    """Execute persist current save."""
    wrote_original = False
    if changed_values:
        callbacks.save_file(parsed_file, changed_values, encoding)
        wrote_original = True
    callbacks.write_cache(path, parsed_file.entries, callbacks.now_ts())
    return SaveCurrentResult(
        wrote_original=wrote_original,
        wrote_cache=True,
    )


def write_from_cache(
    path: Path,
    encoding: str,
    *,
    cache_map: Mapping[int, CacheEntry],
    callbacks: SaveFromCacheCallbacks,
    hash_for_entry: Callable[[Entry], int],
) -> SaveFromCacheResult:
    """Write from cache."""
    if not any(entry.value is not None for entry in cache_map.values()):
        return SaveFromCacheResult(
            had_drafts=False,
            wrote_original=False,
            changed_values={},
        )
    try:
        parsed = callbacks.parse_file(path, encoding)
    except Exception as exc:
        raise SaveFromCacheParseError(path=path, original=exc) from exc
    overlay = apply_cache_for_write(
        parsed.entries,
        cache_map,
        hash_for_entry=hash_for_entry,
    )
    parsed.entries = overlay.entries
    if overlay.changed_values:
        callbacks.save_file(parsed, overlay.changed_values, encoding)
    callbacks.write_cache(path, parsed.entries)
    return SaveFromCacheResult(
        had_drafts=True,
        wrote_original=bool(overlay.changed_values),
        changed_values=overlay.changed_values,
    )
