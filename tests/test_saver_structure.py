"""Test module for saver structure."""

from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.saver import save


def _save_and_read(tmp_path: Path, text: str, updates: dict[str, str]) -> str:
    path = tmp_path / "file.txt"
    path.write_text(text, encoding="utf-8")
    pf = parse(path, encoding="utf-8")
    save(pf, updates, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def test_save_preserves_stray_quotes_with_markup(tmp_path: Path) -> None:
    """Verify save preserves stray quotes with markup."""
    text = 'X = " <CENTRE> "<SIZE:large> hello",\nY = "Ok"\n'
    out = _save_and_read(tmp_path, text, {"Y": "Fine"})
    assert out == 'X = " <CENTRE> "<SIZE:large> hello",\nY = "Fine"\n'


def test_save_preserves_double_slash_header(tmp_path: Path) -> None:
    """Verify save preserves double slash header."""
    text = '// Auto-generated file\nX = "Hello"\nY = "World"\n'
    out = _save_and_read(tmp_path, text, {"Y": "Earth"})
    assert out == '// Auto-generated file\nX = "Hello"\nY = "Earth"\n'


def test_save_preserves_trivia_spacing(tmp_path: Path) -> None:
    """Verify save preserves trivia spacing."""
    text = 'HELLO \t =  "Hel"  ..  "lo"  -- cmt  \n'
    out = _save_and_read(tmp_path, text, {"HELLO": "Hola"})
    assert out == 'HELLO \t =  "Hol"  ..  "a"  -- cmt  \n'


def test_save_raw_replaces_entire_file(tmp_path: Path) -> None:
    """Verify save raw replaces entire file."""
    text = 'Line with "=" and "quotes"\n'
    path = tmp_path / "News_BE.txt"
    path.write_text(text, encoding="utf-8")
    pf = parse(path, encoding="utf-8")
    save(pf, {"News_BE.txt": "New raw content\n"}, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == "New raw content\n"
