from __future__ import annotations

from pathlib import Path

from translationzed_py.core.project_session import (
    collect_draft_files,
    find_last_opened_file,
)


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_draft_files_filters_by_opened_and_locale(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    _touch(root / "BE" / "b.txt")
    _touch(root / "RU" / "c.txt")
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    _touch(root / ".tzp" / "cache" / "BE" / "b.bin")
    _touch(root / ".tzp" / "cache" / "RU" / "c.bin")

    drafts = {
        root / ".tzp" / "cache" / "BE" / "a.bin",
        root / ".tzp" / "cache" / "RU" / "c.bin",
    }

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda cache_path: cache_path in drafts,
        locales=["BE", "RU"],
        opened_files={root / "BE" / "a.txt", root / "RU" / "c.txt"},
    )
    assert files == [root / "BE" / "a.txt", root / "RU" / "c.txt"]


def test_collect_draft_files_skips_missing_originals(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "ghost.bin")

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda _path: True,
    )
    assert files == []


def test_find_last_opened_file_selects_latest_timestamp(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    _touch(root / "BE" / "b.txt")
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    _touch(root / ".tzp" / "cache" / "BE" / "b.bin")

    timestamps = {
        root / ".tzp" / "cache" / "BE" / "a.bin": 10,
        root / ".tzp" / "cache" / "BE" / "b.bin": 20,
    }
    best, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        read_last_opened=lambda cache_path: timestamps.get(cache_path, 0),
    )
    assert best == root / "BE" / "b.txt"
    assert scanned == 2


def test_find_last_opened_file_returns_none_without_selected_locales(
    tmp_path: Path,
) -> None:
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    best, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=[],
        read_last_opened=lambda _cache_path: 1,
    )
    assert best is None
    assert scanned == 0


def test_collect_draft_files_reads_legacy_cache_dir(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    legacy_cache = root / ".tzp-cache" / "BE" / "a.bin"
    _touch(legacy_cache)

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda cache_path: cache_path == legacy_cache,
        locales=["BE"],
    )

    assert files == [root / "BE" / "a.txt"]
