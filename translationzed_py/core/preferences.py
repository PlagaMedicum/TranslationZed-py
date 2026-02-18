"""Load, normalize, and persist user preferences."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Any

from translationzed_py.core.app_config import (
    LEGACY_CONFIG_DIR,
)
from translationzed_py.core.app_config import (
    load as _load_app_config,
)
from translationzed_py.core.atomic_io import write_text_atomic

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}
_EXTRAS_KEY = "__extras__"

_DEFAULTS: dict[str, Any] = {
    "prompt_write_on_exit": True,
    "wrap_text": False,
    "large_text_optimizations": True,
    "qa_check_trailing": True,
    "qa_check_newlines": True,
    "qa_check_escapes": False,
    "qa_check_same_as_source": False,
    "qa_auto_refresh": False,
    "qa_auto_mark_for_review": False,
    "qa_auto_mark_touched_for_review": False,
    "last_root": "",
    "last_locales": [],
    "window_geometry": "",
    "default_root": "",
    "search_scope": "FILE",
    "replace_scope": "FILE",
    "tm_import_dir": "",
}
_REQUIRED_PREF_KEYS = (
    "prompt_write_on_exit",
    "wrap_text",
    "large_text_optimizations",
    "qa_check_trailing",
    "qa_check_newlines",
    "qa_check_escapes",
    "qa_check_same_as_source",
    "qa_auto_refresh",
    "qa_auto_mark_for_review",
    "qa_auto_mark_touched_for_review",
    "search_scope",
    "replace_scope",
    "tm_import_dir",
)


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def _config_dir(root: Path | None = None) -> Path:
    base = Path(root).resolve() if root is not None else _runtime_root()
    cfg = _load_app_config(base)
    return base / cfg.config_dir


def _legacy_config_dir(root: Path | None = None) -> Path:
    base = Path(root).resolve() if root is not None else _runtime_root()
    return base / LEGACY_CONFIG_DIR


def _config_path(root: Path | None = None) -> Path:
    return _config_dir(root) / "settings.env"


def _legacy_config_path(root: Path | None = None) -> Path:
    return _legacy_config_dir(root) / "settings.env"


def _existing_config_path(root: Path | None = None) -> Path:
    current = _config_path(root)
    if current.exists():
        return current
    legacy = _legacy_config_path(root)
    if legacy != current and legacy.exists():
        return legacy
    return current


def _default_tm_import_dir(root: Path | None = None) -> str:
    return str(_canonical_tm_import_dir(root))


def _canonical_tm_import_dir(root: Path | None = None) -> Path:
    base = Path(root).resolve() if root is not None else _runtime_root()
    return (base / ".tzp" / "tms").resolve()


def _legacy_tm_import_dirs(root: Path | None = None) -> tuple[Path, ...]:
    base = Path(root).resolve() if root is not None else _runtime_root()
    return (
        (base / ".tzp" / "imported_tms").resolve(),
        (base / "imported_tms").resolve(),
    )


def _normalize_tm_import_dir(value: object, root: Path | None = None) -> str:
    canonical = _canonical_tm_import_dir(root)
    raw = str(value).strip()
    if not raw:
        return str(canonical)
    path = Path(raw).expanduser().resolve()
    if path == canonical:
        return str(canonical)
    if path in _legacy_tm_import_dirs(root):
        return str(canonical)
    return str(path)


def _migrate_legacy_tm_import_dirs(root: Path | None = None) -> bool:
    canonical = _canonical_tm_import_dir(root)
    changed = False
    with contextlib.suppress(OSError):
        canonical.mkdir(parents=True, exist_ok=True)
    for legacy in _legacy_tm_import_dirs(root):
        if legacy == canonical or not legacy.exists() or not legacy.is_dir():
            continue
        for source in sorted(legacy.iterdir()):
            if not source.is_file():
                continue
            dest = canonical / source.name
            if dest.exists():
                idx = 1
                while True:
                    candidate = canonical / f"{source.stem}_{idx}{source.suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    idx += 1
            try:
                source.replace(dest)
            except OSError:
                continue
            changed = True
        with contextlib.suppress(OSError):
            legacy.rmdir()
    return changed


def _parse_env(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    out: dict[str, Any] = {}
    extras: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "PROMPT_WRITE_ON_EXIT":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["prompt_write_on_exit"] = True
                elif val in _BOOL_FALSE:
                    out["prompt_write_on_exit"] = False
            elif key == "WRAP_TEXT":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["wrap_text"] = True
                elif val in _BOOL_FALSE:
                    out["wrap_text"] = False
            elif key == "LARGE_TEXT_OPTIMIZATIONS":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["large_text_optimizations"] = True
                elif val in _BOOL_FALSE:
                    out["large_text_optimizations"] = False
            elif key == "QA_CHECK_TRAILING":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_check_trailing"] = True
                elif val in _BOOL_FALSE:
                    out["qa_check_trailing"] = False
            elif key == "QA_CHECK_NEWLINES":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_check_newlines"] = True
                elif val in _BOOL_FALSE:
                    out["qa_check_newlines"] = False
            elif key == "QA_CHECK_ESCAPES":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_check_escapes"] = True
                elif val in _BOOL_FALSE:
                    out["qa_check_escapes"] = False
            elif key == "QA_CHECK_SAME_AS_SOURCE":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_check_same_as_source"] = True
                elif val in _BOOL_FALSE:
                    out["qa_check_same_as_source"] = False
            elif key == "QA_AUTO_REFRESH":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_auto_refresh"] = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_refresh"] = False
            elif key == "QA_AUTO_MARK_FOR_REVIEW":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_auto_mark_for_review"] = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_mark_for_review"] = False
            elif key == "QA_AUTO_MARK_TOUCHED_FOR_REVIEW":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_auto_mark_touched_for_review"] = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_mark_touched_for_review"] = False
            elif key == "LAST_ROOT":
                out["last_root"] = value
            elif key == "LAST_LOCALES":
                out["last_locales"] = [v.strip() for v in value.split(",") if v.strip()]
            elif key == "WINDOW_GEOMETRY":
                out["window_geometry"] = value
            elif key == "DEFAULT_ROOT":
                out["default_root"] = value
            elif key == "SEARCH_SCOPE":
                value = value.upper()
                if value in {"FILE", "LOCALE", "POOL"}:
                    out["search_scope"] = value
            elif key == "REPLACE_SCOPE":
                value = value.upper()
                if value in {"FILE", "LOCALE", "POOL"}:
                    out["replace_scope"] = value
            elif key == "TM_IMPORT_DIR":
                out["tm_import_dir"] = value
            else:
                extras[key] = value
    except OSError:
        return {}
    if extras:
        out[_EXTRAS_KEY] = extras
    return out


def load(root: Path | None = None) -> dict[str, Any]:
    """
    Load preferences from disk without side effects.

    Unknown keys are preserved.
    """
    merged = dict(_DEFAULTS)
    parsed = _parse_env(_existing_config_path(root))
    extras = dict(parsed.pop(_EXTRAS_KEY, {}))
    merged.update(parsed)
    merged["tm_import_dir"] = _normalize_tm_import_dir(
        merged.get("tm_import_dir", ""),
        root,
    )
    if extras:
        merged[_EXTRAS_KEY] = extras
    return merged


def ensure_defaults(root: Path | None = None) -> dict[str, Any]:
    """
    Ensure settings file exists and contains required keys.

    Best effort only: returns loaded prefs even when write fails.
    """
    path = _config_path(root)
    parsed = _parse_env(_existing_config_path(root))
    prefs = dict(_DEFAULTS)
    extras = dict(parsed.pop(_EXTRAS_KEY, {}))
    prefs.update(parsed)
    prefs["tm_import_dir"] = _normalize_tm_import_dir(
        prefs.get("tm_import_dir", ""),
        root,
    )
    migrated_tm_dirs = _migrate_legacy_tm_import_dirs(root)
    if extras:
        prefs[_EXTRAS_KEY] = extras
    parsed_tm_dir = str(parsed.get("tm_import_dir", "")).strip()
    if parsed_tm_dir:
        parsed_tm_dir_norm = str(Path(parsed_tm_dir).expanduser().resolve())
        tm_dir_changed = (
            _normalize_tm_import_dir(parsed_tm_dir, root) != parsed_tm_dir_norm
        )
    else:
        tm_dir_changed = False
    if (
        not path.exists()
        or any(key not in parsed for key in _REQUIRED_PREF_KEYS)
        or tm_dir_changed
        or migrated_tm_dirs
    ):
        with contextlib.suppress(OSError):
            save(prefs, root)
    return prefs


def save(prefs: dict[str, Any], root: Path | None = None) -> None:
    """Persist preferences to disk (atomic replace)."""
    path = _config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    extras: dict[str, str] = dict(prefs.get(_EXTRAS_KEY, {}))
    known_keys = {
        "PROMPT_WRITE_ON_EXIT",
        "WRAP_TEXT",
        "LARGE_TEXT_OPTIMIZATIONS",
        "QA_CHECK_TRAILING",
        "QA_CHECK_NEWLINES",
        "QA_CHECK_ESCAPES",
        "QA_CHECK_SAME_AS_SOURCE",
        "QA_AUTO_REFRESH",
        "QA_AUTO_MARK_FOR_REVIEW",
        "QA_AUTO_MARK_TOUCHED_FOR_REVIEW",
        "LAST_ROOT",
        "LAST_LOCALES",
        "WINDOW_GEOMETRY",
        "DEFAULT_ROOT",
        "SEARCH_SCOPE",
        "REPLACE_SCOPE",
        "TM_IMPORT_DIR",
    }
    lines = [
        f"PROMPT_WRITE_ON_EXIT={'true' if prefs.get('prompt_write_on_exit', True) else 'false'}",
        f"WRAP_TEXT={'true' if prefs.get('wrap_text', False) else 'false'}",
        (
            "LARGE_TEXT_OPTIMIZATIONS="
            f"{'true' if prefs.get('large_text_optimizations', True) else 'false'}"
        ),
        f"QA_CHECK_TRAILING={'true' if prefs.get('qa_check_trailing', True) else 'false'}",
        f"QA_CHECK_NEWLINES={'true' if prefs.get('qa_check_newlines', True) else 'false'}",
        f"QA_CHECK_ESCAPES={'true' if prefs.get('qa_check_escapes', False) else 'false'}",
        (
            "QA_CHECK_SAME_AS_SOURCE="
            f"{'true' if prefs.get('qa_check_same_as_source', False) else 'false'}"
        ),
        (
            "QA_AUTO_REFRESH="
            f"{'true' if prefs.get('qa_auto_refresh', False) else 'false'}"
        ),
        (
            "QA_AUTO_MARK_FOR_REVIEW="
            f"{'true' if prefs.get('qa_auto_mark_for_review', False) else 'false'}"
        ),
        (
            "QA_AUTO_MARK_TOUCHED_FOR_REVIEW="
            f"{'true' if prefs.get('qa_auto_mark_touched_for_review', False) else 'false'}"
        ),
    ]
    last_root = str(prefs.get("last_root", "")).strip()
    if last_root:
        lines.append(f"LAST_ROOT={last_root}")
    last_locales = prefs.get("last_locales", [])
    if isinstance(last_locales, list | tuple) and last_locales:
        lines.append(f"LAST_LOCALES={','.join(str(v) for v in last_locales)}")
    geometry = str(prefs.get("window_geometry", "")).strip()
    if geometry:
        lines.append(f"WINDOW_GEOMETRY={geometry}")
    default_root = str(prefs.get("default_root", "")).strip()
    if default_root:
        lines.append(f"DEFAULT_ROOT={default_root}")
    search_scope = str(prefs.get("search_scope", "FILE")).strip().upper()
    if search_scope:
        lines.append(f"SEARCH_SCOPE={search_scope}")
    replace_scope = str(prefs.get("replace_scope", "FILE")).strip().upper()
    if replace_scope:
        lines.append(f"REPLACE_SCOPE={replace_scope}")
    tm_import_dir = str(prefs.get("tm_import_dir", "")).strip()
    if tm_import_dir:
        lines.append(f"TM_IMPORT_DIR={tm_import_dir}")
    for key, value in extras.items():
        if key in known_keys:
            continue
        lines.append(f"{key}={value}")
    lines.append("")
    raw = "\n".join(lines)
    write_text_atomic(path, raw, encoding="utf-8")
