"""Test module for regression roundtrip."""

from pathlib import Path

import pytest

from translationzed_py.core import list_translatable_files, parse, scan_root
from translationzed_py.core.saver import save


def _roundtrip_locale_root(tmp_path: Path, root: Path) -> None:
    root = root.resolve()
    locales = scan_root(root)
    for meta in locales.values():
        for src in list_translatable_files(meta.path):
            rel = src.relative_to(root)
            dest = tmp_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            pf = parse(dest, encoding=meta.charset)
            save(pf, {}, encoding=meta.charset)
            assert dest.read_bytes() == src.read_bytes()


@pytest.mark.parametrize(
    "fixture_root",
    [
        "conflict_manual",
        "conflict_manual_cp1251",
        "conflict_manual_utf16",
    ],
    ids=["utf8-locale", "cp1251-locale", "utf16-locale"],
)
def test_roundtrip_locale_fixtures(tmp_path: Path, fixture_root: str) -> None:
    """Verify roundtrip locale fixtures."""
    root = Path("tests/fixtures") / fixture_root
    _roundtrip_locale_root(tmp_path, root)


def test_roundtrip_prod_like(tmp_path: Path) -> None:
    """Verify roundtrip prod like."""
    root = Path("tests/fixtures/prod_like")
    _roundtrip_locale_root(tmp_path, root)
