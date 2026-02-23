"""Application configuration loading utilities for repository-local settings."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
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
    """Store effective runtime paths and adapter identifiers."""

    cache_dir: str = ".tzp/cache"
    config_dir: str = ".tzp/config"
    cache_ext: str = ".bin"
    translation_ext: str = ".txt"
    comment_prefix: str = "--"
    en_hash_filename: str = "en.hashes.bin"
    parser_adapter: str = "lua_v1"
    ui_adapter: str = "pyside6"
    cache_adapter: str = "binary_v1"
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
    except OSError:
        return {}


def _normalize_ext(value: str) -> str:
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
        glob = str(item).strip()
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
        adapters = data.get("adapters", {})
        if isinstance(paths, dict):
            cfg = AppConfig(
                cache_dir=paths.get("cache_dir", cfg.cache_dir),
                config_dir=paths.get("config_dir", cfg.config_dir),
                cache_ext=cfg.cache_ext,
                translation_ext=cfg.translation_ext,
                comment_prefix=cfg.comment_prefix,
                parser_adapter=cfg.parser_adapter,
                ui_adapter=cfg.ui_adapter,
                cache_adapter=cfg.cache_adapter,
                insertion_enabled_globs=cfg.insertion_enabled_globs,
                preview_context_lines=cfg.preview_context_lines,
            )
        if isinstance(cache, dict):
            ext = cache.get("extension", cfg.cache_ext)
            cfg = AppConfig(
                cache_dir=cfg.cache_dir,
                config_dir=cfg.config_dir,
                cache_ext=_normalize_ext(str(ext)),
                translation_ext=cfg.translation_ext,
                comment_prefix=cfg.comment_prefix,
                en_hash_filename=str(
                    cache.get("en_hash_filename", cfg.en_hash_filename)
                ),
                parser_adapter=cfg.parser_adapter,
                ui_adapter=cfg.ui_adapter,
                cache_adapter=cfg.cache_adapter,
                insertion_enabled_globs=cfg.insertion_enabled_globs,
                preview_context_lines=cfg.preview_context_lines,
            )
        if isinstance(adapters, dict):
            cfg = AppConfig(
                cache_dir=cfg.cache_dir,
                config_dir=cfg.config_dir,
                cache_ext=cfg.cache_ext,
                translation_ext=cfg.translation_ext,
                comment_prefix=cfg.comment_prefix,
                en_hash_filename=cfg.en_hash_filename,
                parser_adapter=str(adapters.get("parser", cfg.parser_adapter)),
                ui_adapter=str(adapters.get("ui", cfg.ui_adapter)),
                cache_adapter=str(adapters.get("cache", cfg.cache_adapter)),
                insertion_enabled_globs=cfg.insertion_enabled_globs,
                preview_context_lines=cfg.preview_context_lines,
            )
        formats = data.get("formats", {})
        if isinstance(formats, dict):
            ext = formats.get("translation_ext", cfg.translation_ext)
            cfg = AppConfig(
                cache_dir=cfg.cache_dir,
                config_dir=cfg.config_dir,
                cache_ext=cfg.cache_ext,
                translation_ext=_normalize_ext(str(ext)),
                comment_prefix=str(formats.get("comment_prefix", cfg.comment_prefix)),
                en_hash_filename=cfg.en_hash_filename,
                parser_adapter=cfg.parser_adapter,
                ui_adapter=cfg.ui_adapter,
                cache_adapter=cfg.cache_adapter,
                insertion_enabled_globs=cfg.insertion_enabled_globs,
                preview_context_lines=cfg.preview_context_lines,
            )
        diff = data.get("diff", {})
        if isinstance(diff, dict):
            cfg = AppConfig(
                cache_dir=cfg.cache_dir,
                config_dir=cfg.config_dir,
                cache_ext=cfg.cache_ext,
                translation_ext=cfg.translation_ext,
                comment_prefix=cfg.comment_prefix,
                en_hash_filename=cfg.en_hash_filename,
                parser_adapter=cfg.parser_adapter,
                ui_adapter=cfg.ui_adapter,
                cache_adapter=cfg.cache_adapter,
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
