from pathlib import Path

from translationzed_py.core import LocaleMeta, list_translatable_files, scan_root


def test_scan_root_discovers_locales(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for loc in ("EN", "EN UK", "PTBR"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            "VERSION = 1,\ntext = English,\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (root / loc / "ui.txt").write_text("dummy")
    (root / ".tzp-cache").mkdir()
    (root / "_TVRADIO_TRANSLATIONS").mkdir()
    (root / ".git").mkdir()
    (root / ".vscode").mkdir()
    result = scan_root(root)
    assert set(result) == {"EN", "EN UK", "PTBR"}
    assert all(isinstance(meta, LocaleMeta) for meta in result.values())


def test_scan_root_reads_language_txt(prod_like_root: Path) -> None:
    locales = scan_root(prod_like_root)
    assert locales["EN"].display_name == "English"
    assert locales["EN"].charset.upper() == "UTF-8"
    assert locales["RU"].charset.upper() == "CP1251"
    assert locales["KO"].charset.upper() == "UTF-16"


def test_list_translatable_files_excludes_non_translatables(prod_like_root: Path) -> None:
    en_path = prod_like_root / "EN"
    files = list_translatable_files(en_path)
    names = {p.name for p in files}
    assert "language.txt" not in names
    assert "credits.txt" not in names
    assert "IG_UI_EN.txt" in names


def test_list_translatable_files_ignores_tvradio(prod_like_root: Path) -> None:
    root = prod_like_root
    locales = scan_root(root)
    assert "_TVRADIO_TRANSLATIONS" not in locales
