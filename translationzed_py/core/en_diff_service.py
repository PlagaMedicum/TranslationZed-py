"""EN diff classification helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from translationzed_py.core.en_diff_snapshot import hash_key, hash_text

DIFF_NEW = "NEW"
DIFF_REMOVED = "REMOVED"
DIFF_MODIFIED = "MODIFIED"


@dataclass(frozen=True, slots=True)
class ENDiffResult:
    """Represent EN diff classification for one locale file."""

    new_keys: tuple[str, ...]
    removed_keys: tuple[str, ...]
    modified_keys: tuple[str, ...]


def classify_file(
    *,
    en_values: Mapping[str, str],
    locale_values: Mapping[str, str],
    snapshot_rows: Mapping[str, str],
) -> ENDiffResult:
    """Classify locale keys against EN keys and snapshot baseline."""
    en_keys = set(en_values)
    locale_keys = set(locale_values)
    new_keys = tuple(key for key in en_values if key not in locale_keys)
    removed_keys = tuple(sorted(key for key in locale_values if key not in en_keys))
    modified: list[str] = []
    for key in en_values:
        if key not in locale_keys:
            continue
        key_hash = hash_key(key)
        baseline = snapshot_rows.get(key_hash)
        if not baseline:
            continue
        if baseline != hash_text(str(en_values[key])):
            modified.append(key)
    return ENDiffResult(
        new_keys=new_keys,
        removed_keys=removed_keys,
        modified_keys=tuple(modified),
    )
