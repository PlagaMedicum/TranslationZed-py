"""Test module for en hash cache."""

from pathlib import Path

from translationzed_py.core.en_hash_cache import (
    _cache_path,
    _legacy_cache_path,
    compute,
    read,
    write,
)


def _init_en_project(root: Path) -> Path:
    en = root / "EN"
    en.mkdir(parents=True, exist_ok=True)
    (en / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n",
        encoding="utf-8",
    )
    file = en / "ui.txt"
    file.write_text('HELLO = "Hi"\n', encoding="utf-8")
    return file


def test_en_hash_roundtrip(tmp_path: Path) -> None:
    """Verify en hash roundtrip."""
    root = tmp_path / "proj"
    _init_en_project(root)

    hashes = compute(root)
    assert hashes
    write(root, hashes)
    restored = read(root)
    assert restored == hashes


def test_compute_returns_empty_when_en_locale_is_missing(tmp_path: Path) -> None:
    """Verify compute yields empty mapping without EN locale metadata."""
    root = tmp_path / "proj"
    ru = root / "RU"
    ru.mkdir(parents=True)
    (ru / "language.txt").write_text(
        "text = Russian,\ncharset = UTF-8,\n",
        encoding="utf-8",
    )
    (ru / "ui.txt").write_text('HELLO = "Privet"\n', encoding="utf-8")
    assert compute(root) == {}


def test_compute_skips_files_that_fail_to_read(tmp_path: Path, monkeypatch) -> None:
    """Verify compute continues when one source file raises read errors."""
    root = tmp_path / "proj"
    unreadable = _init_en_project(root)
    second = root / "EN" / "ok.txt"
    second.write_text('BYE = "Ok"\n', encoding="utf-8")

    original = Path.read_bytes

    def _patched_read_bytes(path_obj: Path) -> bytes:
        if path_obj == unreadable:
            raise OSError("boom")
        return original(path_obj)

    monkeypatch.setattr(Path, "read_bytes", _patched_read_bytes)
    hashes = compute(root)
    assert f"EN/{unreadable.name}" not in hashes
    assert f"EN/{second.name}" in hashes


def test_read_returns_empty_for_missing_invalid_and_truncated_cache(tmp_path: Path) -> None:
    """Verify read safely handles absent or malformed cache data."""
    root = tmp_path / "proj"
    _init_en_project(root)
    cache = _cache_path(root)
    cache.parent.mkdir(parents=True, exist_ok=True)

    assert read(root) == {}

    cache.write_bytes(b"BAD!")
    assert read(root) == {}

    cache.write_bytes(b"ENH1")
    assert read(root) == {}


def test_read_uses_legacy_cache_when_current_cache_is_missing(tmp_path: Path) -> None:
    """Verify read falls back to legacy cache path when needed."""
    root = tmp_path / "proj"
    _init_en_project(root)
    hashes = {"EN/ui.txt": 123}
    write(root, hashes)

    current = _cache_path(root)
    legacy = _legacy_cache_path(root)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    current.replace(legacy)

    assert current.exists() is False
    assert read(root) == hashes


def test_write_empty_hashes_removes_current_and_legacy_cache(tmp_path: Path) -> None:
    """Verify write clears both cache locations when hashes are empty."""
    root = tmp_path / "proj"
    _init_en_project(root)
    current = _cache_path(root)
    legacy = _legacy_cache_path(root)
    current.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    current.write_bytes(b"current")
    legacy.write_bytes(b"legacy")

    write(root, {})

    assert current.exists() is False
    assert legacy.exists() is False
