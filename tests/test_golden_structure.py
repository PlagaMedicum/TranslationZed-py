"""Test module for golden structure."""

from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.saver import save


def _run_case(
    tmp_path: Path,
    *,
    fixture: str,
    filename: str,
    updates: dict[str, str],
    expected: str | None = None,
) -> None:
    base = Path("tests/fixtures/golden")
    src = base / f"{fixture}_input.txt"
    expected_path = base / (expected or f"{fixture}_expected.txt")
    dest = tmp_path / filename
    dest.write_bytes(src.read_bytes())
    pf = parse(dest, encoding="utf-8")
    save(pf, updates, encoding="utf-8")
    # Keep assertions stable across platform-specific checkout EOL settings.
    assert dest.read_text(encoding="utf-8") == expected_path.read_text(encoding="utf-8")


def test_structure_recorded_media_slice(tmp_path: Path) -> None:
    """Verify structure recorded media slice."""
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
    """Verify structure stash slice."""
    _run_case(
        tmp_path,
        fixture="stash",
        filename="Stash_BE.txt",
        updates={"STASH_HEADER": "Header2"},
    )


def test_structure_news_raw(tmp_path: Path) -> None:
    """Verify structure news raw."""
    _run_case(
        tmp_path,
        fixture="news_raw",
        filename="News_BE.txt",
        updates={"News_BE.txt": "New raw content\nLine 2\n"},
    )


def test_structure_mixed_single(tmp_path: Path) -> None:
    """Verify structure mixed single."""
    _run_case(
        tmp_path,
        fixture="mixed",
        filename="Mixed_BE.txt",
        updates={"KEY_TWO": "Two updated"},
        expected="mixed_expected_single.txt",
    )


def test_structure_mixed_multi(tmp_path: Path) -> None:
    """Verify structure mixed multi."""
    _run_case(
        tmp_path,
        fixture="mixed",
        filename="Mixed_BE.txt",
        updates={
            "KEY_ONE": "One changed",
            "KEY_THREE": "World!",
            "KEY_FOUR": "XYZ",
            "KEY_FIVE": "Spaced out",
        },
        expected="mixed_expected_multi.txt",
    )


def test_structure_edge_cases(tmp_path: Path) -> None:
    """Verify structure edge cases."""
    _run_case(
        tmp_path,
        fixture="edge_cases",
        filename="EdgeCases_BE.txt",
        updates={"B": "Spaced out"},
        expected="edge_cases_expected.txt",
    )
