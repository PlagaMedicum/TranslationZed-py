from __future__ import annotations

from pathlib import Path
from typing import Any

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.atomic_io import write_text_atomic

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}
_EXTRAS_KEY = "__extras__"

_DEFAULTS: dict[str, Any] = {
    "prompt_write_on_exit": True,
    "wrap_text": False,
    "last_root": "",
    "last_locales": [],
    "window_geometry": "",
    "default_root": "",
    "search_scope": "FILE",
    "replace_scope": "FILE",
}


def _config_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    cfg = _load_app_config(root)
    return base / cfg.config_dir


def _config_path(root: Path | None = None) -> Path:
    return _config_dir(root) / "settings.env"


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
            else:
                extras[key] = value
    except OSError:
        return {}
    if extras:
        out[_EXTRAS_KEY] = extras
    return out


def _candidate_roots(root: Path | None) -> list[Path]:
    roots = [Path.cwd()]
    if root is not None:
        roots.append(root)
    # de-dup while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for entry in roots:
        entry = entry.resolve()
        if entry in seen:
            continue
        seen.add(entry)
        out.append(entry)
    return out


def load(root: Path | None = None) -> dict[str, Any]:
    """
    Load preferences from disk, falling back to defaults.
    Unknown keys are preserved.
    """
    merged = dict(_DEFAULTS)
    extras: dict[str, str] = {}
    for base in _candidate_roots(root):
        parsed = _parse_env(_config_path(base))
        extras.update(parsed.pop(_EXTRAS_KEY, {}))
        merged.update(parsed)
    if extras:
        merged[_EXTRAS_KEY] = extras
    return merged


def save(prefs: dict[str, Any], root: Path | None = None) -> None:
    """Persist preferences to disk (atomic replace)."""
    path = _config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    extras: dict[str, str] = dict(prefs.get(_EXTRAS_KEY, {}))
    known_keys = {
        "PROMPT_WRITE_ON_EXIT",
        "WRAP_TEXT",
        "LAST_ROOT",
        "LAST_LOCALES",
        "WINDOW_GEOMETRY",
        "DEFAULT_ROOT",
        "SEARCH_SCOPE",
        "REPLACE_SCOPE",
    }
    lines = [
        f"PROMPT_WRITE_ON_EXIT={'true' if prefs.get('prompt_write_on_exit', True) else 'false'}",
        f"WRAP_TEXT={'true' if prefs.get('wrap_text', False) else 'false'}",
    ]
    last_root = str(prefs.get("last_root", "")).strip()
    if last_root:
        lines.append(f"LAST_ROOT={last_root}")
    last_locales = prefs.get("last_locales", [])
    if isinstance(last_locales, (list, tuple)) and last_locales:
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
    for key, value in extras.items():
        if key in known_keys:
            continue
        lines.append(f"{key}={value}")
    lines.append("")
    raw = "\n".join(lines)
    write_text_atomic(path, raw, encoding="utf-8")
