"""Application configuration loading utilities for repository-local settings."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

tomllib: ModuleType | None
try:  # Python 3.11+
    tomllib = importlib.import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Store effective runtime file and diff settings."""

    cache_dir: str = ".tzp/cache"
    config_dir: str = ".tzp/config"
    cache_ext: str = ".bin"
    translation_ext: str = ".txt"
    comment_prefix: str = "--"
    en_hash_filename: str = "en.hashes.bin"
    insertion_enabled_globs: tuple[str, ...] = ("*.txt",)
    preview_context_lines: int = 3


LEGACY_CACHE_DIR = ".tzp-cache"
LEGACY_CONFIG_DIR = ".tzp-config"


def _candidate_roots(root: Path | None) -> list[Path]:
    roots = [Path.cwd()]
    if root is not None:
        roots.append(root)
    seen: set[Path] = set()
    out: list[Path] = []
    for entry in roots:
        entry = entry.resolve()
        if entry in seen:
            continue
        seen.add(entry)
        out.append(entry)
    return out


def _load_toml(path: Path) -> dict[str, Any]:
    if tomllib is None or not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _nonempty_string(value: Any, *, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _normalize_ext(value: Any, *, default: str) -> str:
    if not isinstance(value, str) or not (value := value.strip()):
        return default
    return value if value.startswith(".") else f".{value}"


def _normalize_globs(value: Any, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        candidate = [value]
    elif isinstance(value, list):
        candidate = value
    else:
        return default
    out: list[str] = []
    seen: set[str] = set()
    for item in candidate:
        if not isinstance(item, str):
            continue
        glob = item.strip()
        if not glob or glob in seen:
            continue
        seen.add(glob)
        out.append(glob)
    return tuple(out) if out else default


def _normalize_preview_context_lines(value: Any, *, default: int = 3) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(0, min(parsed, 20))


@lru_cache(maxsize=8)
def load(root: Path | None = None) -> AppConfig:
    """Load and merge app configuration from `config/app.toml` candidates."""
    cfg = AppConfig()
    for base in _candidate_roots(root):
        path = base / "config" / "app.toml"
        data = _load_toml(path)
        paths = data.get("paths", {})
        cache = data.get("cache", {})
        if isinstance(paths, dict):
            cfg = replace(
                cfg,
                cache_dir=_nonempty_string(
                    paths.get("cache_dir"), default=cfg.cache_dir
                ),
                config_dir=_nonempty_string(
                    paths.get("config_dir"), default=cfg.config_dir
                ),
            )
        if isinstance(cache, dict):
            cfg = replace(
                cfg,
                cache_ext=_normalize_ext(cache.get("extension"), default=cfg.cache_ext),
                en_hash_filename=_nonempty_string(
                    cache.get("en_hash_filename"), default=cfg.en_hash_filename
                ),
            )
        formats = data.get("formats", {})
        if isinstance(formats, dict):
            cfg = replace(
                cfg,
                translation_ext=_normalize_ext(
                    formats.get("translation_ext"), default=cfg.translation_ext
                ),
                comment_prefix=_nonempty_string(
                    formats.get("comment_prefix"), default=cfg.comment_prefix
                ),
            )
        diff = data.get("diff", {})
        if isinstance(diff, dict):
            cfg = replace(
                cfg,
                insertion_enabled_globs=_normalize_globs(
                    diff.get("insertion_enabled_globs"),
                    default=cfg.insertion_enabled_globs,
                ),
                preview_context_lines=_normalize_preview_context_lines(
                    diff.get("preview_context_lines"),
                    default=cfg.preview_context_lines,
                ),
            )
    return cfg
