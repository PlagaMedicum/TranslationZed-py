"""Test module for golden roundtrip."""

from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.saver import save


def _run_case(
    tmp_path: Path, name: str, encoding: str, updates: dict[str, str]
) -> None:
    base = Path("tests/fixtures/golden")
    src = base / f"{name}_input.txt"
    expected = base / f"{name}_expected.txt"
    dest = tmp_path / src.name
    dest.write_bytes(src.read_bytes())
    pf = parse(dest, encoding=encoding)
    save(pf, updates, encoding=encoding)
    assert dest.read_bytes() == expected.read_bytes()


def test_golden_utf8(tmp_path: Path):
    """Verify golden utf8."""
    _run_case(
        tmp_path,
        "utf8",
        "utf-8",
        {"HELLO": "Hola", "SINGLE": "No"},
    )


def test_golden_cp1251(tmp_path: Path):
    """Verify golden cp1251."""
    _run_case(
        tmp_path,
        "cp1251",
        "cp1251",
        {"UI_OK": "Здравствуйте"},
    )


def test_golden_utf16(tmp_path: Path):
    """Verify golden utf16."""
    _run_case(
        tmp_path,
        "utf16",
        "UTF-16",
        {"UI_OK": "테스트2"},
    )
