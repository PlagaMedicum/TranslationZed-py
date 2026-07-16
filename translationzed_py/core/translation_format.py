"""Identify supported Project Zomboid translation files and cache identities."""

from __future__ import annotations

from pathlib import Path

B42_JSON_EXTENSION = ".json"


def supported_extensions(legacy_extension: str) -> tuple[str, ...]:
    """Return supported translation extensions without duplicates."""
    legacy = legacy_extension.lower()
    if legacy == B42_JSON_EXTENSION:
        return (B42_JSON_EXTENSION,)
    return (legacy, B42_JSON_EXTENSION)


def is_json_translation(path: Path) -> bool:
    """Return whether *path* uses the confirmed B42 JSON format."""
    return path.suffix.lower() == B42_JSON_EXTENSION


def is_supported_translation(path: Path, *, legacy_extension: str) -> bool:
    """Return whether *path* has a supported translation-file extension."""
    return path.suffix.lower() in supported_extensions(legacy_extension)


def cache_relative_path(
    translation_relative_path: Path,
    *,
    legacy_extension: str,
    cache_extension: str,
) -> Path:
    """Map a translation-relative path to a format-distinct cache path."""
    if is_json_translation(translation_relative_path):
        return translation_relative_path.with_name(
            f"{translation_relative_path.name}{cache_extension}"
        )
    if translation_relative_path.stem.lower().endswith(B42_JSON_EXTENSION):
        return translation_relative_path.with_name(
            f"{translation_relative_path.name}{cache_extension}"
        )
    return translation_relative_path.with_suffix(cache_extension)


def translation_relative_path(
    cache_relative_path_value: Path,
    *,
    legacy_extension: str,
    cache_extension: str,
) -> Path | None:
    """Recover a supported translation-relative path from its cache path."""
    name = cache_relative_path_value.name
    legacy_tail = f"{legacy_extension}{cache_extension}"
    if name.lower().endswith(legacy_tail.lower()):
        return cache_relative_path_value.with_name(name[: -len(cache_extension)])
    json_tail = f"{B42_JSON_EXTENSION}{cache_extension}"
    if name.lower().endswith(json_tail.lower()):
        return cache_relative_path_value.with_name(name[: -len(cache_extension)])
    if cache_relative_path_value.suffix.lower() != cache_extension.lower():
        return None
    return cache_relative_path_value.with_suffix(legacy_extension)
