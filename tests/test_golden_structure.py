from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.saver import save


def _run_case(
    tmp_path: Path,
    *,
    fixture: str,
    filename: str,
    updates: dict[str, str],
) -> None:
    base = Path("tests/fixtures/golden")
    src = base / f"{fixture}_input.txt"
    expected = base / f"{fixture}_expected.txt"
    dest = tmp_path / filename
    dest.write_bytes(src.read_bytes())
    pf = parse(dest, encoding="utf-8")
    save(pf, updates, encoding="utf-8")
    assert dest.read_bytes() == expected.read_bytes()


def test_structure_recorded_media_slice(tmp_path: Path) -> None:
    _run_case(
        tmp_path,
        fixture="recorded_media",
        filename="Recorded_Media_BE.txt",
        updates={
            "MEDIA_DETAIL": 'A "quoted" word and a backslash \\ and more',
            "MEDIA_CHAIN": "Hola",
        },
    )


def test_structure_stash_slice(tmp_path: Path) -> None:
    _run_case(
        tmp_path,
        fixture="stash",
        filename="Stash_BE.txt",
        updates={"STASH_HEADER": "Header2"},
    )


def test_structure_news_raw(tmp_path: Path) -> None:
    _run_case(
        tmp_path,
        fixture="news_raw",
        filename="News_BE.txt",
        updates={"News_BE.txt": "New raw content\nLine 2\n"},
    )
