"""Source reference service module."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .model import EntrySequence

if TYPE_CHECKING:
    from .model import ParsedFile


@dataclass(frozen=True, slots=True)
class SourceReferenceResolution:
    """Represent SourceReferenceResolution."""

    requested_mode: str
    resolved_locale: str
    fallback_used: bool


@dataclass(frozen=True, slots=True)
class SourceLookupMaterialized:
    """Represent SourceLookupMaterialized."""

    by_key: dict[str, str] | None = None
    by_row_values: list[str] | None = None
    by_row_entries: EntrySequence | None = None
    keys: list[str] | None = None


def source_reference_path_key(root: Path, path: Path) -> str:
    """Execute source reference path key."""
    try:
        rel = path.relative_to(root)
        return rel.as_posix()
    except ValueError:
        return path.as_posix()


def load_source_reference_file_overrides(raw: object) -> dict[str, str]:
    """Load source reference file overrides."""
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    overrides: dict[str, str] = {}
    for key, value in parsed.items():
        path_key = str(key).strip().replace("\\", "/")
        mode = normalize_source_reference_mode(value, default="")
        if path_key and mode:
            overrides[path_key] = mode
    return overrides


def dump_source_reference_file_overrides(overrides: Mapping[str, str]) -> str:
    """Execute dump source reference file overrides."""
    normalized: dict[str, str] = {}
    for key in sorted(overrides):
        path_key = str(key).strip().replace("\\", "/")
        mode = normalize_source_reference_mode(overrides.get(key), default="")
        if path_key and mode:
            normalized[path_key] = mode
    return json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))


def resolve_source_reference_mode_for_path(
    *,
    root: Path,
    path: Path,
    default_mode: object,
    overrides: Mapping[str, str],
) -> str:
    """Resolve source reference mode for path."""
    key = source_reference_path_key(root, path)
    requested = overrides.get(key, default_mode)
    return normalize_source_reference_mode(requested, default="EN")


def normalize_source_reference_mode(value: object, *, default: str = "EN") -> str:
    """Normalize source reference mode."""
    raw = str(value).strip().upper()
    if not raw:
        return default
    return raw


def resolve_source_reference_locale(
    mode: object,
    *,
    available_locales: Iterable[str],
    fallback_locale: str | None = None,
    default: str = "EN",
) -> SourceReferenceResolution:
    """Resolve source reference locale."""
    requested = normalize_source_reference_mode(mode, default=default)
    available = {str(locale).strip().upper() for locale in available_locales if locale}
    fallback = normalize_source_reference_mode(fallback_locale or "", default="")
    normalized_default = normalize_source_reference_mode(default, default="EN")

    if requested in available:
        return SourceReferenceResolution(
            requested_mode=requested,
            resolved_locale=requested,
            fallback_used=False,
        )
    if normalized_default in available:
        return SourceReferenceResolution(
            requested_mode=requested,
            resolved_locale=normalized_default,
            fallback_used=True,
        )
    if fallback and fallback in available:
        return SourceReferenceResolution(
            requested_mode=requested,
            resolved_locale=fallback,
            fallback_used=True,
        )
    if available:
        resolved = sorted(available)[0]
        return SourceReferenceResolution(
            requested_mode=requested,
            resolved_locale=resolved,
            fallback_used=True,
        )
    return SourceReferenceResolution(
        requested_mode=requested,
        resolved_locale=normalized_default,
        fallback_used=requested != normalized_default,
    )


def reference_path_for(
    root: Path,
    path: Path,
    *,
    target_locale: str,
    reference_locale: str,
) -> Path | None:
    """Execute reference path for."""
    target = normalize_source_reference_mode(target_locale, default="")
    reference = normalize_source_reference_mode(reference_locale, default="")
    if not target or not reference:
        return None
    if target == reference:
        return path if path.exists() else None
    locale_root = root / target
    try:
        rel = path.relative_to(locale_root)
    except ValueError:
        try:
            rel_full = path.relative_to(root)
        except ValueError:
            return None
        if not rel_full.parts or rel_full.parts[0].upper() != target:
            return None
        rel = Path(*rel_full.parts[1:])
    candidate = root / reference / rel
    if candidate.exists():
        return candidate
    stem = rel.stem
    for token in _locale_suffix_tokens(target):
        suffix = f"_{token}"
        if not stem.endswith(suffix):
            continue
        prefix = stem[: -len(suffix)]
        for reference_token in _locale_suffix_tokens(reference):
            alt_name = f"{prefix}_{reference_token}{rel.suffix}"
            alt_path = root / reference / rel.with_name(alt_name)
            if alt_path.exists():
                return alt_path
    return None


def _locale_suffix_tokens(locale: str) -> tuple[str, ...]:
    """Execute locale suffix tokens."""
    raw = locale.strip()
    underscore = raw.replace(" ", "_")
    if underscore == raw:
        return (raw,)
    return (raw, underscore)


def build_source_lookup_materialized(
    reference_entries: EntrySequence,
    *,
    target_entries: EntrySequence | None,
    path_name: str,
) -> SourceLookupMaterialized:
    """Build source lookup materialized."""
    if _is_raw_single_entry(reference_entries):
        raw_value = reference_entries[0].value
        if target_entries is not None and _matches_single_raw_target(
            target_entries, path_name
        ):
            return SourceLookupMaterialized(
                by_row_values=[raw_value],
                keys=[path_name],
            )
        return SourceLookupMaterialized(by_key={path_name: raw_value})

    if target_entries is not None and _keys_match(target_entries, reference_entries):
        keys = _keys_list(target_entries)
        if hasattr(reference_entries, "prefetch"):
            return SourceLookupMaterialized(by_row_entries=reference_entries, keys=keys)
        return SourceLookupMaterialized(
            by_row_values=[entry.value for entry in reference_entries],
            keys=keys,
        )
    return SourceLookupMaterialized(
        by_key={entry.key: entry.value for entry in reference_entries}
    )


def load_reference_lookup(
    *,
    root: Path,
    path: Path,
    target_locale: str | None,
    reference_locale: str,
    locale_encodings: Mapping[str, str],
    target_entries: EntrySequence | None,
    parsed_cache: MutableMapping[Path, ParsedFile],
    should_parse_lazy: Callable[[Path], bool],
    parse_eager: Callable[[Path, str], ParsedFile],
    parse_lazy: Callable[[Path, str], ParsedFile],
) -> SourceLookupMaterialized | None:
    """Load reference lookup."""
    if not target_locale:
        return None
    if reference_locale not in locale_encodings:
        return None
    if reference_locale == target_locale:
        source_path = path if path.exists() else None
    else:
        source_path = reference_path_for(
            root,
            path,
            target_locale=target_locale,
            reference_locale=reference_locale,
        )
    if source_path is None:
        return None
    parsed = parsed_cache.get(source_path)
    if parsed is None:
        encoding = locale_encodings.get(reference_locale, "utf-8")
        try:
            parsed = (
                parse_lazy(source_path, encoding)
                if should_parse_lazy(source_path)
                else parse_eager(source_path, encoding)
            )
        except Exception:
            return None
        parsed_cache[source_path] = parsed
    return build_source_lookup_materialized(
        parsed.entries,
        target_entries=target_entries,
        path_name=path.name,
    )


def _entry_key(entries: EntrySequence, idx: int) -> str:
    """Execute entry key."""
    if hasattr(entries, "key_at"):
        return str(entries.key_at(idx))
    return entries[idx].key


def _keys_match(a: EntrySequence, b: EntrySequence) -> bool:
    """Execute keys match."""
    count = len(a)
    if count != len(b):
        return False
    return all(_entry_key(a, idx) == _entry_key(b, idx) for idx in range(count))


def _keys_list(entries: EntrySequence) -> list[str]:
    """Execute keys list."""
    return [_entry_key(entries, idx) for idx in range(len(entries))]


def _is_raw_single_entry(entries: EntrySequence) -> bool:
    """Return whether raw single entry."""
    if not entries:
        return False
    if hasattr(entries, "meta_at"):
        return len(entries) == 1 and bool(entries.meta_at(0).raw)
    return all(getattr(entry, "raw", False) for entry in entries)


def _matches_single_raw_target(entries: EntrySequence, path_name: str) -> bool:
    """Execute matches single raw target."""
    return len(entries) == 1 and _entry_key(entries, 0) == path_name
