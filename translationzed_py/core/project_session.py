from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from pathlib import Path

from translationzed_py.core.app_config import LEGACY_CACHE_DIR


def _cache_roots(root: Path, cache_dir: str) -> tuple[Path, ...]:
    primary = root / cache_dir
    legacy = root / LEGACY_CACHE_DIR
    if legacy == primary:
        return (primary,)
    return (primary, legacy)


def collect_draft_files(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    has_drafts: Callable[[Path], bool],
    locales: Iterable[str] | None = None,
    opened_files: Collection[Path] | None = None,
) -> list[Path]:
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return []
    locale_list = [loc for loc in locales or [] if loc]
    files: list[Path] = []
    for cache_root in cache_roots:
        cache_dirs = (
            [cache_root / loc for loc in locale_list] if locale_list else [cache_root]
        )
        for cache_dir_path in cache_dirs:
            if not cache_dir_path.exists():
                continue
            for cache_path in cache_dir_path.rglob(f"*{cache_ext}"):
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (root / rel).with_suffix(translation_ext)
                if not original.exists():
                    continue
                if opened_files is not None and original not in opened_files:
                    continue
                if has_drafts(cache_path):
                    files.append(original)
    return sorted(set(files))


def find_last_opened_file(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    selected_locales: Iterable[str],
    read_last_opened: Callable[[Path], int],
) -> tuple[Path | None, int]:
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return None, 0
    locales = [loc for loc in selected_locales if loc]
    if not locales:
        return None, 0
    best_ts = 0
    best_path: Path | None = None
    scanned = 0
    for cache_root in cache_roots:
        for locale in locales:
            cache_dir_path = cache_root / locale
            if not cache_dir_path.exists():
                continue
            for cache_path in cache_dir_path.rglob(f"*{cache_ext}"):
                scanned += 1
                ts = read_last_opened(cache_path)
                if ts <= 0:
                    continue
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (root / rel).with_suffix(translation_ext)
                if not original.exists():
                    continue
                if ts > best_ts:
                    best_ts = ts
                    best_path = original
    return best_path, scanned
