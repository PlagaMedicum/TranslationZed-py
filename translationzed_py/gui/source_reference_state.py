"""Source reference state module for direct source-or-empty behavior."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path

from translationzed_py.core.source_reference_service import (
    normalize_source_reference_mode,
    resolve_source_reference_mode_for_path,
)

_LEGACY_SOURCE_REFERENCE_EXTRA_KEYS = (
    "SOURCE_REFERENCE_FALLBACK_POLICY",
    "SOURCE_REFERENCE_FALLBACK_CHAIN",
    "SOURCE_REFERENCE_FALLBACK_PRESETS",
)


def _window_available_source_reference_locales(
    win: object, *, exclude_locale: str | None = None
) -> tuple[str, ...]:
    """Return visible source-reference locale options for the active window."""
    excluded = str(exclude_locale or "").strip().upper()
    out = ["EN"]
    for locale in getattr(win, "_selected_locales", ()):
        code = str(locale).strip().upper()
        if code and code != excluded and code not in out:
            out.append(code)
    return tuple(out)


def source_reference_preferences_payload_for_window(win: object) -> dict[str, str]:
    """Build source-reference preference payload for dialog initialization."""
    _ = win
    return {}


def effective_source_reference_mode(
    *,
    root: Path,  # kept for call-shape stability
    path: Path,  # kept for call-shape stability
    locale: str | None,
    default_mode: object,
    overrides: Mapping[str, str],  # kept for call-shape stability
    available_locales: Iterable[str],
) -> str:
    """Return the requested source-reference locale for one file context."""
    _ = (locale, available_locales)
    return resolve_source_reference_mode_for_path(
        root=root,
        path=path,
        default_mode=default_mode,
        overrides=overrides,
    )


def apply_source_reference_mode_change(
    *,
    mode: object,
    root: Path,  # kept for call-shape stability
    current_path: Path | None,  # kept for call-shape stability
    default_mode: str,
    overrides: MutableMapping[str, str],  # kept for call-shape stability
    extras: MutableMapping[str, str],
) -> tuple[str, bool]:
    """Apply source reference mode change."""
    _ = (root, current_path, overrides)
    normalized_mode = normalize_source_reference_mode(mode, default="EN")
    if normalized_mode == default_mode:
        return default_mode, False
    extras["SOURCE_REFERENCE_MODE"] = normalized_mode
    return normalized_mode, True


def apply_source_reference_preferences(
    *,
    values: Mapping[str, object],
    overrides: MutableMapping[str, str],  # kept for call-shape stability
    extras: MutableMapping[str, str],
) -> bool:
    """Drop any legacy fallback extras that should no longer persist."""
    _ = (values, overrides)
    changed = False
    for key in _LEGACY_SOURCE_REFERENCE_EXTRA_KEYS:
        if key in extras:
            extras.pop(key, None)
            changed = True
    return changed


def refresh_source_reference_from_window(win: object) -> None:
    """Refresh source reference from the active window context."""
    current_pf = getattr(win, "_current_pf", None)
    current_model = getattr(win, "_current_model", None)
    if current_pf is None or current_model is None:
        return
    path = current_pf.path
    locale = win._locale_for_path(path)
    source_lookup = win._load_reference_source(
        path,
        locale,
        target_entries=current_pf.entries,
    )
    current_model.set_source_lookup(
        source_values=source_lookup,
        source_by_row=source_lookup.by_row,
    )
    win._sync_detail_editors()
    win._update_status_bar()
    win._schedule_search()


def effective_source_reference_mode_for_window(
    win: object, path: Path, locale: str | None
) -> str:
    """Return the visible source-reference mode for the active window."""
    return effective_source_reference_mode(
        root=win._root,
        path=path,
        locale=locale,
        default_mode=win._source_reference_mode,
        overrides=win._source_reference_file_overrides,
        available_locales=_window_available_source_reference_locales(
            win, exclude_locale=locale
        ),
    )


def sync_source_reference_override_ui_for_window(win: object) -> None:
    """Synchronize source reference selection UI for the active window."""
    from .source_reference_ui import sync_source_reference_combo

    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    available_locales = _window_available_source_reference_locales(
        win,
        exclude_locale=current_locale,
    )
    sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
    )


def sync_source_reference_mode_for_window(win: object, *, persist: bool) -> None:
    """Synchronize source reference mode for window."""
    from .source_reference_ui import sync_source_reference_combo

    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    available_locales = _window_available_source_reference_locales(
        win,
        exclude_locale=current_locale,
    )
    win._source_reference_mode = sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
    )
    win._prefs_extras["SOURCE_REFERENCE_MODE"] = win._source_reference_mode
    sync_source_reference_override_ui_for_window(win)
    if persist:
        win._persist_preferences()


def handle_source_reference_changed(win: object, index: int) -> None:
    """Handle source reference changed."""
    from .source_reference_ui import source_reference_mode_from_combo

    mode = source_reference_mode_from_combo(win.source_ref_combo, index)
    win._source_reference_mode, changed = apply_source_reference_mode_change(
        mode=mode,
        root=win._root,
        current_path=win._current_pf.path if win._current_pf else None,
        default_mode=win._source_reference_mode,
        overrides=win._source_reference_file_overrides,
        extras=win._prefs_extras,
    )
    if not changed:
        return
    win._persist_preferences()
    win._search_rows_cache.clear()
    sync_source_reference_override_ui_for_window(win)
    refresh_source_reference_from_window(win)


def apply_source_reference_preferences_for_window(
    win: object, values: Mapping[str, object]
) -> bool:
    """Apply source reference preferences for window."""
    changed = apply_source_reference_preferences(
        values=values,
        overrides=win._source_reference_file_overrides,
        extras=win._prefs_extras,
    )
    if not changed:
        return False
    win._search_rows_cache.clear()
    sync_source_reference_override_ui_for_window(win)
    refresh_source_reference_from_window(win)
    return True
