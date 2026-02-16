from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path

from translationzed_py.core.source_reference_service import (
    normalize_source_reference_mode,
    resolve_source_reference_locale,
)

_FALLBACK_EN_THEN_TARGET = "EN_THEN_TARGET"
_FALLBACK_TARGET_THEN_EN = "TARGET_THEN_EN"


def _window_available_source_reference_locales(
    win: object, *, exclude_locale: str | None = None
) -> tuple[str, ...]:
    excluded = str(exclude_locale or "").strip().upper()
    out = ["EN"]
    for locale in getattr(win, "_selected_locales", ()):
        code = str(locale).strip().upper()
        if code and code != excluded and code not in out:
            out.append(code)
    return tuple(out)


def normalize_source_reference_fallback_policy(
    value: object, *, default: str = _FALLBACK_EN_THEN_TARGET
) -> str:
    raw = str(value).strip().upper()
    if raw in {_FALLBACK_EN_THEN_TARGET, _FALLBACK_TARGET_THEN_EN}:
        return raw
    return default


def source_reference_fallback_pair(locale: str | None, policy: str) -> tuple[str, str]:
    target = normalize_source_reference_mode(locale, default="EN")
    normalized = normalize_source_reference_fallback_policy(policy)
    if normalized == _FALLBACK_TARGET_THEN_EN:
        return target, "EN"
    return "EN", target


def effective_source_reference_mode(
    *,
    root: Path,  # kept for call-shape stability
    path: Path,  # kept for call-shape stability
    locale: str | None,
    default_mode: object,
    overrides: Mapping[str, str],  # kept for call-shape stability
    available_locales: Iterable[str],
    fallback_policy: str = _FALLBACK_EN_THEN_TARGET,
) -> str:
    requested = normalize_source_reference_mode(default_mode, default="EN")
    default_locale, fallback_locale = source_reference_fallback_pair(
        locale, fallback_policy
    )
    resolution = resolve_source_reference_locale(
        requested,
        available_locales=available_locales,
        fallback_locale=fallback_locale,
        default=default_locale,
    )
    return resolution.resolved_locale


def apply_source_reference_mode_change(
    *,
    mode: object,
    root: Path,  # kept for call-shape stability
    current_path: Path | None,  # kept for call-shape stability
    default_mode: str,
    overrides: MutableMapping[str, str],  # kept for call-shape stability
    extras: MutableMapping[str, str],
) -> tuple[str, bool]:
    _ = (root, current_path, overrides)
    normalized_mode = normalize_source_reference_mode(mode, default="EN")
    if normalized_mode == default_mode:
        return default_mode, False
    extras["SOURCE_REFERENCE_MODE"] = normalized_mode
    return normalized_mode, True


def apply_source_reference_preferences(
    *,
    values: Mapping[str, object],
    current_fallback_policy: str,
    overrides: MutableMapping[str, str],  # kept for call-shape stability
    extras: MutableMapping[str, str],
) -> tuple[str, bool]:
    _ = overrides
    policy = normalize_source_reference_fallback_policy(
        values.get("source_reference_fallback_policy", current_fallback_policy),
        default=current_fallback_policy,
    )
    changed = policy != current_fallback_policy
    if changed:
        extras["SOURCE_REFERENCE_FALLBACK_POLICY"] = policy
    return policy, changed


def refresh_source_reference_from_window(win: object) -> None:
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
    return effective_source_reference_mode(
        root=win._root,
        path=path,
        locale=locale,
        default_mode=win._source_reference_mode,
        overrides=win._source_reference_file_overrides,
        available_locales=_window_available_source_reference_locales(
            win, exclude_locale=locale
        ),
        fallback_policy=win._source_reference_fallback_policy,
    )


def sync_source_reference_override_ui_for_window(win: object) -> None:
    from .source_reference_ui import sync_source_reference_combo

    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    available_locales = _window_available_source_reference_locales(
        win,
        exclude_locale=current_locale,
    )
    active_locale = current_locale or (
        win._selected_locales[0] if getattr(win, "_selected_locales", ()) else "EN"
    )
    fallback_default, fallback_secondary = source_reference_fallback_pair(
        active_locale,
        win._source_reference_fallback_policy,
    )
    sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
        fallback_default=fallback_default,
        fallback_secondary=fallback_secondary,
    )


def sync_source_reference_mode_for_window(win: object, *, persist: bool) -> None:
    from .source_reference_ui import sync_source_reference_combo

    selected_locale = win._selected_locales[0] if win._selected_locales else "EN"
    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    available_locales = _window_available_source_reference_locales(
        win,
        exclude_locale=current_locale,
    )
    fallback_default, fallback_secondary = source_reference_fallback_pair(
        selected_locale,
        win._source_reference_fallback_policy,
    )
    win._source_reference_mode = sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
        fallback_default=fallback_default,
        fallback_secondary=fallback_secondary,
    )
    win._prefs_extras["SOURCE_REFERENCE_MODE"] = win._source_reference_mode
    sync_source_reference_override_ui_for_window(win)
    if persist:
        win._persist_preferences()


def handle_source_reference_changed(win: object, index: int) -> None:
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
    policy, changed = apply_source_reference_preferences(
        values=values,
        current_fallback_policy=win._source_reference_fallback_policy,
        overrides=win._source_reference_file_overrides,
        extras=win._prefs_extras,
    )
    win._source_reference_fallback_policy = policy
    if not changed:
        return False
    win._search_rows_cache.clear()
    sync_source_reference_override_ui_for_window(win)
    refresh_source_reference_from_window(win)
    return True
