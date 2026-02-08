from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VALID_SCOPES = {"FILE", "LOCALE", "POOL"}


@dataclass(frozen=True, slots=True)
class StartupRootResolution:
    root: Path | None
    default_root: str
    requires_picker: bool


@dataclass(frozen=True, slots=True)
class LoadedPreferences:
    prompt_write_on_exit: bool
    wrap_text: bool
    large_text_optimizations: bool
    default_root: str
    search_scope: str
    replace_scope: str
    last_locales: list[str]
    last_root: str
    extras: dict[str, str]
    tm_import_dir: str
    window_geometry: str
    patched_raw: dict[str, Any] | None


def resolve_startup_root(
    *, project_root: str | None, saved_default_root: str
) -> StartupRootResolution:
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
    raw = str(value).upper().strip()
    if raw in _VALID_SCOPES:
        return raw
    return default


def normalize_loaded_preferences(
    raw: dict[str, Any],
    *,
    fallback_default_root: str,
    fallback_last_root: str,
    default_tm_import_dir: str,
    test_mode: bool,
    layout_reset_rev: str = "3",
) -> LoadedPreferences:
    prompt_write_on_exit = bool(raw.get("prompt_write_on_exit", True))
    if test_mode:
        prompt_write_on_exit = False

    wrap_text = bool(raw.get("wrap_text", False))
    large_text_optimizations = bool(raw.get("large_text_optimizations", True))
    default_root = str(raw.get("default_root", "") or fallback_default_root)
    search_scope = normalize_scope(raw.get("search_scope", "FILE"), default="FILE")
    replace_scope = normalize_scope(raw.get("replace_scope", "FILE"), default="FILE")
    last_locales = list(raw.get("last_locales", []) or [])
    last_root = str(raw.get("last_root", "") or fallback_last_root)
    extras = dict(raw.get("__extras__", {}))
    tm_import_dir = str(raw.get("tm_import_dir", "")).strip() or default_tm_import_dir
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
        default_root=default_root,
        search_scope=search_scope,
        replace_scope=replace_scope,
        last_locales=last_locales,
        last_root=last_root,
        extras=extras,
        tm_import_dir=tm_import_dir,
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
) -> dict[str, Any]:
    return {
        "prompt_write_on_exit": bool(prompt_write_on_exit),
        "wrap_text": bool(wrap_text),
        "large_text_optimizations": bool(large_text_optimizations),
        "last_root": str(last_root),
        "last_locales": list(last_locales),
        "window_geometry": str(window_geometry),
        "default_root": str(default_root).strip(),
        "tm_import_dir": str(tm_import_dir).strip(),
        "search_scope": normalize_scope(search_scope, default="FILE"),
        "replace_scope": normalize_scope(replace_scope, default="FILE"),
        "__extras__": dict(extras),
    }
