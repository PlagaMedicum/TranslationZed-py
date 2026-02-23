"""Preferences service module."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .languagetool import default_server_url as _default_lt_server_url
from .languagetool import dump_language_map as _dump_lt_language_map
from .languagetool import load_language_map as _load_lt_language_map
from .languagetool import normalize_editor_mode as _normalize_lt_editor_mode
from .languagetool import normalize_timeout_ms as _normalize_lt_timeout_ms
from .preferences import ensure_defaults as _ensure_preferences
from .preferences import load as _load_preferences
from .preferences import save as _save_preferences

_VALID_SCOPES = {"FILE", "LOCALE", "POOL"}
_QA_LT_MAX_ROWS_DEFAULT = 500
_QA_LT_MAX_ROWS_MIN = 1
_QA_LT_MAX_ROWS_MAX = 5000


@dataclass(frozen=True, slots=True)
class StartupRootResolution:
    """Represent StartupRootResolution."""

    root: Path | None
    default_root: str
    requires_picker: bool


@dataclass(frozen=True, slots=True)
class LoadedPreferences:
    """Represent LoadedPreferences."""

    prompt_write_on_exit: bool
    wrap_text: bool
    large_text_optimizations: bool
    qa_check_trailing: bool
    qa_check_newlines: bool
    qa_check_escapes: bool
    qa_check_same_as_source: bool
    qa_auto_refresh: bool
    qa_auto_mark_for_review: bool
    qa_auto_mark_touched_for_review: bool
    qa_check_languagetool: bool
    qa_languagetool_max_rows: int
    qa_languagetool_automark: bool
    default_root: str
    search_scope: str
    replace_scope: str
    last_locales: list[str]
    last_root: str
    extras: dict[str, str]
    tm_import_dir: str
    lt_editor_mode: str
    lt_server_url: str
    lt_timeout_ms: int
    lt_picky_mode: bool
    lt_locale_map: str
    window_geometry: str
    patched_raw: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class PreferencesService:
    """Represent PreferencesService."""

    def normalize_scope(self, value: object, *, default: str = "FILE") -> str:
        """Normalize scope."""
        return normalize_scope(value, default=default)

    def resolve_startup_root(
        self, *, project_root: str | None
    ) -> StartupRootResolution:
        """Resolve startup root."""
        prefs_global = _load_preferences(None)
        return resolve_startup_root(
            project_root=project_root,
            saved_default_root=str(prefs_global.get("default_root", "")),
        )

    def persist_default_root(self, default_root: str) -> None:
        """Execute persist default root."""
        raw = default_root.strip()
        if not raw:
            return
        try:
            prefs = _load_preferences(None)
            prefs["default_root"] = raw
            _save_preferences(prefs, None)
        except Exception:
            return

    def load_normalized_preferences(
        self,
        *,
        fallback_default_root: str,
        fallback_last_root: str,
        default_tm_import_dir: str,
        test_mode: bool,
        layout_reset_rev: str = "3",
    ) -> LoadedPreferences:
        """Load normalized preferences."""
        _ensure_preferences(None)
        raw = _load_preferences(None)
        normalized = normalize_loaded_preferences(
            raw,
            fallback_default_root=fallback_default_root,
            fallback_last_root=fallback_last_root,
            default_tm_import_dir=default_tm_import_dir,
            test_mode=test_mode,
            layout_reset_rev=layout_reset_rev,
        )
        if normalized.patched_raw is not None:
            with contextlib.suppress(Exception):
                _save_preferences(normalized.patched_raw, None)
        return normalized

    def persist_main_window_preferences(
        self,
        *,
        prompt_write_on_exit: bool,
        wrap_text: bool,
        large_text_optimizations: bool,
        last_root: str,
        last_locales: list[str],
        window_geometry: str,
        default_root: str,
        tm_import_dir: str,
        search_scope: str,
        replace_scope: str,
        extras: dict[str, str],
        qa_check_trailing: bool = True,
        qa_check_newlines: bool = True,
        qa_check_escapes: bool = False,
        qa_check_same_as_source: bool = False,
        qa_auto_refresh: bool = False,
        qa_auto_mark_for_review: bool = False,
        qa_auto_mark_touched_for_review: bool = False,
        qa_check_languagetool: bool = False,
        qa_languagetool_max_rows: int = _QA_LT_MAX_ROWS_DEFAULT,
        qa_languagetool_automark: bool = False,
        lt_editor_mode: str = "auto",
        lt_server_url: str = "",
        lt_timeout_ms: int = 1200,
        lt_picky_mode: bool = False,
        lt_locale_map: str = "{}",
    ) -> None:
        """Execute persist main window preferences."""
        prefs = build_persist_payload(
            prompt_write_on_exit=prompt_write_on_exit,
            wrap_text=wrap_text,
            large_text_optimizations=large_text_optimizations,
            qa_check_trailing=qa_check_trailing,
            qa_check_newlines=qa_check_newlines,
            qa_check_escapes=qa_check_escapes,
            qa_check_same_as_source=qa_check_same_as_source,
            qa_auto_refresh=qa_auto_refresh,
            qa_auto_mark_for_review=qa_auto_mark_for_review,
            qa_auto_mark_touched_for_review=qa_auto_mark_touched_for_review,
            qa_check_languagetool=qa_check_languagetool,
            qa_languagetool_max_rows=qa_languagetool_max_rows,
            qa_languagetool_automark=qa_languagetool_automark,
            last_root=last_root,
            last_locales=last_locales,
            window_geometry=window_geometry,
            default_root=default_root,
            tm_import_dir=tm_import_dir,
            lt_editor_mode=lt_editor_mode,
            lt_server_url=lt_server_url,
            lt_timeout_ms=lt_timeout_ms,
            lt_picky_mode=lt_picky_mode,
            lt_locale_map=lt_locale_map,
            search_scope=search_scope,
            replace_scope=replace_scope,
            extras=extras,
        )
        with contextlib.suppress(Exception):
            _save_preferences(prefs, None)
        self.persist_default_root(default_root)


def resolve_startup_root(
    *, project_root: str | None, saved_default_root: str
) -> StartupRootResolution:
    """Resolve startup root."""
    if project_root:
        return StartupRootResolution(
            root=Path(project_root).resolve(),
            default_root="",
            requires_picker=False,
        )
    default_root = saved_default_root.strip()
    if default_root and Path(default_root).exists():
        return StartupRootResolution(
            root=Path(default_root).resolve(),
            default_root=default_root,
            requires_picker=False,
        )
    return StartupRootResolution(root=None, default_root="", requires_picker=True)


def normalize_scope(value: object, *, default: str = "FILE") -> str:
    """Normalize scope."""
    raw = str(value).upper().strip()
    if raw in _VALID_SCOPES:
        return raw
    return default


def normalize_qa_languagetool_max_rows(value: object) -> int:
    """Normalize QA LanguageTool row cap."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = _QA_LT_MAX_ROWS_DEFAULT
    return max(_QA_LT_MAX_ROWS_MIN, min(_QA_LT_MAX_ROWS_MAX, parsed))


def resolve_qa_preferences(
    values: Mapping[str, object],
    *,
    current: tuple[bool, bool, bool, bool, bool, bool, bool],
) -> tuple[tuple[bool, bool, bool, bool, bool, bool, bool], bool]:
    """Resolve qa preferences."""
    updated = (
        bool(values.get("qa_check_trailing", current[0])),
        bool(values.get("qa_check_newlines", current[1])),
        bool(values.get("qa_check_escapes", current[2])),
        bool(values.get("qa_check_same_as_source", current[3])),
        bool(values.get("qa_auto_refresh", current[4])),
        bool(values.get("qa_auto_mark_for_review", current[5])),
        bool(values.get("qa_auto_mark_touched_for_review", current[6])),
    )
    return updated, updated != current


def normalize_loaded_preferences(
    raw: dict[str, Any],
    *,
    fallback_default_root: str,
    fallback_last_root: str,
    default_tm_import_dir: str,
    test_mode: bool,
    layout_reset_rev: str = "3",
) -> LoadedPreferences:
    """Normalize loaded preferences."""
    prompt_write_on_exit = bool(raw.get("prompt_write_on_exit", True))
    if test_mode:
        prompt_write_on_exit = False

    wrap_text = bool(raw.get("wrap_text", False))
    large_text_optimizations = bool(raw.get("large_text_optimizations", True))
    qa_check_trailing = bool(raw.get("qa_check_trailing", True))
    qa_check_newlines = bool(raw.get("qa_check_newlines", True))
    qa_check_escapes = bool(raw.get("qa_check_escapes", False))
    qa_check_same_as_source = bool(raw.get("qa_check_same_as_source", False))
    qa_auto_refresh = bool(raw.get("qa_auto_refresh", False))
    qa_auto_mark_for_review = bool(raw.get("qa_auto_mark_for_review", False))
    qa_auto_mark_touched_for_review = bool(
        raw.get("qa_auto_mark_touched_for_review", False)
    )
    qa_check_languagetool = bool(raw.get("qa_check_languagetool", False))
    qa_languagetool_max_rows = normalize_qa_languagetool_max_rows(
        raw.get("qa_languagetool_max_rows", _QA_LT_MAX_ROWS_DEFAULT)
    )
    qa_languagetool_automark = bool(raw.get("qa_languagetool_automark", False))
    default_root = str(raw.get("default_root", "") or fallback_default_root)
    search_scope = normalize_scope(raw.get("search_scope", "FILE"), default="FILE")
    replace_scope = normalize_scope(raw.get("replace_scope", "FILE"), default="FILE")
    last_locales = list(raw.get("last_locales", []) or [])
    last_root = str(raw.get("last_root", "") or fallback_last_root)
    extras = dict(raw.get("__extras__", {}))
    tm_import_dir = str(raw.get("tm_import_dir", "")).strip() or default_tm_import_dir
    lt_editor_mode = _normalize_lt_editor_mode(raw.get("lt_editor_mode", "auto"))
    lt_server_url = (
        str(raw.get("lt_server_url", "")).strip() or _default_lt_server_url()
    )
    lt_timeout_ms = _normalize_lt_timeout_ms(raw.get("lt_timeout_ms", 1200))
    lt_picky_mode = bool(raw.get("lt_picky_mode", False))
    lt_locale_map_data = _load_lt_language_map(raw.get("lt_locale_map", "{}"))
    lt_locale_map = _dump_lt_language_map(lt_locale_map_data) if lt_locale_map_data else "{}"
    window_geometry = str(raw.get("window_geometry", "")).strip()

    patched_raw: dict[str, Any] | None = None
    if str(extras.get("LAYOUT_RESET_REV", "")).strip() != layout_reset_rev:
        window_geometry = ""
        for key in (
            "TABLE_KEY_WIDTH",
            "TABLE_STATUS_WIDTH",
            "TABLE_SRC_RATIO",
            "TREE_PANEL_WIDTH",
        ):
            extras.pop(key, None)
        extras["LAYOUT_RESET_REV"] = layout_reset_rev
        patched_raw = dict(raw)
        patched_raw["window_geometry"] = ""
        patched_raw["__extras__"] = dict(extras)

    return LoadedPreferences(
        prompt_write_on_exit=prompt_write_on_exit,
        wrap_text=wrap_text,
        large_text_optimizations=large_text_optimizations,
        qa_check_trailing=qa_check_trailing,
        qa_check_newlines=qa_check_newlines,
        qa_check_escapes=qa_check_escapes,
        qa_check_same_as_source=qa_check_same_as_source,
        qa_auto_refresh=qa_auto_refresh,
        qa_auto_mark_for_review=qa_auto_mark_for_review,
        qa_auto_mark_touched_for_review=qa_auto_mark_touched_for_review,
        qa_check_languagetool=qa_check_languagetool,
        qa_languagetool_max_rows=qa_languagetool_max_rows,
        qa_languagetool_automark=qa_languagetool_automark,
        default_root=default_root,
        search_scope=search_scope,
        replace_scope=replace_scope,
        last_locales=last_locales,
        last_root=last_root,
        extras=extras,
        tm_import_dir=tm_import_dir,
        lt_editor_mode=lt_editor_mode,
        lt_server_url=lt_server_url,
        lt_timeout_ms=lt_timeout_ms,
        lt_picky_mode=lt_picky_mode,
        lt_locale_map=lt_locale_map,
        window_geometry=window_geometry,
        patched_raw=patched_raw,
    )


def build_persist_payload(
    *,
    prompt_write_on_exit: bool,
    wrap_text: bool,
    large_text_optimizations: bool,
    last_root: str,
    last_locales: list[str],
    window_geometry: str,
    default_root: str,
    tm_import_dir: str,
    search_scope: str,
    replace_scope: str,
    extras: dict[str, str],
    qa_check_trailing: bool = True,
    qa_check_newlines: bool = True,
    qa_check_escapes: bool = False,
    qa_check_same_as_source: bool = False,
    qa_auto_refresh: bool = False,
    qa_auto_mark_for_review: bool = False,
    qa_auto_mark_touched_for_review: bool = False,
    qa_check_languagetool: bool = False,
    qa_languagetool_max_rows: int = _QA_LT_MAX_ROWS_DEFAULT,
    qa_languagetool_automark: bool = False,
    lt_editor_mode: str = "auto",
    lt_server_url: str = "",
    lt_timeout_ms: int = 1200,
    lt_picky_mode: bool = False,
    lt_locale_map: str = "{}",
) -> dict[str, Any]:
    """Build persist payload."""
    return {
        "prompt_write_on_exit": bool(prompt_write_on_exit),
        "wrap_text": bool(wrap_text),
        "large_text_optimizations": bool(large_text_optimizations),
        "qa_check_trailing": bool(qa_check_trailing),
        "qa_check_newlines": bool(qa_check_newlines),
        "qa_check_escapes": bool(qa_check_escapes),
        "qa_check_same_as_source": bool(qa_check_same_as_source),
        "qa_auto_refresh": bool(qa_auto_refresh),
        "qa_auto_mark_for_review": bool(qa_auto_mark_for_review),
        "qa_auto_mark_touched_for_review": bool(qa_auto_mark_touched_for_review),
        "qa_check_languagetool": bool(qa_check_languagetool),
        "qa_languagetool_max_rows": normalize_qa_languagetool_max_rows(
            qa_languagetool_max_rows
        ),
        "qa_languagetool_automark": bool(qa_languagetool_automark),
        "last_root": str(last_root),
        "last_locales": list(last_locales),
        "window_geometry": str(window_geometry),
        "default_root": str(default_root).strip(),
        "tm_import_dir": str(tm_import_dir).strip(),
        "lt_editor_mode": _normalize_lt_editor_mode(lt_editor_mode),
        "lt_server_url": str(lt_server_url).strip() or _default_lt_server_url(),
        "lt_timeout_ms": _normalize_lt_timeout_ms(lt_timeout_ms),
        "lt_picky_mode": bool(lt_picky_mode),
        "lt_locale_map": (
            _dump_lt_language_map(_load_lt_language_map(lt_locale_map)) or "{}"
        ),
        "search_scope": normalize_scope(search_scope, default="FILE"),
        "replace_scope": normalize_scope(replace_scope, default="FILE"),
        "__extras__": dict(extras),
    }
