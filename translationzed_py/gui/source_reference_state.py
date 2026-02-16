from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QToolButton

from translationzed_py.core.source_reference_service import (
    dump_source_reference_file_overrides,
    normalize_source_reference_mode,
    resolve_source_reference_locale,
    resolve_source_reference_mode_for_path,
    source_reference_path_key,
)

_FALLBACK_EN_THEN_TARGET = "EN_THEN_TARGET"
_FALLBACK_TARGET_THEN_EN = "TARGET_THEN_EN"


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


def current_source_reference_path_key(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return source_reference_path_key(root, path)


def effective_source_reference_mode(
    *,
    root: Path,
    path: Path,
    locale: str | None,
    default_mode: object,
    overrides: Mapping[str, str],
    available_locales: Iterable[str],
    fallback_policy: str = _FALLBACK_EN_THEN_TARGET,
) -> str:
    requested = resolve_source_reference_mode_for_path(
        root=root,
        path=path,
        default_mode=default_mode,
        overrides=overrides,
    )
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


def sync_source_reference_override_ui(
    *,
    combo: QComboBox,
    pin_btn: QToolButton,
    root: Path,
    current_path: Path | None,
    current_locale: str | None,
    default_mode: str,
    overrides: Mapping[str, str],
    available_locales: Iterable[str],
    fallback_policy: str = _FALLBACK_EN_THEN_TARGET,
) -> None:
    path_key = current_source_reference_path_key(root, current_path)
    override_active = bool(path_key and path_key in overrides)
    pin_btn.setEnabled(bool(path_key))
    blocker = pin_btn.blockSignals(True)
    pin_btn.setChecked(override_active)
    pin_btn.blockSignals(blocker)
    pin_btn.setToolTip(
        "Use file-specific Source locale."
        if override_active
        else "Pin current Source locale for this file."
    )
    if current_path is None:
        return
    mode = effective_source_reference_mode(
        root=root,
        path=current_path,
        locale=current_locale,
        default_mode=default_mode,
        overrides=overrides,
        available_locales=available_locales,
        fallback_policy=fallback_policy,
    )
    idx = combo.findData(mode)
    if idx < 0 or idx == combo.currentIndex():
        return
    combo_blocker = combo.blockSignals(True)
    combo.setCurrentIndex(idx)
    combo.blockSignals(combo_blocker)


def persist_source_reference_overrides(
    *,
    extras: MutableMapping[str, str],
    overrides: Mapping[str, str],
) -> None:
    if overrides:
        extras["SOURCE_REFERENCE_FILE_OVERRIDES"] = (
            dump_source_reference_file_overrides(overrides)
        )
    else:
        extras.pop("SOURCE_REFERENCE_FILE_OVERRIDES", None)


def apply_source_reference_mode_change(
    *,
    mode: object,
    root: Path,
    current_path: Path | None,
    default_mode: str,
    overrides: MutableMapping[str, str],
    extras: MutableMapping[str, str],
) -> tuple[str, bool]:
    normalized_mode = normalize_source_reference_mode(mode, default="EN")
    path_key = current_source_reference_path_key(root, current_path)
    if path_key and path_key in overrides:
        if overrides.get(path_key) == normalized_mode:
            return default_mode, False
        overrides[path_key] = normalized_mode
        persist_source_reference_overrides(extras=extras, overrides=overrides)
        return default_mode, True
    if normalized_mode == default_mode:
        return default_mode, False
    extras["SOURCE_REFERENCE_MODE"] = normalized_mode
    return normalized_mode, True


def apply_source_reference_pin_toggle(
    *,
    checked: bool,
    mode: object,
    root: Path,
    current_path: Path | None,
    overrides: MutableMapping[str, str],
    extras: MutableMapping[str, str],
) -> bool:
    path_key = current_source_reference_path_key(root, current_path)
    if not path_key:
        return False
    normalized_mode = normalize_source_reference_mode(mode, default="EN")
    if checked:
        overrides[path_key] = normalized_mode
    else:
        overrides.pop(path_key, None)
    persist_source_reference_overrides(extras=extras, overrides=overrides)
    return True


def apply_source_reference_preferences(
    *,
    values: Mapping[str, object],
    current_fallback_policy: str,
    overrides: MutableMapping[str, str],
    extras: MutableMapping[str, str],
) -> tuple[str, bool]:
    policy = normalize_source_reference_fallback_policy(
        values.get("source_reference_fallback_policy", current_fallback_policy),
        default=current_fallback_policy,
    )
    changed = policy != current_fallback_policy
    if changed:
        extras["SOURCE_REFERENCE_FALLBACK_POLICY"] = policy
    clear_overrides = bool(values.get("source_reference_clear_overrides", False))
    if clear_overrides and overrides:
        overrides.clear()
        persist_source_reference_overrides(extras=extras, overrides=overrides)
        changed = True
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
        available_locales=win._locales.keys(),
        fallback_policy=win._source_reference_fallback_policy,
    )


def sync_source_reference_override_ui_for_window(win: object) -> None:
    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    sync_source_reference_override_ui(
        combo=win.source_ref_combo,
        pin_btn=win.source_ref_pin_btn,
        root=win._root,
        current_path=current_path,
        current_locale=current_locale,
        default_mode=win._source_reference_mode,
        overrides=win._source_reference_file_overrides,
        available_locales=win._locales.keys(),
        fallback_policy=win._source_reference_fallback_policy,
    )


def sync_source_reference_mode_for_window(win: object, *, persist: bool) -> None:
    from .source_reference_ui import sync_source_reference_combo

    selected_locale = win._selected_locales[0] if win._selected_locales else "EN"
    fallback_default, fallback_secondary = source_reference_fallback_pair(
        selected_locale,
        win._source_reference_fallback_policy,
    )
    win._source_reference_mode = sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=win._selected_locales,
        all_locales=win._locales.keys(),
        fallback_default=fallback_default,
        fallback_secondary=fallback_secondary,
    )
    win._prefs_extras["SOURCE_REFERENCE_MODE"] = win._source_reference_mode
    sync_source_reference_override_ui_for_window(win)
    if persist:
        win._persist_preferences()


def handle_source_reference_pin_toggle(win: object, checked: bool) -> None:
    from .source_reference_ui import source_reference_mode_from_combo

    mode = source_reference_mode_from_combo(
        win.source_ref_combo, win.source_ref_combo.currentIndex()
    )
    if not apply_source_reference_pin_toggle(
        checked=checked,
        mode=mode,
        root=win._root,
        current_path=win._current_pf.path if win._current_pf else None,
        overrides=win._source_reference_file_overrides,
        extras=win._prefs_extras,
    ):
        win.source_ref_pin_btn.setChecked(False)
        return
    win._persist_preferences()
    win._search_rows_cache.clear()
    sync_source_reference_override_ui_for_window(win)
    refresh_source_reference_from_window(win)


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
