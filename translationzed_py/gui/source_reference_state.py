"""Source reference state module."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path

from translationzed_py.core.source_reference_service import (
    SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET,
    SOURCE_REFERENCE_FALLBACK_TARGET_THEN_EN,
    build_source_reference_fallback_chain,
    dump_source_reference_fallback_presets,
    load_source_reference_fallback_presets,
    normalize_source_reference_mode,
    resolve_source_reference_locale,
)
from translationzed_py.core.source_reference_service import (
    normalize_source_reference_fallback_chain as _normalize_fallback_chain,
)
from translationzed_py.core.source_reference_service import (
    normalize_source_reference_fallback_policy as _normalize_fallback_policy,
)

_FALLBACK_EN_THEN_TARGET = SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET
_FALLBACK_TARGET_THEN_EN = SOURCE_REFERENCE_FALLBACK_TARGET_THEN_EN
_FALLBACK_CHAIN_EXTRA_KEY = "SOURCE_REFERENCE_FALLBACK_CHAIN"
_FALLBACK_PRESETS_EXTRA_KEY = "SOURCE_REFERENCE_FALLBACK_PRESETS"


def _window_available_source_reference_locales(
    win: object, *, exclude_locale: str | None = None
) -> tuple[str, ...]:
    """Execute window available source reference locales."""
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
    """Normalize source reference fallback policy."""
    return _normalize_fallback_policy(value, default=default)


def normalize_source_reference_fallback_chain(
    value: object, *, default: Iterable[str] = ()
) -> tuple[str, ...]:
    """Normalize source reference fallback chain."""
    return _normalize_fallback_chain(value, default=default)


def normalize_source_reference_fallback_presets(
    value: Mapping[str, Iterable[str]] | object,
) -> dict[str, tuple[str, ...]]:
    """Normalize source reference fallback presets."""
    if isinstance(value, Mapping):
        normalized: dict[str, tuple[str, ...]] = {}
        for locale, chain in value.items():
            locale_code = normalize_source_reference_mode(locale, default="")
            chain_codes = normalize_source_reference_fallback_chain(chain, default=())
            if locale_code and chain_codes:
                normalized[locale_code] = chain_codes
        return normalized
    return load_source_reference_fallback_presets(value)


def serialize_source_reference_fallback_chain(chain: Iterable[str]) -> str:
    """Serialize source reference fallback chain."""
    normalized = normalize_source_reference_fallback_chain(chain, default=())
    return ",".join(normalized)


def source_reference_fallback_chain(
    locale: str | None,
    *,
    policy: str,
    fallback_chain: Iterable[str] = (),
    fallback_presets: Mapping[str, Iterable[str]] | None = None,
) -> tuple[str, ...]:
    """Build effective source-reference fallback chain for target locale."""
    target = normalize_source_reference_mode(locale, default="EN")
    built = build_source_reference_fallback_chain(
        target_locale=target,
        policy=policy,
        presets=fallback_presets or {},
    )
    return normalize_source_reference_fallback_chain(
        (*built, *tuple(fallback_chain)),
        default=built,
    )


def _window_source_reference_fallback_chain(win: object) -> tuple[str, ...]:
    raw = getattr(win, "_source_reference_fallback_chain", None)
    if raw is None:
        extras = getattr(win, "_prefs_extras", {})
        if isinstance(extras, Mapping):
            raw = extras.get(_FALLBACK_CHAIN_EXTRA_KEY)
    return normalize_source_reference_fallback_chain(raw, default=())


def _window_source_reference_fallback_presets(
    win: object,
) -> dict[str, tuple[str, ...]]:
    raw = getattr(win, "_source_reference_fallback_presets", None)
    if raw is None:
        extras = getattr(win, "_prefs_extras", {})
        if isinstance(extras, Mapping):
            raw = extras.get(_FALLBACK_PRESETS_EXTRA_KEY)
    return normalize_source_reference_fallback_presets(raw or {})


def source_reference_preferences_payload_for_window(win: object) -> dict[str, str]:
    """Build source-reference preference payload for dialog initialization."""
    return {
        "source_reference_fallback_policy": normalize_source_reference_fallback_policy(
            getattr(win, "_source_reference_fallback_policy", _FALLBACK_EN_THEN_TARGET)
        ),
        "source_reference_fallback_chain": serialize_source_reference_fallback_chain(
            _window_source_reference_fallback_chain(win)
        ),
        "source_reference_fallback_presets": dump_source_reference_fallback_presets(
            _window_source_reference_fallback_presets(win)
        ),
    }


def source_reference_fallback_pair(locale: str | None, policy: str) -> tuple[str, str]:
    """Execute source reference fallback pair."""
    chain = source_reference_fallback_chain(locale, policy=policy)
    default_locale = chain[0] if chain else "EN"
    secondary_locale = chain[1] if len(chain) > 1 else default_locale
    return default_locale, secondary_locale


def effective_source_reference_mode(
    *,
    root: Path,  # kept for call-shape stability
    path: Path,  # kept for call-shape stability
    locale: str | None,
    default_mode: object,
    overrides: Mapping[str, str],  # kept for call-shape stability
    available_locales: Iterable[str],
    fallback_policy: str = _FALLBACK_EN_THEN_TARGET,
    fallback_chain: Iterable[str] = (),
    fallback_presets: Mapping[str, Iterable[str]] | None = None,
) -> str:
    """Execute effective source reference mode."""
    _ = (root, path, overrides)
    requested = normalize_source_reference_mode(default_mode, default="EN")
    chain = source_reference_fallback_chain(
        locale,
        policy=fallback_policy,
        fallback_chain=fallback_chain,
        fallback_presets=fallback_presets,
    )
    default_locale = chain[0] if chain else "EN"
    resolution = resolve_source_reference_locale(
        requested,
        available_locales=available_locales,
        fallback_chain=chain[1:],
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
    current_fallback_policy: str,
    current_fallback_chain: Iterable[str] = (),
    current_fallback_presets: Mapping[str, Iterable[str]] | None = None,
    overrides: MutableMapping[str, str],  # kept for call-shape stability
    extras: MutableMapping[str, str],
) -> tuple[str, tuple[str, ...], dict[str, tuple[str, ...]], bool]:
    """Apply source reference preferences."""
    _ = overrides
    current_chain = normalize_source_reference_fallback_chain(
        current_fallback_chain,
        default=(),
    )
    current_presets = normalize_source_reference_fallback_presets(
        current_fallback_presets or {}
    )
    policy = normalize_source_reference_fallback_policy(
        values.get("source_reference_fallback_policy", current_fallback_policy),
        default=current_fallback_policy,
    )
    chain = normalize_source_reference_fallback_chain(
        values.get("source_reference_fallback_chain", current_chain),
        default=current_chain,
    )
    if "source_reference_fallback_presets" in values:
        presets = normalize_source_reference_fallback_presets(
            values.get("source_reference_fallback_presets")
        )
    else:
        presets = current_presets
    changed = (
        policy != current_fallback_policy
        or chain != current_chain
        or presets != current_presets
    )
    if changed:
        extras["SOURCE_REFERENCE_FALLBACK_POLICY"] = policy
        if chain:
            extras[_FALLBACK_CHAIN_EXTRA_KEY] = (
                serialize_source_reference_fallback_chain(chain)
            )
        else:
            extras.pop(_FALLBACK_CHAIN_EXTRA_KEY, None)
        if presets:
            extras[_FALLBACK_PRESETS_EXTRA_KEY] = (
                dump_source_reference_fallback_presets(presets)
            )
        else:
            extras.pop(_FALLBACK_PRESETS_EXTRA_KEY, None)
    return policy, chain, presets, changed


def refresh_source_reference_from_window(win: object) -> None:
    """Refresh source reference from window."""
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
    """Execute effective source reference mode for window."""
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
        fallback_chain=_window_source_reference_fallback_chain(win),
        fallback_presets=_window_source_reference_fallback_presets(win),
    )


def sync_source_reference_override_ui_for_window(win: object) -> None:
    """Synchronize source reference override ui for window."""
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
    fallback_chain = source_reference_fallback_chain(
        active_locale,
        policy=win._source_reference_fallback_policy,
        fallback_chain=_window_source_reference_fallback_chain(win),
        fallback_presets=_window_source_reference_fallback_presets(win),
    )
    sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
        fallback_chain=fallback_chain,
    )


def sync_source_reference_mode_for_window(win: object, *, persist: bool) -> None:
    """Synchronize source reference mode for window."""
    from .source_reference_ui import sync_source_reference_combo

    selected_locale = win._selected_locales[0] if win._selected_locales else "EN"
    current_path = win._current_pf.path if win._current_pf else None
    current_locale = win._locale_for_path(current_path) if current_path else None
    available_locales = _window_available_source_reference_locales(
        win,
        exclude_locale=current_locale,
    )
    fallback_chain = source_reference_fallback_chain(
        selected_locale,
        policy=win._source_reference_fallback_policy,
        fallback_chain=_window_source_reference_fallback_chain(win),
        fallback_presets=_window_source_reference_fallback_presets(win),
    )
    win._source_reference_mode = sync_source_reference_combo(
        win.source_ref_combo,
        current_mode=win._source_reference_mode,
        selected_locales=available_locales,
        all_locales=None,
        fallback_chain=fallback_chain,
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
    policy, chain, presets, changed = apply_source_reference_preferences(
        values=values,
        current_fallback_policy=win._source_reference_fallback_policy,
        current_fallback_chain=_window_source_reference_fallback_chain(win),
        current_fallback_presets=_window_source_reference_fallback_presets(win),
        overrides=win._source_reference_file_overrides,
        extras=win._prefs_extras,
    )
    win._source_reference_fallback_policy = policy
    win._source_reference_fallback_chain = chain
    win._source_reference_fallback_presets = presets
    if not changed:
        return False
    win._search_rows_cache.clear()
    sync_source_reference_override_ui_for_window(win)
    refresh_source_reference_from_window(win)
    return True
