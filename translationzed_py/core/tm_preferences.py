"""Preference-application helpers for TM import and enablement state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tm_store import TMStore


@dataclass(slots=True)
class TMPreferencesActions:
    """Hold pending TM preference mutations requested from the preferences UI."""

    remove_paths: set[str] = field(default_factory=set)
    enabled_map: dict[str, bool] = field(default_factory=dict)
    import_paths: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return whether no TM preference changes are queued."""
        return not self.remove_paths and not self.enabled_map and not self.import_paths


@dataclass(frozen=True, slots=True)
class TMPreferencesApplyReport:
    """Summarize TM preference application results and encountered failures."""

    sync_paths: tuple[Path, ...]
    failures: tuple[str, ...]


def actions_from_values(values: dict[str, Any]) -> TMPreferencesActions:
    """Translate raw dialog values into normalized TM preference actions."""
    actions = TMPreferencesActions()
    remove_paths_raw = values.get("tm_remove_paths", []) or []
    enabled_raw = values.get("tm_enabled", {}) or {}
    import_paths_raw = values.get("tm_import_paths", []) or []
    actions.remove_paths = {
        str(path).strip() for path in remove_paths_raw if str(path).strip()
    }
    if isinstance(enabled_raw, dict):
        for path, flag in enabled_raw.items():
            path_s = str(path).strip()
            if path_s:
                actions.enabled_map[path_s] = bool(flag)
    actions.import_paths = [
        str(path).strip() for path in import_paths_raw if str(path).strip()
    ]
    return actions


def apply_actions(
    store: TMStore,
    actions: TMPreferencesActions,
    *,
    copy_to_import_dir: Callable[[Path], Path],
) -> TMPreferencesApplyReport:
    """Apply TM preference actions to the store and import directory."""
    failures: list[str] = []
    sync_paths: set[Path] = set()
    for source in actions.import_paths:
        try:
            sync_paths.add(copy_to_import_dir(Path(source)))
        except Exception as exc:
            failures.append(f"{source}: {exc}")
    for tm_path in actions.remove_paths:
        path = Path(tm_path)
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                failures.append(f"{tm_path}: {exc}")
                continue
        store.delete_import_file(tm_path)
    for tm_path, enabled in actions.enabled_map.items():
        if tm_path in actions.remove_paths:
            continue
        store.set_import_enabled(tm_path, enabled)
    return TMPreferencesApplyReport(
        sync_paths=tuple(sorted(sync_paths)),
        failures=tuple(failures),
    )
