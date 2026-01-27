from __future__ import annotations

from pathlib import Path
from typing import Any

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}

_DEFAULTS: dict[str, Any] = {
    "prompt_write_on_exit": True,
}


def _config_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / ".tzp-config"


def _config_path(root: Path | None = None) -> Path:
    return _config_dir(root) / "settings.env"


def _parse_env(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    out: dict[str, Any] = {}
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
    except OSError:
        return {}
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
    for base in _candidate_roots(root):
        merged.update(_parse_env(_config_path(base)))
    return merged


def save(prefs: dict[str, Any], root: Path | None = None) -> None:
    """Persist preferences to disk (atomic replace)."""
    path = _config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = "\n".join(
        [
            f"PROMPT_WRITE_ON_EXIT={'true' if prefs.get('prompt_write_on_exit', True) else 'false'}",
            "",
        ]
    )
    tmp = path.with_suffix(".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(path)
