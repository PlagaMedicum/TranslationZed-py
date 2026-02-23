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
from translationzed_py.core.languagetool import (
    default_server_url as _default_lt_server_url,
)
from translationzed_py.core.languagetool import (
    dump_language_map as _dump_lt_language_map,
)
from translationzed_py.core.languagetool import (
    load_language_map as _load_lt_language_map,
)
from translationzed_py.core.languagetool import (
    normalize_editor_mode as _normalize_lt_editor_mode,
)
from translationzed_py.core.languagetool import (
    normalize_timeout_ms as _normalize_lt_timeout_ms,
)

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}
_EXTRAS_KEY = "__extras__"
_QA_LT_MAX_ROWS_DEFAULT = 500
_QA_LT_MAX_ROWS_MIN = 1
_QA_LT_MAX_ROWS_MAX = 5000


def _normalize_qa_languagetool_max_rows(value: object) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = _QA_LT_MAX_ROWS_DEFAULT
    return max(_QA_LT_MAX_ROWS_MIN, min(_QA_LT_MAX_ROWS_MAX, parsed))


def _normalize_lt_locale_map(value: object) -> str:
    mapping = _load_lt_language_map(value)
    if mapping:
        return _dump_lt_language_map(mapping)
    raw = str(value or "").strip()
    if raw in {"", "{}"}:
        return raw
    return "{}"


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
    "qa_auto_mark_translated_for_review": False,
    "qa_auto_mark_proofread_for_review": False,
    "last_root": "",
    "last_locales": [],
    "window_geometry": "",
    "default_root": "",
    "search_scope": "FILE",
    "replace_scope": "FILE",
    "tm_import_dir": "",
    "lt_editor_mode": "auto",
    "lt_server_url": _default_lt_server_url(),
    "lt_timeout_ms": 1200,
    "lt_picky_mode": False,
    "lt_locale_map": "{}",
    "qa_check_languagetool": False,
    "qa_languagetool_max_rows": _QA_LT_MAX_ROWS_DEFAULT,
    "qa_languagetool_automark": False,
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
    "qa_auto_mark_translated_for_review",
    "qa_auto_mark_proofread_for_review",
    "search_scope",
    "replace_scope",
    "tm_import_dir",
    "lt_editor_mode",
    "lt_server_url",
    "lt_timeout_ms",
    "lt_picky_mode",
    "lt_locale_map",
    "qa_check_languagetool",
    "qa_languagetool_max_rows",
    "qa_languagetool_automark",
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
    legacy_touched: bool | None = None
    translated_seen = False
    proofread_seen = False
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
                    legacy_touched = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_mark_touched_for_review"] = False
                    legacy_touched = False
            elif key == "QA_AUTO_MARK_TRANSLATED_FOR_REVIEW":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_auto_mark_translated_for_review"] = True
                    translated_seen = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_mark_translated_for_review"] = False
                    translated_seen = True
            elif key == "QA_AUTO_MARK_PROOFREAD_FOR_REVIEW":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_auto_mark_proofread_for_review"] = True
                    proofread_seen = True
                elif val in _BOOL_FALSE:
                    out["qa_auto_mark_proofread_for_review"] = False
                    proofread_seen = True
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
            elif key == "LT_EDITOR_MODE":
                out["lt_editor_mode"] = _normalize_lt_editor_mode(value)
            elif key == "LT_SERVER_URL":
                out["lt_server_url"] = value
            elif key == "LT_TIMEOUT_MS":
                out["lt_timeout_ms"] = _normalize_lt_timeout_ms(value)
            elif key == "LT_PICKY_MODE":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["lt_picky_mode"] = True
                elif val in _BOOL_FALSE:
                    out["lt_picky_mode"] = False
            elif key == "LT_LOCALE_MAP":
                out["lt_locale_map"] = _normalize_lt_locale_map(value)
            elif key == "QA_CHECK_LANGUAGETOOL":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_check_languagetool"] = True
                elif val in _BOOL_FALSE:
                    out["qa_check_languagetool"] = False
            elif key == "QA_LANGUAGETOOL_MAX_ROWS":
                out["qa_languagetool_max_rows"] = _normalize_qa_languagetool_max_rows(
                    value
                )
            elif key == "QA_LANGUAGETOOL_AUTOMARK":
                val = value.lower()
                if val in _BOOL_TRUE:
                    out["qa_languagetool_automark"] = True
                elif val in _BOOL_FALSE:
                    out["qa_languagetool_automark"] = False
            else:
                extras[key] = value
    except OSError:
        return {}
    if legacy_touched is not None:
        if not translated_seen:
            out["qa_auto_mark_translated_for_review"] = legacy_touched
        if not proofread_seen:
            out["qa_auto_mark_proofread_for_review"] = legacy_touched
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
    merged["lt_editor_mode"] = _normalize_lt_editor_mode(
        merged.get("lt_editor_mode", "auto")
    )
    merged["lt_server_url"] = (
        str(merged.get("lt_server_url", "")).strip() or _default_lt_server_url()
    )
    merged["lt_timeout_ms"] = _normalize_lt_timeout_ms(
        merged.get("lt_timeout_ms", 1200)
    )
    merged["lt_picky_mode"] = bool(merged.get("lt_picky_mode", False))
    merged["lt_locale_map"] = _normalize_lt_locale_map(
        merged.get("lt_locale_map", "{}")
    )
    merged["qa_check_languagetool"] = bool(merged.get("qa_check_languagetool", False))
    merged["qa_languagetool_max_rows"] = _normalize_qa_languagetool_max_rows(
        merged.get("qa_languagetool_max_rows", _QA_LT_MAX_ROWS_DEFAULT)
    )
    merged["qa_languagetool_automark"] = bool(
        merged.get("qa_languagetool_automark", False)
    )
    merged["qa_auto_mark_for_review"] = bool(
        merged.get("qa_auto_mark_for_review", False)
    )
    merged["qa_auto_mark_translated_for_review"] = bool(
        merged.get("qa_auto_mark_for_review", False)
        and merged.get("qa_auto_mark_translated_for_review", False)
    )
    merged["qa_auto_mark_proofread_for_review"] = bool(
        merged.get("qa_auto_mark_for_review", False)
        and merged.get("qa_auto_mark_proofread_for_review", False)
    )
    merged["qa_auto_mark_touched_for_review"] = bool(
        merged.get("qa_auto_mark_translated_for_review", False)
        or merged.get("qa_auto_mark_proofread_for_review", False)
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
    prefs["lt_editor_mode"] = _normalize_lt_editor_mode(
        prefs.get("lt_editor_mode", "auto")
    )
    prefs["lt_server_url"] = (
        str(prefs.get("lt_server_url", "")).strip() or _default_lt_server_url()
    )
    prefs["lt_timeout_ms"] = _normalize_lt_timeout_ms(prefs.get("lt_timeout_ms", 1200))
    prefs["lt_picky_mode"] = bool(prefs.get("lt_picky_mode", False))
    prefs["lt_locale_map"] = _normalize_lt_locale_map(prefs.get("lt_locale_map", "{}"))
    prefs["qa_check_languagetool"] = bool(prefs.get("qa_check_languagetool", False))
    prefs["qa_languagetool_max_rows"] = _normalize_qa_languagetool_max_rows(
        prefs.get("qa_languagetool_max_rows", _QA_LT_MAX_ROWS_DEFAULT)
    )
    prefs["qa_languagetool_automark"] = bool(
        prefs.get("qa_languagetool_automark", False)
    )
    prefs["qa_auto_mark_for_review"] = bool(
        prefs.get("qa_auto_mark_for_review", False)
    )
    prefs["qa_auto_mark_translated_for_review"] = bool(
        prefs.get("qa_auto_mark_for_review", False)
        and prefs.get("qa_auto_mark_translated_for_review", False)
    )
    prefs["qa_auto_mark_proofread_for_review"] = bool(
        prefs.get("qa_auto_mark_for_review", False)
        and prefs.get("qa_auto_mark_proofread_for_review", False)
    )
    prefs["qa_auto_mark_touched_for_review"] = bool(
        prefs.get("qa_auto_mark_translated_for_review", False)
        or prefs.get("qa_auto_mark_proofread_for_review", False)
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
        "QA_AUTO_MARK_TRANSLATED_FOR_REVIEW",
        "QA_AUTO_MARK_PROOFREAD_FOR_REVIEW",
        "LAST_ROOT",
        "LAST_LOCALES",
        "WINDOW_GEOMETRY",
        "DEFAULT_ROOT",
        "SEARCH_SCOPE",
        "REPLACE_SCOPE",
        "TM_IMPORT_DIR",
        "LT_EDITOR_MODE",
        "LT_SERVER_URL",
        "LT_TIMEOUT_MS",
        "LT_PICKY_MODE",
        "LT_LOCALE_MAP",
        "QA_CHECK_LANGUAGETOOL",
        "QA_LANGUAGETOOL_MAX_ROWS",
        "QA_LANGUAGETOOL_AUTOMARK",
    }
    qa_lt_max_rows = _normalize_qa_languagetool_max_rows(
        prefs.get("qa_languagetool_max_rows", _QA_LT_MAX_ROWS_DEFAULT)
    )
    qa_auto_mark_for_review = bool(prefs.get("qa_auto_mark_for_review", False))
    qa_auto_mark_translated_for_review = bool(
        qa_auto_mark_for_review
        and prefs.get("qa_auto_mark_translated_for_review", False)
    )
    qa_auto_mark_proofread_for_review = bool(
        qa_auto_mark_for_review
        and prefs.get("qa_auto_mark_proofread_for_review", False)
    )
    qa_auto_mark_touched_for_review = bool(
        qa_auto_mark_translated_for_review or qa_auto_mark_proofread_for_review
    )
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
            f"{'true' if qa_auto_mark_for_review else 'false'}"
        ),
        (
            "QA_AUTO_MARK_TOUCHED_FOR_REVIEW="
            f"{'true' if qa_auto_mark_touched_for_review else 'false'}"
        ),
        (
            "QA_AUTO_MARK_TRANSLATED_FOR_REVIEW="
            f"{'true' if qa_auto_mark_translated_for_review else 'false'}"
        ),
        (
            "QA_AUTO_MARK_PROOFREAD_FOR_REVIEW="
            f"{'true' if qa_auto_mark_proofread_for_review else 'false'}"
        ),
        (
            "LT_EDITOR_MODE="
            f"{_normalize_lt_editor_mode(prefs.get('lt_editor_mode', 'auto'))}"
        ),
        (
            "LT_SERVER_URL="
            f"{str(prefs.get('lt_server_url', '')).strip() or _default_lt_server_url()}"
        ),
        f"LT_TIMEOUT_MS={_normalize_lt_timeout_ms(prefs.get('lt_timeout_ms', 1200))}",
        f"LT_PICKY_MODE={'true' if prefs.get('lt_picky_mode', False) else 'false'}",
        f"LT_LOCALE_MAP={_normalize_lt_locale_map(prefs.get('lt_locale_map', '{}'))}",
        (
            "QA_CHECK_LANGUAGETOOL="
            f"{'true' if prefs.get('qa_check_languagetool', False) else 'false'}"
        ),
        ("QA_LANGUAGETOOL_MAX_ROWS=" f"{qa_lt_max_rows}"),
        (
            "QA_LANGUAGETOOL_AUTOMARK="
            f"{'true' if prefs.get('qa_languagetool_automark', False) else 'false'}"
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
