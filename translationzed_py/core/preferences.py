from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "prompt_write_on_exit": True,
}


def _config_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / ".tzp-config"


def _config_path(root: Path | None = None) -> Path:
    return _config_dir(root) / "settings.json"


def load(root: Path | None = None) -> dict[str, Any]:
    """
    Load preferences from disk, falling back to defaults.
    Unknown keys are preserved.
    """
    path = _config_path(root)
    data: dict[str, Any] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except FileNotFoundError:
        data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = dict(_DEFAULTS)
    merged.update(data)
    return merged


def save(prefs: dict[str, Any], root: Path | None = None) -> None:
    """Persist preferences to disk (atomic replace)."""
    path = _config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(prefs, ensure_ascii=True, indent=2, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(path)
