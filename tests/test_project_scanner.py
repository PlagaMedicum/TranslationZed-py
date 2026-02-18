"""Test module for project scanner."""

from pathlib import Path

import pytest

from translationzed_py.core import (
    LocaleMeta,
    list_translatable_files,
    scan_root,
    scan_root_with_errors,
)
from translationzed_py.core.project_scanner import (
    LanguageFileError,
    _parse_language_file,
    _top_level_dir,
)


def test_scan_root_discovers_locales(tmp_path: Path) -> None:
    """Verify scan root discovers locales."""
    root = tmp_path / "project"
    root.mkdir()
    for loc in ("EN", "EN UK", "PTBR"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            "VERSION = 1,\ntext = English,\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (root / loc / "ui.txt").write_text("dummy")
    (root / ".tzp" / "cache").mkdir(parents=True)
    (root / "_TVRADIO_TRANSLATIONS").mkdir()
    (root / ".git").mkdir()
    (root / ".vscode").mkdir()
    result = scan_root(root)
    assert set(result) == {"EN", "EN UK", "PTBR"}
    assert all(isinstance(meta, LocaleMeta) for meta in result.values())


def test_scan_root_reads_language_txt(prod_like_root: Path) -> None:
    """Verify scan root reads language txt."""
    locales = scan_root(prod_like_root)
    assert locales["EN"].display_name == "English"
    assert locales["EN"].charset.upper() == "UTF-8"
    assert locales["RU"].charset.upper() == "CP1251"
    assert locales["KO"].charset.upper() == "UTF-16"


def test_scan_root_requires_language_txt(tmp_path: Path) -> None:
    """Verify scan root requires language txt."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "EN").mkdir()
    with pytest.raises(ValueError):
        scan_root(root)


def test_scan_root_requires_charset(tmp_path: Path) -> None:
    """Verify scan root requires charset."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "EN").mkdir()
    (root / "EN" / "language.txt").write_text("text = English,\n", encoding="utf-8")
    with pytest.raises(ValueError):
        scan_root(root)


def test_scan_root_with_errors_skips_invalid(tmp_path: Path) -> None:
    """Verify scan root with errors skips invalid."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "EN").mkdir()
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "BE").mkdir()
    locales, errors = scan_root_with_errors(root)
    assert "EN" in locales
    assert "BE" not in locales
    assert errors


def test_list_translatable_files_excludes_non_translatables(
    prod_like_root: Path,
) -> None:
    """Verify list translatable files excludes non translatables."""
    en_path = prod_like_root / "EN"
    files = list_translatable_files(en_path)
    names = {p.name for p in files}
    assert "language.txt" not in names
    assert "credits.txt" not in names
    assert "IG_UI_EN.txt" in names


def test_list_translatable_files_ignores_tvradio(prod_like_root: Path) -> None:
    """Verify list translatable files ignores tvradio."""
    root = prod_like_root
    locales = scan_root(root)
    assert "_TVRADIO_TRANSLATIONS" not in locales


def test_project_scanner_helpers_cover_top_level_and_read_error_paths(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify scanner helper behavior for top-level parsing and read failures."""
    assert _top_level_dir("") is None
    assert _top_level_dir("/.tzp/cache") == ".tzp"

    lang_file = tmp_path / "language.txt"
    lang_file.write_text("text = EN,\ncharset = UTF-8,\n", encoding="utf-8")

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("cannot read")),
    )
    with pytest.raises(LanguageFileError, match="Failed to read language.txt"):
        _parse_language_file(lang_file)


def test_scan_root_with_errors_raises_for_non_directory_input(tmp_path: Path) -> None:
    """Verify scan root with errors rejects non-directory roots."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan_root_with_errors(file_path)
